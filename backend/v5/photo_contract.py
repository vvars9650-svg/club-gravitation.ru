"""Phase A contract for protected photo validation and normalization."""

import re

from .domain import DomainError


PHOTO_REQUIRED_LEGAL_APPROVED = True
PROD_PHOTO_RKN_GATE_PENDING = True
MAX_PHOTO_BYTES = 10 * 1024 * 1024
ALLOWED_IMAGE_FORMATS = {
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
}
PHOTO_OBJECT_ID_PATTERN = re.compile(r"PHOTO-[A-Za-z0-9_-]{16,120}\Z")


def validate_photo_object_id(value):
    value = str(value or "").strip()
    if not value:
        raise DomainError("photo_required")
    if not PHOTO_OBJECT_ID_PATTERN.fullmatch(value):
        raise DomainError("invalid_photo_reference")
    return value


def normalize_photo(source, codec):
    """Decode and re-encode through a trusted local codec, stripping metadata.

    ``codec.normalize`` is the Phase B boundary. It must detect the actual format,
    fully decode pixels, discard metadata, and return newly encoded bytes plus
    ``format``, ``mime_type``, and ``metadata_stripped=True``. No face analysis is
    part of this interface.
    """
    if not isinstance(source, bytes) or not source:
        raise DomainError("invalid_photo")
    if len(source) > MAX_PHOTO_BYTES:
        raise DomainError("photo_too_large")
    try:
        normalized, details = codec.normalize(source)
    except Exception as exc:
        raise DomainError("invalid_photo") from exc
    if not isinstance(normalized, bytes) or not normalized:
        raise DomainError("invalid_photo")
    detected_format = str(details.get("format", "")).lower()
    detected_mime = str(details.get("mime_type", "")).lower()
    if ALLOWED_IMAGE_FORMATS.get(detected_format) != detected_mime:
        raise DomainError("unsupported_photo_format")
    if details.get("metadata_stripped") is not True:
        raise DomainError("photo_metadata_not_stripped")
    return normalized, {
        "detected_format": detected_format,
        "mime_type": detected_mime,
        "byte_size": len(normalized),
        "metadata_stripped": True,
    }
