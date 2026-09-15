import os
import threading

from .repository import RepositoryUnavailable


_runtime_repository_instance = None
_runtime_repository_lock = threading.Lock()


def runtime_repository():
    global _runtime_repository_instance

    if os.getenv("V5_REPOSITORY") == "fake":
        raise RepositoryUnavailable("fake_repository_for_tests_only")

    if _runtime_repository_instance is not None:
        return _runtime_repository_instance

    with _runtime_repository_lock:
        if _runtime_repository_instance is not None:
            return _runtime_repository_instance

        # Assign only after successful construction. Configuration or
        # connection failures must remain retryable on a later invocation.
        repository = _create_runtime_repository()
        _runtime_repository_instance = repository
        return repository


def _create_runtime_repository():
    from .ydb_repository import YdbRepository

    return YdbRepository()


def runtime_photo_upload_service(context, repository):
    """Build invocation-scoped clients so the IAM token is never cached."""
    from .image_codec import PillowPhotoCodec
    from .object_storage import (
        YandexObjectStorageClient,
        YandexPresignClient,
        runtime_iam_token,
    )
    from .photo_upload_service import PhotoUploadService

    bucket = os.getenv("V5_TEST_PHOTO_BUCKET")
    if not bucket:
        raise RepositoryUnavailable("missing_photo_bucket_configuration")
    token = runtime_iam_token(context)
    return PhotoUploadService(
        repository=repository,
        storage=YandexObjectStorageClient(bucket, token),
        presigner=YandexPresignClient(token),
        codec=PillowPhotoCodec(),
        bucket=bucket,
    )
