"""模型配置 CRUD 与连通性测试。"""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.nexusmind.db.base import utcnow
from app.nexusmind.models import ModelConfig
from app.nexusmind.schemas.model_config import (
    ModelConfigCreate,
    ModelConfigOut,
    ModelConfigUpdate,
    ModelTestRequest,
    ModelTestResult,
)
from app.nexusmind.services.llm_service import ModelEndpoint, test_connection
from app.nexusmind.utils.errors import NotFoundError, ValidationError


def mask_api_key(api_key: str) -> str:
    key = api_key or ""
    if not key:
        return ""
    if len(key) <= 8:
        return "*" * len(key)
    return f"{key[:3]}****{key[-4:]}"


def _is_masked_secret(value: str | None, original: str = "") -> bool:
    if value is None:
        return False
    text = str(value)
    if text.startswith("***"):
        return True
    if original and text == mask_api_key(original):
        return True
    return False


def _public_extra_config(extra: dict | None) -> dict:
    """对外返回时掩码敏感字段，避免 Secret 明文回传前端。"""
    data = dict(extra or {})
    secret = data.get("aws_secret_access_key")
    if secret:
        data["aws_secret_access_key"] = mask_api_key(str(secret))
        data["has_aws_secret"] = True
    elif "aws_secret_access_key" in data:
        data["has_aws_secret"] = False
    session = data.get("aws_session_token")
    if session:
        data["aws_session_token"] = mask_api_key(str(session))
    return data


def _merge_extra_config(old: dict | None, new: dict | None) -> dict:
    """合并 extra_config，掩码占位不覆盖已有密钥。"""
    merged = dict(old or {})
    incoming = dict(new or {})
    for key in ("aws_secret_access_key", "aws_session_token"):
        if key not in incoming:
            continue
        if _is_masked_secret(str(incoming.get(key) or ""), str(merged.get(key) or "")):
            incoming.pop(key, None)
    merged.update(incoming)
    return merged


def to_out(item: ModelConfig) -> ModelConfigOut:
    return ModelConfigOut(
        id=item.id,
        name=item.name,
        provider=item.provider,
        api_key_masked=mask_api_key(item.api_key),
        has_api_key=bool(item.api_key),
        base_url=item.base_url or "",
        resolved_base_url=item.resolved_base_url,
        model_name=item.model_name,
        temperature=item.temperature,
        max_tokens=item.max_tokens,
        is_default=item.is_default,
        is_active=item.is_active,
        last_tested_at=item.last_tested_at,
        last_test_ok=item.last_test_ok,
        last_test_message=item.last_test_message,
        extra_config=_public_extra_config(item.extra_config),
        created_time=item.created_time,
        updated_time=item.updated_time,
    )


def list_models(db: Session) -> list[ModelConfig]:
    return list(
        db.scalars(
            select(ModelConfig).order_by(
                ModelConfig.is_default.desc(),
                ModelConfig.updated_time.desc(),
            )
        ).all()
    )


def get_model(db: Session, model_id: str) -> ModelConfig:
    item = db.get(ModelConfig, model_id)
    if item is None:
        raise NotFoundError("模型配置不存在")
    return item


def get_default_model(db: Session) -> ModelConfig | None:
    return db.scalar(
        select(ModelConfig)
        .where(ModelConfig.is_active.is_(True), ModelConfig.is_default.is_(True))
        .limit(1)
    ) or db.scalar(
        select(ModelConfig)
        .where(ModelConfig.is_active.is_(True))
        .order_by(ModelConfig.updated_time.desc())
        .limit(1)
    )


def _clear_default(db: Session) -> None:
    db.execute(update(ModelConfig).where(ModelConfig.is_default.is_(True)).values(is_default=False))


def create_model(db: Session, payload: ModelConfigCreate) -> ModelConfig:
    if payload.is_default:
        _clear_default(db)
    elif not db.scalar(select(ModelConfig.id).limit(1)):
        # 第一条自动成为默认
        payload.is_default = True

    item = ModelConfig(
        name=payload.name,
        provider=payload.provider,
        api_key=payload.api_key or "",
        base_url=(payload.base_url or "").strip(),
        model_name=payload.model_name,
        temperature=payload.temperature,
        max_tokens=payload.max_tokens,
        is_default=payload.is_default,
        is_active=payload.is_active,
        extra_config=payload.extra_config or {},
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_model(db: Session, model_id: str, payload: ModelConfigUpdate) -> ModelConfig:
    item = get_model(db, model_id)
    data = payload.model_dump(exclude_unset=True)

    if data.get("is_default") is True:
        _clear_default(db)

    if "api_key" in data:
        new_key = data.pop("api_key")
        if new_key is None:
            pass
        elif _is_masked_secret(new_key, item.api_key):
            # 掩码占位 → 保留原密钥
            pass
        else:
            # 含空字符串：允许 Ollama 等场景清空
            item.api_key = new_key

    if "extra_config" in data and data["extra_config"] is not None:
        data["extra_config"] = _merge_extra_config(item.extra_config, data["extra_config"])

    for field, value in data.items():
        if field == "base_url" and value is not None:
            setattr(item, field, value.strip())
        else:
            setattr(item, field, value)

    # 不允许取消唯一默认后系统没有默认：若全无默认，把当前条设默认
    if not db.scalar(select(ModelConfig.id).where(ModelConfig.is_default.is_(True))):
        item.is_default = True

    db.commit()
    db.refresh(item)
    return item


def delete_model(db: Session, model_id: str) -> None:
    item = get_model(db, model_id)
    was_default = item.is_default
    db.delete(item)
    db.commit()
    if was_default:
        nxt = db.scalar(select(ModelConfig).order_by(ModelConfig.updated_time.desc()).limit(1))
        if nxt:
            nxt.is_default = True
            db.commit()


def set_default(db: Session, model_id: str) -> ModelConfig:
    item = get_model(db, model_id)
    _clear_default(db)
    item.is_default = True
    item.is_active = True
    db.commit()
    db.refresh(item)
    return item


async def run_test(db: Session, payload: ModelTestRequest) -> ModelTestResult:
    endpoint: ModelEndpoint
    saved: ModelConfig | None = None

    if payload.id:
        saved = get_model(db, payload.id)
        endpoint = ModelEndpoint.from_config(saved)
        # 允许用请求体临时覆盖 key（测新 key）
        if payload.api_key and not _is_masked_secret(payload.api_key, saved.api_key):
            endpoint.api_key = payload.api_key
        if payload.extra_config is not None:
            endpoint.extra_config = _merge_extra_config(saved.extra_config, payload.extra_config)
        if payload.base_url is not None:
            endpoint.base_url = payload.base_url.strip() or endpoint.base_url
        if payload.model_name:
            endpoint.model_name = payload.model_name
        if payload.temperature is not None:
            endpoint.temperature = float(payload.temperature)
        if payload.max_tokens is not None:
            endpoint.max_tokens = int(payload.max_tokens)
    else:
        if not payload.provider or not payload.model_name:
            raise ValidationError("测试草稿时必须提供 provider 与 model_name")
        from app.nexusmind.models.model_config import PROVIDER_DEFAULT_BASE_URL

        base = (payload.base_url or "").strip() or PROVIDER_DEFAULT_BASE_URL.get(payload.provider, "")
        endpoint = ModelEndpoint(
            provider=payload.provider,
            api_key=payload.api_key or "",
            base_url=base,
            model_name=payload.model_name,
            temperature=float(payload.temperature or 0.2),
            max_tokens=int(payload.max_tokens or 64),
            extra_config=payload.extra_config or {},
        )

    try:
        result = await test_connection(endpoint)
        ok = True
        message = f"连接成功（{result.latency_ms} ms）"
        preview = result.content[:200]
    except Exception as exc:  # noqa: BLE001 - 测试接口需要吞掉并回传
        ok = False
        message = str(exc)
        preview = None
        result_latency = 0
    else:
        result_latency = result.latency_ms

    if saved is not None:
        saved.last_tested_at = utcnow()
        saved.last_test_ok = ok
        saved.last_test_message = message[:500]
        db.commit()

    return ModelTestResult(
        ok=ok,
        message=message,
        latency_ms=result_latency if ok else 0,
        reply_preview=preview,
    )
