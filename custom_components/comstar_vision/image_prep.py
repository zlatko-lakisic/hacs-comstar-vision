"""Load and downscale local JPEGs for Reach multimodal payloads."""

from __future__ import annotations

import base64
import io
import logging
from pathlib import Path
from typing import Any

_LOGGER = logging.getLogger(__name__)

_MIME_BY_SUFFIX = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


def parse_image_file_field(raw: str | list[str] | None) -> list[str]:
    """Split blueprint ``image_file`` (newline-joined paths) into a path list."""
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(p).strip() for p in raw if str(p).strip()]
    text = str(raw).replace("\r\n", "\n").replace("\r", "\n")
    return [line.strip() for line in text.split("\n") if line.strip()]


def _downscale_jpeg_bytes(data: bytes, *, target_width: int, mime: str) -> tuple[bytes, str]:
    """Return JPEG bytes resized so the long edge is at most target_width."""
    if target_width <= 0:
        return data, mime
    try:
        from PIL import Image
    except ImportError:
        _LOGGER.warning("Pillow not available; sending original image bytes")
        return data, mime

    with Image.open(io.BytesIO(data)) as img:
        img = img.convert("RGB")
        w, h = img.size
        if max(w, h) <= target_width:
            out = io.BytesIO()
            img.save(out, format="JPEG", quality=90, optimize=True)
            return out.getvalue(), "image/jpeg"
        if w >= h:
            nw, nh = target_width, max(1, int(h * (target_width / w)))
        else:
            nh, nw = target_width, max(1, int(w * (target_width / h)))
        resized = img.resize((nw, nh), Image.Resampling.LANCZOS)
        out = io.BytesIO()
        resized.save(out, format="JPEG", quality=88, optimize=True)
        return out.getvalue(), "image/jpeg"


def load_images_for_reach(
    paths: list[str],
    *,
    target_width: int = 1280,
    max_images: int = 16,
) -> list[dict[str, Any]]:
    """Read local files into Reach ``images`` parts.

    Each item: ``{mimeType, dataBase64, name}``.
    """
    images: list[dict[str, Any]] = []
    for raw_path in paths[:max_images]:
        path = Path(raw_path)
        if not path.is_file():
            _LOGGER.warning("Skipping missing image: %s", path)
            continue
        try:
            data = path.read_bytes()
        except OSError as exc:
            _LOGGER.warning("Failed to read %s: %s", path, exc)
            continue
        if not data:
            continue
        mime = _MIME_BY_SUFFIX.get(path.suffix.lower(), "image/jpeg")
        data, mime = _downscale_jpeg_bytes(data, target_width=target_width, mime=mime)
        images.append(
            {
                "mimeType": mime,
                "dataBase64": base64.b64encode(data).decode("ascii"),
                "name": path.name,
            }
        )
    return images
