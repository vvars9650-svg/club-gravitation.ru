"""Trusted local Pillow codec for private participant photos."""

from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

from .domain import DomainError


MAX_IMAGE_PIXELS = 40_000_000
MAX_IMAGE_EDGE = 12_000
_FORMATS = {"JPEG": "jpeg", "PNG": "png", "WEBP": "webp"}


class PillowPhotoCodec:
    def normalize(self, source):
        try:
            with Image.open(BytesIO(source)) as opened:
                detected = _FORMATS.get(str(opened.format or "").upper())
                if not detected:
                    raise DomainError("unsupported_photo_format")
                if getattr(opened, "n_frames", 1) != 1 or getattr(opened, "is_animated", False):
                    raise DomainError("unsupported_photo_format")
                width, height = opened.size
                if (
                    width < 1 or height < 1
                    or width > MAX_IMAGE_EDGE or height > MAX_IMAGE_EDGE
                    or width * height > MAX_IMAGE_PIXELS
                ):
                    raise DomainError("photo_dimensions_too_large")
                opened.load()
                oriented = ImageOps.exif_transpose(opened)
                mode = "RGB" if detected == "jpeg" else ("RGBA" if "A" in oriented.getbands() else "RGB")
                converted = oriented.convert(mode)
                clean = Image.new(mode, converted.size)
                clean.paste(converted)

                output = BytesIO()
                options = {
                    "jpeg": {"format": "JPEG", "quality": 90, "optimize": True},
                    "png": {"format": "PNG", "optimize": True},
                    "webp": {"format": "WEBP", "quality": 90, "method": 4},
                }[detected]
                clean.save(output, **options)
        except DomainError:
            raise
        except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
            raise ValueError("invalid_photo") from exc
        mime = {"jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}[detected]
        return output.getvalue(), {
            "format": detected,
            "mime_type": mime,
            "metadata_stripped": True,
        }
