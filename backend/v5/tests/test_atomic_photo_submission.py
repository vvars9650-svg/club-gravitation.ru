import copy
import hashlib
import json
import threading
import unittest

from backend.v5.domain import DomainError
from backend.v5.repository import FakeRepository, RepositoryConflict
from backend.v5.service import submit
from backend.v5.tests.test_v5 import P, payload_with_photo


class FailingSubmissionRepository(FakeRepository):
    def __init__(self, fail_stage):
        super().__init__()
        self.fail_stage = fail_stage

    def _submission_checkpoint(self, stage):
        if stage == self.fail_stage:
            raise RuntimeError("injected_" + stage)


class AtomicPhotoSubmissionTests(unittest.TestCase):
    def test_new_participant_application_and_photo_attach_atomically(self):
        repo = FakeRepository()
        key = "atomic-new"
        payload = payload_with_photo(repo, key)

        record, replay = submit(payload, key, repo, "request-new")
        photo = repo.photo_objects[payload["photo_object_id"]]
        participant = repo.participants[record["participant_id"]]

        self.assertFalse(replay)
        self.assertEqual(record["photo_object_id"], payload["photo_object_id"])
        self.assertEqual(repo.by_key[key]["photo_object_id"], payload["photo_object_id"])
        self.assertEqual(photo["lifecycle_state"], "ATTACHED")
        self.assertEqual(photo["application_id"], record["application_id"])
        self.assertEqual(photo["participant_id"], record["participant_id"])
        self.assertEqual(participant["current_photo_object_id"], payload["photo_object_id"])
        self.assertFalse(participant["photo_required_blocked"])

    def test_repeat_submission_keeps_original_application_and_photo(self):
        repo = FakeRepository()
        first_payload = payload_with_photo(repo, "atomic-first")
        first, _ = submit(first_payload, "atomic-first", repo, "request-first")
        first_snapshot = copy.deepcopy(repo.by_key["atomic-first"])

        second_payload = payload_with_photo(repo, "atomic-second")
        second, _ = submit(second_payload, "atomic-second", repo, "request-second")

        self.assertEqual(second["participant_id"], first["participant_id"])
        self.assertEqual(repo.by_key["atomic-first"]["form"], first_snapshot["form"])
        self.assertEqual(repo.by_key["atomic-first"]["photo_object_id"], first_payload["photo_object_id"])
        self.assertNotIn("atomic-second", repo.by_key)
        self.assertEqual(
            repo.participants[first["participant_id"]]["current_photo_object_id"],
            first_payload["photo_object_id"],
        )
        second_photo = repo.photo_objects[second_payload["photo_object_id"]]
        self.assertEqual(second_photo["lifecycle_state"], "DELETE_SCHEDULED")
        self.assertIsNone(second_photo["participant_id"])

    def test_repeat_submission_does_not_replace_deleted_current_photo(self):
        repo = FakeRepository()
        first_payload = payload_with_photo(repo, "atomic-delete-first")
        first, _ = submit(first_payload, "atomic-delete-first", repo, "request-first")
        repo.delete_current_photo(first["participant_id"])
        self.assertIsNone(repo.participants[first["participant_id"]]["current_photo_object_id"])

        second_payload = payload_with_photo(repo, "atomic-restore")
        submit(second_payload, "atomic-restore", repo, "request-second")

        participant = repo.participants[first["participant_id"]]
        self.assertIsNone(participant["current_photo_object_id"])
        self.assertTrue(participant["photo_required_blocked"])
        self.assertEqual(repo.photo_objects[second_payload["photo_object_id"]]["lifecycle_state"], "DELETE_SCHEDULED")
        self.assertEqual(repo.by_key["atomic-delete-first"]["photo_object_id"], first_payload["photo_object_id"])

    def test_rejected_photo_variants_write_no_submission_state(self):
        scenarios = (
            ("missing", None, "photo_reference_not_found"),
            ("foreign", {"owner_context_hash": "f" * 64}, "photo_reference_not_owned"),
            ("pending", {"lifecycle_state": "PENDING_UPLOAD"}, "photo_reference_not_available"),
            ("rejected", {"lifecycle_state": "REJECTED_INVALID_PHOTO"}, "photo_reference_not_available"),
            ("attached", {"lifecycle_state": "ATTACHED"}, "photo_reference_not_available"),
            ("application-set", {"application_id": "APP-OTHER"}, "photo_reference_not_available"),
            ("participant-set", {"participant_id": "PT-OTHER"}, "photo_reference_not_available"),
            ("wrong-environment", {"environment": "PROD"}, "photo_reference_not_available"),
        )
        for name, changes, expected in scenarios:
            with self.subTest(name=name):
                repo = FakeRepository()
                key = "reject-" + name
                photo_id = "PHOTO-" + hashlib.sha256(key.encode()).hexdigest()[:24]
                if changes is not None:
                    repo.register_photo_upload(photo_id, key)
                    repo.photo_objects[photo_id].update(changes)
                before = copy.deepcopy(repo.photo_objects)
                with self.assertRaisesRegex(RepositoryConflict, expected):
                    submit({**P, "photo_object_id": photo_id}, key, repo, "request")
                self.assertEqual(repo.photo_objects, before)
                self.assertEqual((repo.by_key, repo.by_phone, repo.participants, repo.audit), ({}, {}, {}, []))

        with self.assertRaises(DomainError) as malformed:
            submit({**P, "photo_object_id": "PHOTO-short"}, "malformed", FakeRepository(), "request")
        self.assertEqual(malformed.exception.code, "invalid_photo_reference")

    def test_idempotent_retry_after_commit_does_not_require_ready_photo(self):
        repo = FakeRepository()
        key = "atomic-replay"
        payload = payload_with_photo(repo, key)
        first, _ = submit(payload, key, repo, "request-first")
        self.assertEqual(repo.photo_objects[payload["photo_object_id"]]["lifecycle_state"], "ATTACHED")

        replay, replayed = submit(payload, key, repo, "request-retry")
        self.assertTrue(replayed)
        self.assertEqual(replay["application_id"], first["application_id"])
        self.assertEqual((len(repo.by_key), len(repo.participants), len(repo.audit)), (1, 1, 1))

        with self.assertRaises(DomainError) as conflict:
            submit({**payload, "occupation": "changed"}, key, repo, "request-conflict")
        self.assertEqual((conflict.exception.code, conflict.exception.status), ("idempotency_conflict", 409))

    def test_concurrent_same_key_commits_once_and_replays_once(self):
        repo = FakeRepository()
        key = "atomic-race"
        payload = payload_with_photo(repo, key)
        barrier = threading.Barrier(2)
        outcomes = []
        errors = []

        def worker(number):
            try:
                barrier.wait()
                outcomes.append(submit(payload, key, repo, "request-" + str(number))[1])
            except Exception as exc:  # pragma: no cover - assertion reports details
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(number,)) for number in (1, 2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(errors, [])
        self.assertEqual(sorted(outcomes), [False, True])
        self.assertEqual((len(repo.by_key), len(repo.participants), len(repo.audit)), (1, 1, 1))
        photo = repo.photo_objects[payload["photo_object_id"]]
        self.assertEqual(photo["application_id"], repo.by_key[key]["application_id"])

    def test_attached_photo_cannot_be_reused_by_another_application(self):
        repo = FakeRepository()
        first_key = "single-photo-owner"
        payload = payload_with_photo(repo, first_key)
        first, _ = submit(payload, first_key, repo, "request-first")
        attached = copy.deepcopy(repo.photo_objects[payload["photo_object_id"]])

        with self.assertRaises(RepositoryConflict):
            submit(payload, "different-application-key", repo, "request-second")

        self.assertEqual(repo.photo_objects[payload["photo_object_id"]], attached)
        self.assertEqual(repo.photo_objects[payload["photo_object_id"]]["application_id"], first["application_id"])
        self.assertEqual(len(repo.by_key), 1)

    def test_failures_at_each_atomic_stage_leave_only_the_ready_photo(self):
        for stage in (
            "photo_validation",
            "participant_resolution",
            "application_write",
            "photo_attachment",
        ):
            with self.subTest(stage=stage):
                repo = FailingSubmissionRepository(stage)
                key = "failure-" + stage
                payload = payload_with_photo(repo, key)
                photo_before = copy.deepcopy(repo.photo_objects[payload["photo_object_id"]])

                with self.assertRaisesRegex(RuntimeError, "injected_" + stage):
                    submit(payload, key, repo, "request")

                self.assertEqual(repo.photo_objects[payload["photo_object_id"]], photo_before)
                self.assertEqual(repo.photo_objects[payload["photo_object_id"]]["lifecycle_state"], "READY")
                self.assertIsNone(repo.photo_objects[payload["photo_object_id"]]["application_id"])
                self.assertIsNone(repo.photo_objects[payload["photo_object_id"]]["participant_id"])
                self.assertEqual((repo.by_key, repo.by_phone, repo.participants, repo.audit), ({}, {}, {}, []))

    def test_privacy_keeps_only_opaque_photo_reference_on_application(self):
        repo = FakeRepository()
        key = "raw-idempotency-secret"
        payload = payload_with_photo(repo, key)
        record, _ = submit(payload, key, repo, "request")
        application = repo.by_key[key]
        photo = repo.photo_objects[payload["photo_object_id"]]

        self.assertEqual(photo["owner_context_hash"], hashlib.sha256(key.encode("utf-8")).hexdigest())
        self.assertNotIn(key, json.dumps(photo))
        self.assertNotIn("owner_context_hash", application)
        self.assertEqual(application["photo_object_id"], record["photo_object_id"])
        for forbidden in ("storage_key", "url", "binary", "filename", "exif"):
            self.assertNotIn(forbidden, application)


if __name__ == "__main__":
    unittest.main()
