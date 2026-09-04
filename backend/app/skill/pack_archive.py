"""Safe zip extraction for nous-pack/2 archives."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import zipfile
from io import BytesIO
from pathlib import Path

from app.core.config import settings
from app.core.exceptions import ValidationError


def _is_within(directory: Path, target: Path) -> bool:
    try:
        target.resolve().relative_to(directory.resolve())
        return True
    except ValueError:
        return False


def extract_pack_zip(data: bytes, *, dest: Path | None = None) -> tuple[Path, str]:
    """Extract zip bytes into a temp (or given) directory.

    Returns (pack_root, sha256_hex).
    Raises ValidationError on zip slip / size / count violations.
    """
    if not data:
        raise ValidationError("Empty archive.")
    if len(data) > settings.skill_pack_max_zip_bytes:
        raise ValidationError(
            f"Archive exceeds {settings.skill_pack_max_zip_bytes} bytes compressed.",
            details={"max_zip_bytes": settings.skill_pack_max_zip_bytes},
        )

    digest = hashlib.sha256(data).hexdigest()
    root = Path(dest) if dest is not None else Path(tempfile.mkdtemp(prefix="nous-pack-"))
    root.mkdir(parents=True, exist_ok=True)

    try:
        with zipfile.ZipFile(BytesIO(data)) as zf:
            infos = zf.infolist()
            if len(infos) > settings.skill_pack_max_files:
                raise ValidationError(
                    f"Archive has too many files (>{settings.skill_pack_max_files})."
                )
            total_uncompressed = 0
            for info in infos:
                name = info.filename.replace("\\", "/")
                if not name or name.endswith("/"):
                    continue
                if name.startswith("/") or name.startswith("../") or "/../" in f"/{name}/":
                    raise ValidationError(f"Illegal path in archive: {name}")
                if info.is_dir():
                    continue
                is_symlink = (info.external_attr >> 16) & 0o170000 == 0o120000
                if is_symlink:
                    raise ValidationError(f"Symlinks are not allowed: {name}")
                total_uncompressed += info.file_size
                if total_uncompressed > settings.skill_pack_max_uncompressed_bytes:
                    raise ValidationError(
                        "Archive uncompressed size exceeds limit.",
                        details={
                            "max_uncompressed_bytes": settings.skill_pack_max_uncompressed_bytes
                        },
                    )
                target = (root / name).resolve()
                if not _is_within(root, target):
                    raise ValidationError(f"Zip slip blocked: {name}")
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info, "r") as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst, length=1024 * 256)
    except zipfile.BadZipFile as exc:
        shutil.rmtree(root, ignore_errors=True)
        raise ValidationError("Invalid zip archive.") from exc
    except ValidationError:
        shutil.rmtree(root, ignore_errors=True)
        raise
    except Exception:
        shutil.rmtree(root, ignore_errors=True)
        raise

    return _find_pack_root(root), digest


def _is_plugin_root(path: Path) -> bool:
    if (path / "plugin.json").is_file() or (path / "pack.json").is_file():
        return True
    if (path / "SKILL.md").is_file():
        return True
    pkg = path / "package.json"
    if pkg.is_file():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = None
        if isinstance(data, dict) and data.get("dsh") is not None:
            return True
    return False


def _find_pack_root(extracted: Path) -> Path:
    """If the zip wrapped a single top-level folder, use that as pack root."""
    if _is_plugin_root(extracted):
        return extracted
    children = [p for p in extracted.iterdir() if p.name != "__MACOSX"]
    if len(children) == 1 and children[0].is_dir() and _is_plugin_root(children[0]):
        return children[0]
    return extracted


def install_tree(src_root: Path, dest_root: Path) -> None:
    """Copy a validated pack tree into the durable install location."""
    if dest_root.exists():
        shutil.rmtree(dest_root)
    dest_root.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src_root, dest_root)
