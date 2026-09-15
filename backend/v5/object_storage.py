"""Private Yandex Object Storage access using a runtime IAM token."""

import urllib.error
import urllib.parse
import urllib.request

from .repository import RepositoryUnavailable


STORAGE_ENDPOINT = "https://storage.yandexcloud.net"
PRESIGN_TTL_SECONDS = 300


class ObjectNotFound(Exception):
    pass


class ObjectStorageError(RuntimeError):
    pass


def runtime_iam_token(context):
    """Extract the invocation-scoped token without persisting or logging it."""
    token = getattr(context, "token", None)
    if isinstance(token, dict):
        token = token.get("access_token") or token.get("iam_token")
    elif token is not None and not isinstance(token, str):
        token = getattr(token, "access_token", None)
    if not isinstance(token, str) or not token.strip():
        raise RepositoryUnavailable("missing_runtime_iam_token")
    return token.strip()


class YandexObjectStorageClient:
    def __init__(self, bucket, iam_token, opener=None, endpoint=STORAGE_ENDPOINT):
        if not bucket:
            raise RepositoryUnavailable("missing_photo_bucket_configuration")
        if not iam_token:
            raise RepositoryUnavailable("missing_runtime_iam_token")
        self.bucket = bucket
        self._iam_token = iam_token
        self._opener = opener or urllib.request.urlopen
        self._endpoint = endpoint.rstrip("/")

    def _url(self, storage_key):
        key = urllib.parse.quote(storage_key, safe="/")
        bucket = urllib.parse.quote(self.bucket, safe="")
        return f"{self._endpoint}/{bucket}/{key}"

    def _request(self, method, storage_key, data=None, headers=None):
        request_headers = {
            "Authorization": "Bearer " + self._iam_token,
            **(headers or {}),
        }
        request = urllib.request.Request(
            self._url(storage_key), data=data, headers=request_headers, method=method
        )
        try:
            return self._opener(request, timeout=20)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise ObjectNotFound("object_not_found") from exc
            raise ObjectStorageError("object_storage_request_failed") from exc
        except (OSError, urllib.error.URLError) as exc:
            raise ObjectStorageError("object_storage_request_failed") from exc

    def head(self, storage_key):
        with self._request("HEAD", storage_key) as response:
            try:
                size = int(response.headers["Content-Length"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ObjectStorageError("object_size_unavailable") from exc
            return {"byte_size": size}

    def get(self, storage_key, max_bytes):
        with self._request("GET", storage_key) as response:
            data = response.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise ObjectStorageError("object_exceeded_read_limit")
        return data

    def put(self, storage_key, data, mime_type):
        with self._request(
            "PUT", storage_key, data=data,
            headers={"Content-Type": mime_type, "Content-Length": str(len(data))},
        ):
            return True

    def delete(self, storage_key):
        try:
            with self._request("DELETE", storage_key):
                return True
        except ObjectNotFound:
            return True


class YandexPresignClient:
    """Thin adapter around Yandex Cloud PresignService.Create."""

    def __init__(self, iam_token, sdk_factory=None):
        if not iam_token:
            raise RepositoryUnavailable("missing_runtime_iam_token")
        self._iam_token = iam_token
        self._sdk_factory = sdk_factory

    def presign_put(self, bucket, storage_key, expires_in=PRESIGN_TTL_SECONDS):
        if not bucket:
            raise RepositoryUnavailable("missing_photo_bucket_configuration")
        try:
            from yandex.cloud.storage.v1.presign_service_pb2 import PresignURLsRequest
            from yandex.cloud.storage.v1.presign_service_pb2_grpc import PresignServiceStub
            if self._sdk_factory is None:
                from yandexcloud import SDK
                sdk = SDK(iam_token=self._iam_token)
            else:
                sdk = self._sdk_factory(self._iam_token)
            client = sdk.client(PresignServiceStub)
            request = PresignURLsRequest(
                bucket_name=bucket,
                objects=[{"expires": expires_in, "name": storage_key, "method": "PUT"}],
            )
            response = client.Create(request)
            urls = list(response.urls)
        except Exception as exc:
            raise ObjectStorageError("photo_presign_failed") from exc
        if len(urls) != 1 or not urls[0]:
            raise ObjectStorageError("photo_presign_failed")
        return urls[0]
