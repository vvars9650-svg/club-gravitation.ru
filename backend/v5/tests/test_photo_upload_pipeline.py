import json
import unittest
from io import BytesIO

from PIL import Image

from backend.v5.domain import DomainError
from backend.v5.handler import handler
from backend.v5.image_codec import PillowPhotoCodec
from backend.v5.object_storage import (
    ObjectNotFound, YandexObjectStorageClient, YandexPresignClient,
    runtime_iam_token,
)
from backend.v5.photo_contract import MAX_PHOTO_BYTES, PHOTO_OBJECT_ID_PATTERN
from backend.v5.photo_upload_service import PhotoUploadService
from backend.v5.repository import FakeRepository


BUCKET = "private-test-bucket"
OWNER = "owner-idempotency-context"


def encoded_image(image_format, exif=False):
    mode = "RGBA" if image_format in ("PNG", "WEBP") else "RGB"
    image = Image.new(mode, (16, 12), (20, 40, 60, 128) if mode == "RGBA" else (20, 40, 60))
    output = BytesIO()
    options = {}
    if exif:
        metadata = Image.Exif()
        metadata[0x010F] = "PRIVATE-CAMERA"
        metadata[0x0112] = 6
        options["exif"] = metadata
    image.save(output, format=image_format, **options)
    return output.getvalue()


class FakePresigner:
    def __init__(self):
        self.calls = []

    def presign_put(self, bucket, storage_key, expires_in):
        self.calls.append((bucket, storage_key, expires_in))
        return "https://signed.example.test/opaque?signature=SECRET"


class FakeStorage:
    def __init__(self):
        self.objects = {}
        self.head_calls = []
        self.get_calls = []
        self.put_calls = []
        self.delete_calls = []
        self.reported_size = None
        self.cleanup_fails = False
        self.get_exceeds_limit = False

    def head(self, key):
        self.head_calls.append(key)
        if key not in self.objects:
            raise ObjectNotFound("object_not_found")
        return {"byte_size": self.reported_size if self.reported_size is not None else len(self.objects[key])}

    def get(self, key, max_bytes):
        self.get_calls.append((key, max_bytes))
        if self.get_exceeds_limit:
            from backend.v5.object_storage import ObjectStorageError
            raise ObjectStorageError("object_exceeded_read_limit")
        return self.objects[key]

    def put(self, key, data, mime_type):
        self.put_calls.append((key, data, mime_type))
        self.objects[key] = data
        return True

    def delete(self, key):
        self.delete_calls.append(key)
        if self.cleanup_fails:
            from backend.v5.object_storage import ObjectStorageError
            raise ObjectStorageError("delete_failed")
        self.objects.pop(key, None)
        return True


class PhotoUploadPipelineTests(unittest.TestCase):
    def setUp(self):
        self.repo = FakeRepository()
        self.storage = FakeStorage()
        self.presigner = FakePresigner()
        self.service = PhotoUploadService(
            self.repo, self.storage, self.presigner, PillowPhotoCodec(), BUCKET
        )

    def initiate(self):
        result = self.service.initiate(OWNER)
        row = self.repo.photo_objects[result["photo_object_id"]]
        return result, row

    def test_initiate_requires_context_and_persists_only_hash_and_opaque_keys(self):
        with self.assertRaises(DomainError) as caught:
            self.service.initiate("")
        self.assertEqual(caught.exception.code, "idempotency_key_required")

        result, row = self.initiate()
        self.assertRegex(result["photo_object_id"], PHOTO_OBJECT_ID_PATTERN)
        self.assertEqual(row["lifecycle_state"], "PENDING_UPLOAD")
        self.assertEqual(len(row["owner_context_hash"]), 64)
        self.assertNotEqual(row["owner_context_hash"], OWNER)
        self.assertNotIn(OWNER, json.dumps(row))
        self.assertTrue(row["storage_key"].startswith("photos/"))
        self.assertNotIn(result["photo_object_id"], row["storage_key"])
        self.assertEqual((row["detected_format"], row["mime_type"], row["byte_size"]), ("", "", 0))
        self.assertEqual(result["upload_method"], "PUT")
        self.assertEqual(result["expires_in"], 300)
        self.assertEqual(self.presigner.calls, [(BUCKET, row["storage_key"], 300)])
        self.assertNotIn("owner_context_hash", result)
        self.assertNotIn("storage_key", result)

    def test_complete_unknown_foreign_and_missing_object_are_rejected(self):
        with self.assertRaises(DomainError) as unknown:
            self.service.complete("PHOTO-0000000000000001", OWNER)
        self.assertEqual(unknown.exception.code, "photo_upload_not_found")
        _, row = self.initiate()
        with self.assertRaises(DomainError) as foreign:
            self.service.complete(row["photo_object_id"], "foreign-context")
        self.assertEqual(foreign.exception.code, "photo_upload_not_owned")
        with self.assertRaises(DomainError) as missing:
            self.service.complete(row["photo_object_id"], OWNER)
        self.assertEqual(missing.exception.code, "photo_object_missing")

    def test_oversized_head_rejects_without_get_and_deletes(self):
        _, row = self.initiate()
        self.storage.objects[row["storage_key"]] = b"small-placeholder"
        self.storage.reported_size = MAX_PHOTO_BYTES + 1
        with self.assertRaises(DomainError) as caught:
            self.service.complete(row["photo_object_id"], OWNER)
        self.assertEqual(caught.exception.code, "photo_too_large")
        self.assertEqual(self.storage.get_calls, [])
        self.assertEqual(self.storage.delete_calls, [row["storage_key"]])
        self.assertEqual(self.repo.photo_objects[row["photo_object_id"]]["lifecycle_state"], "REJECTED_TOO_LARGE")

    def test_object_growing_after_head_is_still_rejected_and_deleted(self):
        _, row = self.initiate()
        self.storage.objects[row["storage_key"]] = b"small-at-head"
        self.storage.get_exceeds_limit = True
        with self.assertRaises(DomainError) as caught:
            self.service.complete(row["photo_object_id"], OWNER)
        self.assertEqual(caught.exception.code, "photo_too_large")
        self.assertEqual(self.storage.delete_calls, [row["storage_key"]])
        self.assertEqual(self.repo.photo_objects[row["photo_object_id"]]["lifecycle_state"], "REJECTED_TOO_LARGE")

    def test_corrupt_and_unsupported_objects_are_deleted_and_not_ready(self):
        for raw, expected in ((b"not-an-image", "invalid_photo"), (encoded_image("GIF"), "unsupported_photo_format")):
            result, row = self.initiate()
            self.storage.objects[row["storage_key"]] = raw
            with self.assertRaises(DomainError) as caught:
                self.service.complete(result["photo_object_id"], OWNER)
            self.assertEqual(caught.exception.code, expected)
            self.assertNotEqual(self.repo.photo_objects[result["photo_object_id"]]["lifecycle_state"], "READY")
            self.assertIn(row["storage_key"], self.storage.delete_calls)

    def test_valid_formats_are_normalized_overwritten_ready_and_idempotent(self):
        for image_format, expected_format, mime in (
            ("JPEG", "jpeg", "image/jpeg"),
            ("PNG", "png", "image/png"),
            ("WEBP", "webp", "image/webp"),
        ):
            result, row = self.initiate()
            raw = encoded_image(image_format, exif=image_format == "JPEG")
            self.storage.objects[row["storage_key"]] = raw
            completed = self.service.complete(result["photo_object_id"], OWNER)
            normalized = self.storage.objects[row["storage_key"]]
            self.assertEqual(completed["detected_format"], expected_format)
            self.assertEqual(completed["mime_type"], mime)
            self.assertTrue(completed["metadata_stripped"])
            self.assertNotIn("storage_key", completed)
            self.assertNotIn("upload_url", completed)
            self.assertNotEqual(normalized, raw)
            with Image.open(BytesIO(normalized)) as image:
                self.assertFalse(image.getexif())
                self.assertNotIn("exif", image.info)
                image.load()
            puts_before = len(self.storage.put_calls)
            replay = self.service.complete(result["photo_object_id"], OWNER)
            self.assertEqual(replay, completed)
            self.assertEqual(len(self.storage.put_calls), puts_before)

    def test_cleanup_failure_is_visible_as_safe_status(self):
        result, row = self.initiate()
        self.storage.objects[row["storage_key"]] = b"corrupt"
        self.storage.cleanup_fails = True
        with self.assertRaises(DomainError):
            self.service.complete(result["photo_object_id"], OWNER)
        self.assertEqual(self.repo.photo_objects[result["photo_object_id"]]["lifecycle_state"], "CLEANUP_FAILED")

    def test_handler_contract_does_not_echo_url_key_token_filename_or_binary(self):
        response = handler(
            {"httpMethod": "POST", "path": "/photo-uploads/initiate",
             "headers": {"Content-Type": "application/json", "Idempotency-Key": OWNER},
             "body": json.dumps({"original_filename": "private-name.jpg"})},
            repo=self.repo, photo_service=self.service,
        )
        self.assertEqual(response["statusCode"], 201)
        body = json.loads(response["body"])
        persisted = json.dumps(self.repo.photo_objects)
        self.assertNotIn("private-name", persisted)
        self.assertNotIn("BASE64-SECRET", persisted)
        self.assertNotIn(OWNER, persisted)
        self.assertNotIn("storage_key", body)
        rejected = handler(
            {"httpMethod": "POST", "path": "/photo-uploads/initiate",
             "headers": {"Content-Type": "application/json", "Idempotency-Key": OWNER},
             "body": json.dumps({"photo_data": "BASE64-SECRET"})},
            repo=self.repo, photo_service=self.service,
        )
        self.assertEqual(rejected["statusCode"], 400)
        self.assertNotIn("BASE64-SECRET", rejected["body"])


class PresignAdapterTests(unittest.TestCase):
    def test_presign_service_receives_exact_single_private_target_and_token_is_not_returned(self):
        captured = {}

        class Client:
            def Create(self, request):
                captured["request"] = request
                return type("Response", (), {"urls": ["https://signed.example.test/u"]})()

        class SDK:
            def client(self, stub):
                captured["stub"] = stub
                return Client()

        def sdk_factory(token):
            captured["token"] = token
            return SDK()

        adapter = YandexPresignClient("IAM-SECRET", sdk_factory=sdk_factory)
        url = adapter.presign_put("private-bucket", "photos/opaque", 300)
        request = captured["request"]
        self.assertEqual(request.bucket_name, "private-bucket")
        self.assertEqual(len(request.objects), 1)
        self.assertEqual(request.objects[0].name, "photos/opaque")
        self.assertEqual(request.objects[0].method, "PUT")
        self.assertEqual(request.objects[0].expires, 300)
        self.assertNotIn("IAM-SECRET", url)


class ObjectStorageAdapterTests(unittest.TestCase):
    def test_bearer_authenticated_head_get_put_delete_use_exact_object(self):
        requests = []

        class Response:
            headers = {"Content-Length": "3"}
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, amount): return b"raw"[:amount]

        def opener(request, timeout):
            requests.append((request, timeout))
            return Response()

        storage = YandexObjectStorageClient(
            "private-bucket", "IAM-SECRET", opener=opener
        )
        self.assertEqual(storage.head("photos/a b")["byte_size"], 3)
        self.assertEqual(storage.get("photos/a b", 10), b"raw")
        self.assertTrue(storage.put("photos/a b", b"new", "image/jpeg"))
        self.assertTrue(storage.delete("photos/a b"))
        self.assertEqual([item[0].method for item in requests], ["HEAD", "GET", "PUT", "DELETE"])
        for request, timeout in requests:
            self.assertEqual(request.full_url, "https://storage.yandexcloud.net/private-bucket/photos/a%20b")
            self.assertEqual(request.get_header("Authorization"), "Bearer IAM-SECRET")
            self.assertEqual(timeout, 20)

    def test_runtime_token_supports_function_context_shape_and_fails_closed(self):
        context = type("Context", (), {"token": {"access_token": "IAM-SECRET"}})()
        self.assertEqual(runtime_iam_token(context), "IAM-SECRET")
        with self.assertRaisesRegex(Exception, "missing_runtime_iam_token"):
            runtime_iam_token(object())


if __name__ == "__main__":
    unittest.main()
