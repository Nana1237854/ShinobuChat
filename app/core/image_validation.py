import io
import logging

from app.core.config import settings
from app.core.exceptions import BadRequestError, PayloadTooLargeError

logger = logging.getLogger(__name__)

# Map Pillow format names to MIME types for whitelist validation
_FORMAT_TO_MIME: dict[str, str] = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "GIF": "image/gif",
    "WEBP": "image/webp",
    "BMP": "image/bmp",
    "TIFF": "image/tiff",
}

ALLOWED_FORMATS: set[str] = set(_FORMAT_TO_MIME.keys())


def validate_image_bytes(
    data: bytes,
    max_bytes: int | None = None,
    max_side: int | None = None,
    max_pixels: int | None = None,
    max_output_bytes: int | None = None,
) -> tuple[bytes, str]:
    """Validate raw image bytes and return (sanitized_bytes, mime_type).

    Raises BadRequestError for empty/invalid/oversized images.
    Re-encodes to RGB JPEG, clamped to max dimensions.
    """
    if max_bytes is None:
        max_bytes = settings.image_max_input_bytes
    if max_side is None:
        max_side = settings.image_max_side
    if max_pixels is None:
        max_pixels = settings.image_max_pixels
    if max_output_bytes is None:
        max_output_bytes = settings.image_max_output_bytes

    if not data:
        raise BadRequestError("Image file is empty")

    if len(data) > max_bytes:
        raise PayloadTooLargeError(
            f"Image too large: {len(data)} bytes exceeds {max_bytes} bytes limit"
        )

    try:
        from PIL import Image

        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception:
        raise BadRequestError("Unrecognized image format")

    # Validate format against whitelist
    fmt = getattr(img, "format", None)
    if fmt is None or fmt.upper() not in ALLOWED_FORMATS:
        raise BadRequestError(
            f"Unsupported image format: {fmt or 'unknown'}. "
            f"Allowed: {', '.join(sorted(ALLOWED_FORMATS))}"
        )

    # Validate dimensions
    w, h = img.size
    if w > max_side or h > max_side:
        raise BadRequestError(
            f"Image dimensions ({w}x{h}) exceed maximum side length ({max_side}px)"
        )
    if w * h > max_pixels:
        raise BadRequestError(
            f"Image pixel count ({w * h}) exceeds limit ({max_pixels})"
        )

    # Clamp dimensions
    if w > max_side or h > max_side:
        ratio = min(max_side / w, max_side / h)
        new_w, new_h = int(w * ratio), int(h * ratio)
        img = img.resize((new_w, new_h), Image.LANCZOS)

    # Re-encode as RGB JPEG for consistent downstream handling
    if img.mode in ("RGBA", "P", "LA"):
        background = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        background.paste(
            img, mask=img.split()[-1] if img.mode == "RGBA" else None
        )
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    output = buf.getvalue()

    if len(output) > max_output_bytes:
        raise PayloadTooLargeError(
            f"Re-encoded image too large: {len(output)} bytes exceeds "
            f"{max_output_bytes} bytes output limit"
        )

    return output, "image/jpeg"
