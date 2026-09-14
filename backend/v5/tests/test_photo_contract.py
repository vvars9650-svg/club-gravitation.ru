import copy
import json
import unittest

from backend.v5.domain import DomainError
from backend.v5.photo_contract import MAX_PHOTO_BYTES, normalize_photo
from backend.v5.repository import FakeRepository, RepositoryConflict
from backend.v5.service import submit
from backend.v5.tests.test_v5 import P, payload_with_photo


class FakeCodec:
    def __init__(self, details=None, output=b"normalized-pixels"):
        self.details = details or {
            "format": "jpeg",
            "mime_type": "image/jpeg",
            "metadata_stripped": True,
        }
        self.output = output

    def normalize(self, source):
        return self.output, self.details


class PhotoContractTests(unittest.TestCase):
    def test_backend_rejects_missing_invalid_and_unowned_reference(self):
        repo = FakeRepository()
        with self.assertRaises(DomainError) as missing:
            submit({**P, "photo_object_id": ""}, "missing", repo, "request")
        self.assertEqual(missing.exception.code, "photo_required")
        with self.assertRaises(DomainError) as invalid:
            submit({**P, "photo_object_id": "PHOTO-short"}, "invalid", repo, "request")
        self.assertEqual(invalid.exception.code, "invalid_photo_reference")
        foreign = payload_with_photo(repo, "owner-key")
        with self.assertRaises(RepositoryConflict) as unowned:
            submit(foreign, "different-key", repo, "request")
        self.assertEqual(str(unowned.exception), "photo_reference_not_owned")

    def test_owned_photo_is_accepted_and_application_snapshot_is_immutable(self):
        repo = FakeRepository()
        payload = payload_with_photo(repo, "application-key")
        record, replay = submit(payload, "application-key", repo, "request")
        self.assertFalse(replay)
        original_photo = record["form"]["photo_object_id"]
        snapshot = copy.deepcopy(repo.by_key["application-key"])
        participant_id = record["participant_id"]
        replacement = "PHOTO-REPLACEMENT00000001"
        repo.register_photo_upload(replacement, "replace-context")
        result = repo.replace_participant_photo(participant_id, replacement, "replace-context")
        self.assertEqual(result["current_photo_object_id"], replacement)
        self.assertEqual(repo.participants[participant_id]["current_photo_object_id"], replacement)
        self.assertEqual(repo.by_key["application-key"], snapshot)
        self.assertEqual(repo.by_key["application-key"]["form"]["photo_object_id"], original_photo)

    def test_photo_only_delete_preserves_participant_and_application(self):
        repo = FakeRepository()
        payload = payload_with_photo(repo, "delete-key")
        record, _ = submit(payload, "delete-key", repo, "request")
        snapshot = copy.deepcopy(repo.by_key["delete-key"])
        result = repo.delete_current_photo(record["participant_id"])
        self.assertFalse(result["participation_deleted"])
        self.assertTrue(result["selection_blocked"])
        self.assertIn(record["participant_id"], repo.participants)
        self.assertEqual(repo.by_key["delete-key"], snapshot)
        self.assertEqual(repo.photo_objects[payload["photo_object_id"]]["lifecycle_state"], "DELETE_REQUESTED")
        self.assertEqual(repo.destruction_plan(record["participant_id"])["records"]["photo_objects"]["count"], 1)

    def test_approved_photo_delete_keeps_active_participation(self):
        repo = FakeRepository()
        payload = payload_with_photo(repo, "approved-delete")
        record, _ = submit(payload, "approved-delete", repo, "request")
        repo.participants[record["participant_id"]]["participant_status"] = "Одобрен"
        result = repo.delete_current_photo(record["participant_id"])
        self.assertFalse(result["selection_blocked"])
        self.assertEqual(repo.participants[record["participant_id"]]["participant_status"], "Одобрен")

    def test_normalization_requires_decode_reencode_metadata_strip_and_detected_format(self):
        normalized, details = normalize_photo(b"synthetic-image", FakeCodec())
        self.assertEqual(normalized, b"normalized-pixels")
        self.assertEqual(details["mime_type"], "image/jpeg")
        with self.assertRaises(DomainError) as metadata:
            normalize_photo(b"synthetic", FakeCodec({"format": "jpeg", "mime_type": "image/jpeg", "metadata_stripped": False}))
        self.assertEqual(metadata.exception.code, "photo_metadata_not_stripped")
        with self.assertRaises(DomainError) as blob:
            normalize_photo(b"arbitrary", FakeCodec({"format": "exe", "mime_type": "application/octet-stream", "metadata_stripped": True}))
        self.assertEqual(blob.exception.code, "unsupported_photo_format")
        with self.assertRaises(DomainError) as large:
            normalize_photo(b"x" * (MAX_PHOTO_BYTES + 1), FakeCodec())
        self.assertEqual(large.exception.code, "photo_too_large")

    def test_repository_metadata_and_logs_never_contain_binary_url_filename_or_exif(self):
        repo = FakeRepository()
        payload = payload_with_photo(repo, "privacy-key")
        submit(payload, "privacy-key", repo, "request")
        serialized = json.dumps({"photos": repo.photo_objects, "audit": repo.audit})
        for forbidden in ("base64", "presigned", "https://", "original_filename", "exif", "synthetic-image"):
            self.assertNotIn(forbidden, serialized.lower())


if __name__ == "__main__":
    unittest.main()
