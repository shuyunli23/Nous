"""Text-to-image generation shared by the builtin tool and pack scripts.

Resolution order:
1. The provider assigned under Settings → models by purpose → image
2. Hugging Face Inference Providers via ``HF_TOKEN`` / ``IMAGE_*`` in ``.env``
3. OpenAI-compatible ``POST {base}/images/generations`` via ``IMAGE_*``
4. AWS Bedrock image models using the active Bedrock chat provider
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import os
import re
import uuid
from pathlib import Path
from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.agent.tools.export_urls import export_download_url, export_user_message

logger = get_logger(__name__)

_SIZE_MAP = {
    "1024x1024": (1024, 1024),
    "1024x1792": (1024, 1792),
    "1792x1024": (1792, 1024),
    "512x512": (512, 512),
}


def _exports_dir() -> Path:
    path = settings.resolve_path("./data/exports")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _safe_stem(hint: str | None, fallback: str = "image") -> str:
    raw = (hint or fallback).strip() or fallback
    return re.sub(r"[^\w\u4e00-\u9fff\-]+", "_", raw)[:40] or fallback


def _save_png(data: bytes, *, filename_hint: str | None) -> dict[str, Any]:
    export_dir = _exports_dir()
    file_id = uuid.uuid4().hex[:12]
    filename = f"{_safe_stem(filename_hint)}_{file_id}.png"
    path = export_dir / filename
    path.write_bytes(data)
    url = export_download_url(filename)
    from app.agent.artifacts import attach_inspect

    return attach_inspect(
        {
            "ok": True,
            "filename": filename,
            "path": str(path),
            "download_url": url,
            "mime_type": "image/png",
            "message": export_user_message(
                kind="Image",
                title=filename,
                download_url=url,
            ),
            "download_hint": (
                "Paste download_url as a markdown relative link. "
                "Never convert it to http://127.0.0.1 or http://localhost."
            ),
        }
    )


def _routed_image_record():
    """Saved provider assigned to the image purpose, if any."""
    from app.core.exceptions import NotFoundError
    from app.llm.provider_store import get_provider_store
    from app.llm.providers import IMAGE_CAPABLE_KINDS

    store = get_provider_store()
    provider_id = store.route_for("image")
    if not provider_id:
        return None
    try:
        record = store.get(provider_id)
    except NotFoundError:
        return None
    if record.kind not in IMAGE_CAPABLE_KINDS:
        return None
    return record


def _image_provider_kind() -> str:
    return (
        (settings.image_provider or "").strip()
        or (os.environ.get("IMAGE_PROVIDER") or "").strip()
        or "auto"
    ).lower()


def _image_api_key() -> str:
    return (
        (settings.image_api_key or "").strip()
        or (os.environ.get("IMAGE_API_KEY") or "").strip()
        or (os.environ.get("OPENAI_API_KEY") or "").strip()
        or (settings.embedding_api_key or "").strip()
    )


def _hf_token() -> str:
    keyed = (settings.image_api_key or "").strip() or (
        os.environ.get("IMAGE_API_KEY") or ""
    ).strip()
    if keyed.startswith("hf_"):
        return keyed
    return (
        (settings.hf_token or "").strip()
        or (os.environ.get("HF_TOKEN") or "").strip()
        or (os.environ.get("HUGGING_FACE_HUB_TOKEN") or "").strip()
        or keyed
    )


def _hf_image_config() -> tuple[str, str, str] | None:
    """Return (api_key, hf_provider, model) when Hugging Face / fal-ai should run."""
    record = _routed_image_record()
    if record is not None:
        if record.kind != "huggingface_image":
            return None
        key = (record.api_key or "").strip() or _hf_token()
        if not key:
            return None
        return (
            key,
            (record.hf_provider or "fal-ai").strip() or "fal-ai",
            record.model,
        )
    kind = _image_provider_kind()
    key = _hf_token()
    hf_provider = (
        (settings.image_hf_provider or "").strip()
        or (os.environ.get("IMAGE_HF_PROVIDER") or "").strip()
        or "fal-ai"
    )
    model = (
        (settings.image_model or "").strip()
        or (os.environ.get("IMAGE_MODEL") or "").strip()
    )
    if not model or model.lower().startswith("dall-e"):
        model = "black-forest-labs/FLUX.1-dev"
    if kind in {"huggingface", "hf", "fal-ai", "fal"}:
        if not key:
            return None
        return key, hf_provider, model
    if kind not in {"auto", ""}:
        return None
    looks_hf = bool(
        (key.startswith("hf_") if key else False)
        or (settings.hf_token or "").strip()
        or (os.environ.get("HF_TOKEN") or "").strip()
        or (os.environ.get("IMAGE_HF_PROVIDER") or "").strip()
        or "/" in ((settings.image_model or os.environ.get("IMAGE_MODEL") or "").strip())
    )
    if looks_hf and key:
        return key, hf_provider, model
    return None


def _openai_image_config() -> tuple[str, str, str] | None:
    """Return (base_url, api_key, model) or None if not configured."""
    record = _routed_image_record()
    if record is not None:
        if record.kind != "openai_compatible":
            return None
        key = (record.api_key or "").strip() or _image_api_key()
        if not key or key.startswith("hf_"):
            return None
        base = (record.base_url or "https://api.openai.com/v1").rstrip("/")
        return base, key, record.model or "dall-e-3"
    if _image_provider_kind() in {"huggingface", "hf", "fal-ai", "fal", "bedrock"}:
        return None
    key = _image_api_key()
    if not key or key.startswith("hf_"):
        return None
    base = (
        (settings.image_api_base_url or "").strip()
        or (os.environ.get("IMAGE_API_BASE") or "").strip()
        or (settings.embedding_base_url or "").strip()
        or "https://api.openai.com/v1"
    ).rstrip("/")
    model = (
        (settings.image_model or "").strip()
        or (os.environ.get("IMAGE_MODEL") or "").strip()
        or "dall-e-3"
    )
    return base, key, model


def _pil_to_png_bytes(image: Any) -> bytes:
    from PIL import Image

    if isinstance(image, (bytes, bytearray)):
        return bytes(image)
    if isinstance(image, Image.Image):
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        return buf.getvalue()
    raise TypeError(f"Unexpected image type: {type(image)!r}")


async def _generate_huggingface(
    *,
    prompt: str,
    size: str,
    filename_hint: str | None,
) -> dict[str, Any]:
    cfg = _hf_image_config()
    if cfg is None:
        return {
            "ok": False,
            "error": (
                "Hugging Face image generation is selected but no token was found. "
                "Set HF_TOKEN in .env, or add a Hugging Face image provider in "
                "设置 → 新增供应商 and pick it under 按用途选用模型 → 文生图."
            ),
        }
    key, provider, model = cfg
    width, height = _SIZE_MAP.get(size, (1024, 1024))
    timeout = settings.image_timeout_seconds

    def _run() -> bytes:
        from huggingface_hub import InferenceClient

        client = InferenceClient(provider=provider, api_key=key, timeout=timeout)
        image = client.text_to_image(
            prompt,
            model=model,
            width=width,
            height=height,
        )
        return _pil_to_png_bytes(image)

    try:
        raw = await asyncio.wait_for(asyncio.to_thread(_run), timeout=timeout + 15)
    except Exception as exc:  # noqa: BLE001
        logger.warning("hf_image_failed", error=str(exc), provider=provider, model=model)
        return {
            "ok": False,
            "error": (
                f"Hugging Face ({provider}) image generation failed: {exc}. "
                "Check HF_TOKEN billing/permissions for this model."
            ),
        }
    return {
        **_save_png(raw, filename_hint=filename_hint),
        "provider": f"huggingface:{provider}",
        "model": model,
        "prompt": prompt[:200],
    }


async def _generate_openai_compatible(
    *,
    prompt: str,
    size: str,
    filename_hint: str | None,
) -> dict[str, Any]:
    cfg = _openai_image_config()
    if cfg is None:
        return {"ok": False, "error": "No IMAGE_API_KEY / OPENAI_API_KEY configured."}
    base, key, model = cfg
    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "size": size if size in _SIZE_MAP else "1024x1024",
        "n": 1,
        "response_format": "b64_json",
    }
    async with httpx.AsyncClient(timeout=settings.image_timeout_seconds) as client:
        try:
            resp = await client.post(
                f"{base}/images/generations",
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"Image API request failed: {exc}"}

    if resp.status_code >= 400:
        return {
            "ok": False,
            "error": f"Image API HTTP {resp.status_code}: {resp.text[:500]}",
        }
    try:
        data = resp.json()
        b64 = data["data"][0]["b64_json"]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        # Some providers return a URL instead of b64
        try:
            url = data["data"][0]["url"]  # type: ignore[index]
        except Exception:  # noqa: BLE001
            return {"ok": False, "error": f"Unexpected image API response: {exc}"}
        async with httpx.AsyncClient(timeout=60.0) as client:
            img = await client.get(url)
            img.raise_for_status()
            return {
                **_save_png(img.content, filename_hint=filename_hint),
                "provider": "openai_compatible",
                "model": model,
                "prompt": prompt[:200],
            }
    raw = base64.b64decode(b64)
    return {
        **_save_png(raw, filename_hint=filename_hint),
        "provider": "openai_compatible",
        "model": model,
        "prompt": prompt[:200],
    }


def _bedrock_size(size: str) -> tuple[int, int]:
    return _SIZE_MAP.get(size, (1024, 1024))


def _bedrock_image_model_candidates(active_chat_model: str | None) -> list[str]:
    """Build an ordered list of Bedrock image model IDs to try."""
    explicit = (
        (settings.image_bedrock_model or "").strip()
        or (os.environ.get("IMAGE_BEDROCK_MODEL") or "").strip()
    )
    bases = [
        "amazon.nova-canvas-v1:0",
        "amazon.titan-image-generator-v2:0",
        "amazon.titan-image-generator-v1",
    ]
    out: list[str] = []
    if explicit:
        out.append(explicit)

    prefix = ""
    model = (active_chat_model or "").strip()
    if "." in model:
        head = model.split(".", 1)[0]
        # Cross-region inference profile prefixes: us / eu / apac / …
        if head in {"us", "eu", "apac", "jp", "au", "ca", "global"}:
            prefix = f"{head}."

    for base in bases:
        if prefix:
            out.append(f"{prefix}{base}")
        out.append(base)

    # Dedup preserve order
    seen: set[str] = set()
    uniq: list[str] = []
    for m in out:
        if m not in seen:
            seen.add(m)
            uniq.append(m)
    return uniq


async def _generate_bedrock(
    *,
    prompt: str,
    size: str,
    filename_hint: str | None,
) -> dict[str, Any]:
    from app.llm.bedrock import _get_client  # noqa: PLC2701
    from app.llm.provider_store import resolve_from_record, resolve_llm
    from app.llm.usage import current_usage_meta

    routed = _routed_image_record()
    if routed is not None and routed.kind == "bedrock":
        llm = resolve_from_record(routed)
    else:
        meta = current_usage_meta()
        llm = resolve_llm(purpose=meta.purpose, provider_id=meta.provider_id)
    if llm.kind != "bedrock":
        return {
            "ok": False,
            "error": (
                "No image provider is configured. Add FLUX / OpenAI / Bedrock under "
                "设置 → 新增供应商, then pick it in 按用途选用模型 → 文生图, "
                "or set HF_TOKEN in .env."
            ),
        }

    width, height = _bedrock_size(size if size in _SIZE_MAP else "1024x1024")
    client = await _get_client(llm)
    candidates = _bedrock_image_model_candidates(llm.model)
    errors: list[str] = []

    for model_id in candidates:
        if "titan-image" in model_id:
            body: dict[str, Any] = {
                "taskType": "TEXT_IMAGE",
                "textToImageParams": {"text": prompt},
                "imageGenerationConfig": {
                    "numberOfImages": 1,
                    "height": height,
                    "width": width,
                    "cfgScale": 8.0,
                },
            }
        else:
            body = {
                "taskType": "TEXT_IMAGE",
                "textToImageParams": {"text": prompt},
                "imageGenerationConfig": {
                    "numberOfImages": 1,
                    "height": height,
                    "width": width,
                    "cfgScale": 6.5,
                    "quality": "standard",
                },
            }

        def _invoke(mid: str = model_id, payload: dict[str, Any] = body) -> dict[str, Any]:
            resp = client.invoke_model(
                modelId=mid,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(payload),
            )
            raw = resp["body"].read()
            return json.loads(raw)

        try:
            import asyncio

            payload = await asyncio.to_thread(_invoke)
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)
            logger.warning("bedrock_image_failed", error=msg, model=model_id)
            errors.append(f"{model_id}: {msg}")
            # Try next candidate on invalid model / access denied
            if any(
                token in msg.lower()
                for token in ("invalid", "access denied", "not authorized", "isn't supported")
            ):
                continue
            break

        b64 = None
        if isinstance(payload.get("images"), list) and payload["images"]:
            first = payload["images"][0]
            b64 = first if isinstance(first, str) else first.get("base64") or first.get("body")
        elif isinstance(payload.get("artifacts"), list) and payload["artifacts"]:
            b64 = payload["artifacts"][0].get("base64")
        if not b64:
            errors.append(f"{model_id}: unexpected response keys {list(payload)[:12]}")
            continue

        raw = base64.b64decode(b64)
        return {
            **_save_png(raw, filename_hint=filename_hint),
            "provider": "bedrock",
            "model": model_id,
            "prompt": prompt[:200],
        }

    return {
        "ok": False,
        "error": (
            "Bedrock image generation failed for all candidate models. "
            "Enable Nova Canvas / Titan Image in this region, set "
            "IMAGE_BEDROCK_MODEL to a valid id, or configure IMAGE_API_KEY. "
            f"Tried: {'; '.join(candidates)}. Details: {' | '.join(errors[:4])}"
        ),
    }


async def generate_image(
    *,
    prompt: str,
    size: str = "1024x1024",
    filename_hint: str | None = None,
) -> dict[str, Any]:
    """Generate an image and write a PNG under ``data/exports``."""
    text = (prompt or "").strip()
    if not text:
        return {"ok": False, "error": "prompt is required"}
    if len(text) > 4000:
        text = text[:4000]

    size_norm = (size or "1024x1024").strip()
    if size_norm not in _SIZE_MAP:
        size_norm = "1024x1024"

    routed = _routed_image_record()
    if routed is not None:
        if routed.kind == "huggingface_image":
            return await _generate_huggingface(
                prompt=text, size=size_norm, filename_hint=filename_hint
            )
        if routed.kind == "openai_compatible":
            return await _generate_openai_compatible(
                prompt=text, size=size_norm, filename_hint=filename_hint
            )
        if routed.kind == "bedrock":
            return await _generate_bedrock(
                prompt=text, size=size_norm, filename_hint=filename_hint
            )

    kind = _image_provider_kind()
    if kind in {"huggingface", "hf", "fal-ai", "fal"} or _hf_image_config() is not None:
        return await _generate_huggingface(
            prompt=text, size=size_norm, filename_hint=filename_hint
        )
    if _openai_image_config() is not None:
        return await _generate_openai_compatible(
            prompt=text, size=size_norm, filename_hint=filename_hint
        )
    return await _generate_bedrock(
        prompt=text, size=size_norm, filename_hint=filename_hint
    )
