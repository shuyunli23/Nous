"""Crop an uploaded/exported image (resume 一寸照, page region, etc.)."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from app.agent.tools.export_urls import ascii_export_stem, export_download_url
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def _resolve_image_path(src: str) -> Path | None:
    raw = unquote((src or "").strip())
    if not raw:
        return None
    as_path = Path(raw)
    if as_path.is_file():
        return as_path
    path = urlparse(raw).path or raw
    name = Path(path).name
    if not name or name in {".", ".."} or "/" in name or "\\" in name:
        return None
    for folder in ("./data/uploads", "./data/exports"):
        candidate = settings.resolve_path(folder) / name
        if candidate.is_file():
            return candidate
    return None


def _box_from_preset(width: int, height: int, preset: str) -> tuple[int, int, int, int]:
    """Return a crop box (left, top, right, bottom)."""
    portrait = height >= width * 1.12
    already_headshot = portrait and width <= 900 and height / max(width, 1) <= 1.7
    if preset in {"portrait", "id_photo", "headshot"} and already_headshot:
        pad = int(min(width, height) * 0.02)
        return pad, pad, width - pad, height - pad
    # Chinese resume convention: 证件照 sits in the top-right.
    crop_w = max(80, int(width * 0.22))
    crop_h = max(100, int(crop_w * 1.35))
    if crop_h > int(height * 0.42):
        crop_h = int(height * 0.42)
        crop_w = max(80, int(crop_h / 1.35))
    margin_x = max(8, int(width * 0.035))
    margin_y = max(8, int(height * 0.03))
    left = max(0, width - crop_w - margin_x)
    top = margin_y
    return left, top, min(width, left + crop_w), min(height, top + crop_h)


async def crop_image(
    *,
    src: str,
    left: float | None = None,
    top: float | None = None,
    width: float | None = None,
    height: float | None = None,
    unit: str = "ratio",
    preset: str | None = "portrait",
    filename_hint: str | None = None,
) -> dict[str, Any]:
    """Crop a local upload/export image and return a new download_url."""
    path = _resolve_image_path(src)
    if path is None:
        return {
            "ok": False,
            "error": (
                "Could not find that image on disk. Pass a PAPER FIGURES / "
                "upload URL such as /api/v1/files/uploads/xxx_img41.png."
            ),
        }
    try:
        from PIL import Image
    except ImportError:
        return {"ok": False, "error": "Pillow is not installed; cannot crop."}

    try:
        image = Image.open(path)
        image.load()
        if image.mode not in {"RGB", "L"}:
            image = image.convert("RGB")
        img_w, img_h = image.size
        has_box = None not in (left, top, width, height)
        if has_box:
            unit_name = (unit or "ratio").lower()
            if unit_name in {"pixel", "px", "pixels"}:
                x0, y0 = int(left or 0), int(top or 0)
                x1 = x0 + int(width or 0)
                y1 = y0 + int(height or 0)
            else:
                x0 = int((left or 0) * img_w)
                y0 = int((top or 0) * img_h)
                x1 = int(((left or 0) + (width or 0)) * img_w)
                y1 = int(((top or 0) + (height or 0)) * img_h)
            box = (
                max(0, min(x0, x1)),
                max(0, min(y0, y1)),
                min(img_w, max(x0, x1)),
                min(img_h, max(y0, y1)),
            )
        else:
            box = _box_from_preset(img_w, img_h, (preset or "portrait").lower())
        if box[2] - box[0] < 16 or box[3] - box[1] < 16:
            return {"ok": False, "error": "Crop box is too small."}
        cropped = image.crop(box)
    except Exception as exc:  # noqa: BLE001
        logger.warning("crop_image_failed", error=str(exc), src=src)
        return {"ok": False, "error": f"Failed to crop image: {exc}"}

    export_dir = settings.resolve_path("./data/exports")
    export_dir.mkdir(parents=True, exist_ok=True)
    stem = ascii_export_stem(filename_hint or path.stem, fallback="portrait")
    filename = f"{stem}_{uuid.uuid4().hex[:10]}.png"
    out = export_dir / filename
    cropped.save(out, format="PNG")
    url = export_download_url(filename)
    from app.agent.artifacts import attach_inspect

    return attach_inspect(
        {
            "ok": True,
            "filename": filename,
            "path": str(out),
            "download_url": url,
            "width": cropped.size[0],
            "height": cropped.size[1],
            "source": path.name,
            "box": list(box),
            "message": (
                f"Cropped photo ready. download_url={url}. "
                "Pass this URL as create_webpage hero.image (cover portrait). "
                "Do not generate_image to fake a person's face."
            ),
        }
    )
