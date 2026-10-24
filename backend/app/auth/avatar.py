"""Validate and strip metadata from an owner-uploaded profile photo."""

from __future__ import annotations

from io import BytesIO
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError


MAX_UPLOAD_BYTES = 2 * 1024 * 1024
MAX_PIXELS = 16_000_000
MAX_EDGE = 512
ALLOWED_FORMATS = frozenset({"JPEG", "PNG", "WEBP"})


class InvalidAvatar(ValueError):
    pass


def prepare_avatar(data: bytes) -> bytes:
    """Produce a small, non-animated JPEG with no EXIF or other metadata."""

    if not data or len(data) > MAX_UPLOAD_BYTES:
        raise InvalidAvatar("Choose a JPG, PNG or WebP photo smaller than 2 MB.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                if image.format not in ALLOWED_FORMATS or getattr(image, "n_frames", 1) != 1:
                    raise InvalidAvatar("Choose one JPG, PNG or WebP photo.")
                if image.width * image.height > MAX_PIXELS:
                    raise InvalidAvatar("Choose a photo smaller than 16 megapixels.")
                image.load()
                oriented = ImageOps.exif_transpose(image)
                oriented.thumbnail((MAX_EDGE, MAX_EDGE), Image.Resampling.LANCZOS)
                rgb = Image.new("RGB", oriented.size, "white")
                if oriented.mode in {"RGBA", "LA"}:
                    rgb.paste(oriented.convert("RGBA"), mask=oriented.convert("RGBA").getchannel("A"))
                else:
                    rgb.paste(oriented.convert("RGB"))
                output = BytesIO()
                rgb.save(output, format="JPEG", quality=85, optimize=True)
                return output.getvalue()
    except InvalidAvatar:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError,
            Image.DecompressionBombWarning) as error:
        raise InvalidAvatar("That file is not a valid JPG, PNG or WebP photo.") from error
