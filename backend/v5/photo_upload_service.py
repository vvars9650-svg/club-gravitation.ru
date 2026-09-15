"""PENDING_UPLOAD -> normalized private object -> READY orchestration."""

import hashlib
import secrets

from .domain import DomainError
from .object_storage import ObjectNotFound, ObjectStorageError, PRESIGN_TTL_SECONDS
from .photo_contract import MAX_PHOTO_BYTES, normalize_photo, validate_photo_object_id
from .repository import RepositoryConflict


def owner_context_hash(upload_context):
    if not upload_context:
        raise DomainError("idempotency_key_required", 400)
    return hashlib.sha256(str(upload_context).encode("utf-8")).hexdigest()


def new_photo_object_id():
    return "PHOTO-" + secrets.token_urlsafe(24)


class PhotoUploadService:
    def __init__(self, repository, storage, presigner, codec, bucket):
        self.repository = repository
        self.storage = storage
        self.presigner = presigner
        self.codec = codec
        self.bucket = bucket

    def initiate(self, upload_context):
        context_hash = owner_context_hash(upload_context)
        for _ in range(3):
            photo_object_id = new_photo_object_id()
            storage_key = "photos/" + secrets.token_urlsafe(32)
            try:
                self.repository.create_photo_upload(
                    photo_object_id, storage_key, context_hash
                )
                break
            except RepositoryConflict:
                continue
        else:
            raise DomainError("photo_id_generation_failed", 503)
        try:
            upload_url = self.presigner.presign_put(
                self.bucket, storage_key, PRESIGN_TTL_SECONDS
            )
        except Exception:
            self.repository.reject_photo_upload(photo_object_id, "REJECTED_PRESIGN")
            raise
        return {
            "photo_object_id": photo_object_id,
            "upload_url": upload_url,
            "upload_method": "PUT",
            "expires_in": PRESIGN_TTL_SECONDS,
        }

    def complete(self, photo_object_id, upload_context):
        photo_object_id = validate_photo_object_id(photo_object_id)
        context_hash = owner_context_hash(upload_context)
        photo = self.repository.get_photo_upload(photo_object_id)
        if not photo:
            raise DomainError("photo_upload_not_found", 404)
        if photo["owner_context_hash"] != context_hash:
            raise DomainError("photo_upload_not_owned", 403)
        if photo["lifecycle_state"] == "READY":
            return self._public_metadata(photo)
        if photo["lifecycle_state"] != "PENDING_UPLOAD":
            raise DomainError("photo_upload_not_completable", 409)

        storage_key = photo["storage_key"]
        try:
            size = self.storage.head(storage_key)["byte_size"]
        except ObjectNotFound as exc:
            raise DomainError("photo_object_missing", 422) from exc
        if size > MAX_PHOTO_BYTES:
            self._reject_and_delete(photo_object_id, storage_key, "REJECTED_TOO_LARGE")
            raise DomainError("photo_too_large")
        try:
            source = self.storage.get(storage_key, MAX_PHOTO_BYTES)
            normalized, metadata = normalize_photo(source, self.codec)
            if len(normalized) > MAX_PHOTO_BYTES:
                raise DomainError("photo_too_large")
            self.storage.put(storage_key, normalized, metadata["mime_type"])
            ready = self.repository.mark_photo_ready(photo_object_id, context_hash, metadata)
            return self._public_metadata(ready)
        except DomainError as exc:
            self._reject_and_delete(photo_object_id, storage_key, "REJECTED_" + exc.code.upper())
            raise
        except ObjectStorageError as exc:
            if str(exc) == "object_exceeded_read_limit":
                self._reject_and_delete(photo_object_id, storage_key, "REJECTED_TOO_LARGE")
                raise DomainError("photo_too_large") from exc
            raise

    def _reject_and_delete(self, photo_object_id, storage_key, status):
        cleanup_ok = False
        try:
            cleanup_ok = bool(self.storage.delete(storage_key))
        except ObjectStorageError:
            cleanup_ok = False
        safe_status = status if cleanup_ok else "CLEANUP_FAILED"
        self.repository.reject_photo_upload(photo_object_id, safe_status)

    @staticmethod
    def _public_metadata(photo):
        return {
            "photo_object_id": photo["photo_object_id"],
            "detected_format": photo["detected_format"],
            "mime_type": photo["mime_type"],
            "byte_size": photo["byte_size"],
            "metadata_stripped": True,
            "lifecycle_state": "READY",
        }
