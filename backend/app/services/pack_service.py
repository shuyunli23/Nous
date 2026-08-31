"""Install / manage nous-pack/2 zip archives."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.database.models import Skill, SkillPack, SkillPackTool
from app.database.models.enums import SkillPackStatus, SkillSource, SkillStatus
from app.memory.skill_memory import index_skill, remove_skill
from app.repositories.skill_repo import SkillRepository
from app.schemas.skill import SkillSummary
from app.schemas.skill_pack import (
    InstalledPackDetail,
    InstalledPackSummary,
    PackArchiveImportResult,
    PackArchivePreview,
    PackToolSummary,
)
from app.skill.pack_archive import extract_pack_zip, install_tree
from app.skill.pack_format import parse_pack_directory, preview_dict

logger = get_logger(__name__)


class PackService:
    def __init__(self, session: AsyncSession | None = None) -> None:
        self.session = session
        self.skills = SkillRepository(session) if session is not None else None

    async def preview_bytes(self, data: bytes) -> PackArchivePreview:
        tmp_root: Path | None = None
        try:
            pack_root, _digest = extract_pack_zip(data)
            tmp_root = pack_root
            parsed = parse_pack_directory(pack_root)
            return PackArchivePreview.model_validate(preview_dict(parsed))
        except ValidationError:
            raise
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        finally:
            self._cleanup_extract(tmp_root)

    async def import_bytes(
        self,
        *,
        user_id: str,
        data: bytes,
        grant_permissions: list[str] | None = None,
        activate: bool = True,
        replace_existing: bool = True,
    ) -> PackArchiveImportResult:
        if self.session is None or self.skills is None:
            raise RuntimeError("PackService.import_bytes requires a DB session")
        session = self.session
        skills_repo = self.skills
        pack_root, digest = extract_pack_zip(data)
        try:
            try:
                parsed = parse_pack_directory(pack_root)
            except ValueError as exc:
                raise ValidationError(str(exc)) from exc

            if parsed.errors:
                raise ValidationError(
                    "Pack validation failed.",
                    details={"errors": parsed.errors, "warnings": parsed.warnings},
                )

            requested = list(parsed.permissions_requested)
            granted = list(grant_permissions) if grant_permissions is not None else list(requested)
            granted = self._normalize_grants(requested, granted)

            # Tools require script.python grant to enable runners
            has_tools = any(s.tools for s in parsed.skills)
            if has_tools and "script.python" not in granted and activate:
                raise ValidationError(
                    "This pack includes scripts; grant script.python to activate tools, "
                    "or set activate=false to install playbooks with tools disabled.",
                    details={"permissions_requested": requested},
                )

            existing = await self._get_by_pack_id(user_id, parsed.pack_id)
            replaced_id: str | None = None
            if existing is not None:
                if not replace_existing:
                    raise ConflictError(
                        f"Pack '{parsed.pack_id}' already installed "
                        f"(version {existing.version}).",
                        details={"pack_row_id": existing.id},
                    )
                replaced_id = existing.id
                await self._uninstall_row(existing, user_id=user_id)

            rel_install = (
                Path(settings.skill_packs_dir)
                / user_id
                / parsed.pack_id
                / parsed.version
            )
            abs_install = settings.resolve_path(str(rel_install))
            install_tree(pack_root, abs_install)

            status = (
                SkillPackStatus.ACTIVE
                if activate and (not has_tools or "script.python" in granted)
                else SkillPackStatus.PENDING_REVIEW
            )
            if not activate:
                status = SkillPackStatus.PENDING_REVIEW

            pack = SkillPack(
                user_id=user_id,
                pack_id=parsed.pack_id,
                version=parsed.version,
                name=parsed.name,
                description=parsed.description,
                format="nous-pack/2",
                permissions=granted,
                permissions_requested=requested,
                tags=parsed.tags,
                author=parsed.author,
                license=parsed.license,
                min_nous=parsed.min_nous,
                install_path=str(rel_install).replace("\\", "/"),
                content_hash=digest,
                status=status.value,
                manifest=parsed.manifest,
            )
            self.session.add(pack)
            await self.session.flush()

            skill_status = (
                SkillStatus.ACTIVE
                if status == SkillPackStatus.ACTIVE
                else SkillStatus.DRAFT
            )
            created_skills: list[Skill] = []
            tools_enabled = status == SkillPackStatus.ACTIVE and "script.python" in granted

            for sk in parsed.skills:
                tool_names = list(sk.tools_builtin) + [t.exposed_name for t in sk.tools]
                skill = await skills_repo.create(
                    user_id=user_id,
                    name=sk.name,
                    description=sk.description,
                    instruction=sk.instruction,
                    trigger_keywords=sk.trigger_keywords,
                    trigger_intent=sk.trigger_intent,
                    workflow=sk.workflow,
                    examples=sk.examples,
                    tools=tool_names,
                    confidence=sk.confidence,
                    source=SkillSource.IMPORTED,
                    status=skill_status,
                )
                skill.pack_row_id = pack.id
                skill.pack_skill_key = sk.key
                await self.session.flush()
                await index_skill(session, skill)
                created_skills.append(skill)

                for tool in sk.tools:
                    row = SkillPackTool(
                        pack_row_id=pack.id,
                        skill_id=skill.id,
                        name=tool.name,
                        exposed_name=tool.exposed_name,
                        description=tool.description,
                        parameters=tool.parameters,
                        runner=tool.runner,
                        skill_key=tool.skill_key,
                        enabled=tools_enabled,
                    )
                    self.session.add(row)

            await self.session.commit()
            await self.session.refresh(pack)

            logger.info(
                "skill_pack_archive_imported",
                pack_id=pack.pack_id,
                version=pack.version,
                skills=len(created_skills),
                tools=sum(len(s.tools) for s in parsed.skills),
                status=pack.status,
            )
            detail = await self.get_installed(user_id=user_id, pack_row_id=pack.id)
            return PackArchiveImportResult(
                pack=detail,
                created_skills=[SkillSummary.model_validate(s) for s in created_skills],
                replaced_pack_id=replaced_id,
                warnings=parsed.warnings,
            )
        finally:
            self._cleanup_extract(pack_root)

    async def list_installed(self, *, user_id: str) -> list[InstalledPackSummary]:
        result = await self.session.execute(
            select(SkillPack)
            .where(SkillPack.user_id == user_id)
            .options(selectinload(SkillPack.tools), selectinload(SkillPack.skills))
            .order_by(SkillPack.updated_at.desc())
        )
        packs = result.scalars().all()
        out: list[InstalledPackSummary] = []
        for p in packs:
            summary = InstalledPackSummary.model_validate(p)
            summary.tool_count = len(p.tools or [])
            summary.skill_count = len(p.skills or [])
            out.append(summary)
        return out

    async def get_installed(self, *, user_id: str, pack_row_id: str) -> InstalledPackDetail:
        pack = await self._get_row(user_id, pack_row_id)
        detail = InstalledPackDetail.model_validate(pack)
        detail.tool_count = len(pack.tools or [])
        detail.skill_count = len(pack.skills or [])
        detail.tools = [PackToolSummary.model_validate(t) for t in (pack.tools or [])]
        detail.skill_ids = [s.id for s in (pack.skills or [])]
        return detail

    async def set_status(
        self, *, user_id: str, pack_row_id: str, status: str
    ) -> InstalledPackDetail:
        pack = await self._get_row(user_id, pack_row_id)
        if status not in (SkillPackStatus.ACTIVE, SkillPackStatus.DISABLED):
            raise ValidationError("status must be active or disabled")
        pack.status = status
        enable_tools = status == SkillPackStatus.ACTIVE and "script.python" in (
            pack.permissions or []
        )
        for tool in pack.tools or []:
            tool.enabled = enable_tools
        skill_status = (
            SkillStatus.ACTIVE if status == SkillPackStatus.ACTIVE else SkillStatus.DISABLED
        )
        for skill in pack.skills or []:
            skill.status = skill_status.value
        await self.session.commit()
        return await self.get_installed(user_id=user_id, pack_row_id=pack_row_id)

    async def uninstall(self, *, user_id: str, pack_row_id: str) -> None:
        pack = await self._get_row(user_id, pack_row_id)
        await self._uninstall_row(pack, user_id=user_id)
        await self.session.commit()

    async def list_enabled_tool_schemas(self, *, user_id: str) -> list[dict[str, Any]]:
        """OpenAI tool schemas for all enabled pack tools owned by the user."""
        result = await self.session.execute(
            select(SkillPackTool)
            .join(SkillPack, SkillPackTool.pack_row_id == SkillPack.id)
            .where(
                SkillPack.user_id == user_id,
                SkillPack.status == SkillPackStatus.ACTIVE.value,
                SkillPackTool.enabled.is_(True),
            )
            .limit(settings.skill_pack_max_tools_in_prompt)
        )
        tools = result.scalars().all()
        schemas: list[dict[str, Any]] = []
        for tool in tools:
            schemas.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.exposed_name,
                        "description": tool.description,
                        "parameters": tool.parameters or {"type": "object", "properties": {}},
                    },
                }
            )
        return schemas

    async def resolve_tool(
        self, *, user_id: str, exposed_name: str
    ) -> tuple[SkillPack, SkillPackTool] | None:
        result = await self.session.execute(
            select(SkillPackTool)
            .join(SkillPack, SkillPackTool.pack_row_id == SkillPack.id)
            .where(
                SkillPack.user_id == user_id,
                SkillPackTool.exposed_name == exposed_name,
            )
            .options(selectinload(SkillPackTool.pack))
        )
        tool = result.scalar_one_or_none()
        if tool is None or tool.pack is None:
            return None
        return tool.pack, tool

    # ── internals ─────────────────────────────────────────────────────────

    def _normalize_grants(self, requested: list[str], granted: list[str]) -> list[str]:
        req = set(requested)
        out: list[str] = []
        for g in granted:
            g = g.strip()
            if not g:
                continue
            if g == "script.shell":
                raise ValidationError("script.shell is not supported.")
            if g not in req and g != "fs.read.pack":
                # Allow granting a subset; ignore unknowns not requested except fs.read.pack
                if g.startswith("env.") and g in req:
                    out.append(g)
                elif g in req:
                    out.append(g)
                else:
                    raise ValidationError(
                        f"Cannot grant permission not requested by pack: {g}",
                        details={"requested": requested},
                    )
            else:
                out.append(g)
        if "fs.read.pack" not in out and req:
            out.append("fs.read.pack")
        # Dedup preserve order
        seen: set[str] = set()
        uniq: list[str] = []
        for p in out:
            if p not in seen:
                seen.add(p)
                uniq.append(p)
        return uniq

    async def _get_by_pack_id(self, user_id: str, pack_id: str) -> SkillPack | None:
        result = await self.session.execute(
            select(SkillPack)
            .where(SkillPack.user_id == user_id, SkillPack.pack_id == pack_id)
            .options(selectinload(SkillPack.tools), selectinload(SkillPack.skills))
            .order_by(SkillPack.created_at.desc())
        )
        return result.scalars().first()

    async def _get_row(self, user_id: str, pack_row_id: str) -> SkillPack:
        result = await self.session.execute(
            select(SkillPack)
            .where(SkillPack.id == pack_row_id, SkillPack.user_id == user_id)
            .options(selectinload(SkillPack.tools), selectinload(SkillPack.skills))
        )
        pack = result.scalar_one_or_none()
        if pack is None:
            raise NotFoundError("Installed pack not found.")
        return pack

    async def _uninstall_row(self, pack: SkillPack, *, user_id: str) -> None:
        for skill in list(pack.skills or []):
            remove_skill(skill.id)
            await self.session.delete(skill)
        install = settings.resolve_path(pack.install_path)
        await self.session.delete(pack)
        await self.session.flush()
        if install.exists():
            shutil.rmtree(install, ignore_errors=True)

    @staticmethod
    def _cleanup_extract(pack_root: Path | None) -> None:
        if pack_root is None:
            return
        # Walk up to the mkdtemp root (nous-pack-*)
        cur = pack_root
        for _ in range(3):
            if cur.name.startswith("nous-pack-"):
                shutil.rmtree(cur, ignore_errors=True)
                return
            if cur.parent == cur:
                break
            cur = cur.parent
        shutil.rmtree(pack_root, ignore_errors=True)
