import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))
MODULE_PATH = SRC_DIR / "index_v3_release.py"
SPEC = importlib.util.spec_from_file_location("gravitation_index_v3_release", MODULE_PATH)
backend = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(backend)


class DummyContext:
    request_id = "req-release-123"


class ParticipantResolutionTest(unittest.TestCase):
    @patch.object(backend, "find_secondary_contact_owners", return_value=set())
    @patch.object(backend, "find_phone_owner", return_value="GR-EXISTING")
    def test_phone_owner_is_reused(self, _phone, _secondary):
        self.assertEqual(
            backend.resolve_participant("+79991234567", "", ""),
            "GR-EXISTING",
        )

    @patch.object(
        backend,
        "find_secondary_contact_owners",
        return_value={"GR-OTHER"},
    )
    @patch.object(backend, "find_phone_owner", return_value="GR-EXISTING")
    def test_foreign_secondary_contact_is_conflict(self, _phone, _secondary):
        with self.assertRaises(backend.core.ParticipantConflictError):
            backend.resolve_participant(
                "+79991234567",
                "same@example.com",
                "",
            )

    @patch.object(
        backend,
        "find_secondary_contact_owners",
        return_value={"GR-EXISTING"},
    )
    @patch.object(backend, "find_phone_owner", return_value=None)
    def test_new_phone_matching_existing_email_requires_review(self, _phone, _secondary):
        with self.assertRaises(backend.core.ParticipantConflictError):
            backend.resolve_participant(
                "+79991234567",
                "known@example.com",
                "",
            )

    @patch.object(backend, "find_secondary_contact_owners", return_value=set())
    @patch.object(backend, "find_phone_owner", return_value=None)
    def test_new_contacts_create_new_participant(self, _phone, _secondary):
        self.assertIsNone(
            backend.resolve_participant(
                "+79991234567",
                "new@example.com",
                "@new",
            )
        )


class IdempotencyTest(unittest.TestCase):
    def test_replay_result_accepts_same_fingerprint(self):
        existing = {
            "participant_id": "GR-1",
            "raw_payload": json.dumps({"idempotency_fingerprint": "abc"}),
        }
        result = backend._replay_result(existing, "APP-1", "FILE-1", "abc")
        self.assertTrue(result["idempotent_replay"])
        self.assertEqual(result["participant_id"], "GR-1")

    def test_replay_result_rejects_changed_payload(self):
        existing = {
            "participant_id": "GR-1",
            "raw_payload": json.dumps({"idempotency_fingerprint": "abc"}),
        }
        with self.assertRaises(backend.core.IdempotencyConflictError):
            backend._replay_result(existing, "APP-1", "FILE-1", "xyz")


class PhotoPathTest(unittest.TestCase):
    @patch.object(backend.requests, "put")
    @patch.object(backend.core, "disk_api_request")
    def test_photo_path_depends_on_application_and_fingerprint(self, disk_request, put):
        disk_request.return_value.json.return_value = {"href": "https://upload.example/test"}
        put.return_value.raise_for_status.return_value = None

        path = backend.upload_photo_to_disk(
            b"photo",
            "APP-123",
            "abcdef0123456789deadbeef",
            ".jpg",
        )

        self.assertTrue(path.endswith("/APP-123-abcdef0123456789.jpg"))
        params = disk_request.call_args.kwargs["params"]
        self.assertEqual(params["path"], path)
        self.assertEqual(params["overwrite"], "true")


class HandlerTest(unittest.TestCase):
    def _event(self, body, key="abcDEF1234567890"):
        return {
            "httpMethod": "POST",
            "headers": {
                "Content-Type": "application/json",
                "Idempotency-Key": key,
            },
            "body": json.dumps(body, ensure_ascii=False),
        }

    @patch.object(backend, "save_application")
    def test_success(self, save_application):
        save_application.return_value = {
            "participant_id": "GR-1",
            "application_id": "APP-1",
            "file_id": "FILE-1",
            "participant_reused": False,
            "idempotent_replay": False,
        }
        response = backend.handler(self._event({"full_name": "Test"}), DummyContext())
        payload = json.loads(response["body"])
        self.assertEqual(response["statusCode"], 201)
        self.assertTrue(payload["success"])
        self.assertEqual(payload["request_id"], "req-release-123")

    @patch.object(backend, "save_application")
    def test_replay_returns_200(self, save_application):
        save_application.return_value = {
            "participant_id": "GR-1",
            "application_id": "APP-1",
            "file_id": "FILE-1",
            "participant_reused": True,
            "idempotent_replay": True,
        }
        response = backend.handler(self._event({"full_name": "Test"}), DummyContext())
        self.assertEqual(response["statusCode"], 200)


if __name__ == "__main__":
    unittest.main()
