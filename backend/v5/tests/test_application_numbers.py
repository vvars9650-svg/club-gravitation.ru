import hashlib
import json
import threading
import unittest

from backend.v5.handler import handler
from backend.v5.domain import DomainError
from backend.v5.migration_ledger import validate_migration_id
from backend.v5.repository import FakeRepository
from backend.v5.service import submit
from backend.v5.tests.test_v5 import P, payload_with_photo


class FailingRepository(FakeRepository):
    def __init__(self, stage):
        super().__init__()
        self.stage = stage

    def _submission_checkpoint(self, stage):
        if stage == self.stage:
            raise RuntimeError("injected_" + stage)


def response_body(result):
    return json.loads(result["body"])


class ApplicationNumberTests(unittest.TestCase):
    def test_first_and_second_new_applications_allocate_sequential_numbers(self):
        repo = FakeRepository()
        first_payload = payload_with_photo(repo, "number-first")
        second_payload = payload_with_photo(repo, "number-second", {**P, "phone": "+79990000002"})

        first, _ = submit(first_payload, "number-first", repo, "request-first")
        second, _ = submit(second_payload, "number-second", repo, "request-second")

        self.assertEqual(first["application_number"], 1)
        self.assertEqual(second["application_number"], 2)
        self.assertEqual(repo.application_counters, {"TEST": 2})

    def test_api_formats_first_number_and_replay_returns_same_number(self):
        repo = FakeRepository()
        key = "number-api"
        payload = payload_with_photo(repo, key)
        event = {
            "httpMethod": "POST",
            "headers": {"Content-Type": "application/json", "Idempotency-Key": key},
            "body": json.dumps(payload),
        }

        first = response_body(handler(event, repo=repo))
        replay = response_body(handler(event, repo=repo))

        self.assertEqual(first["application_id"], "APP-" + hashlib.sha256(key.encode()).hexdigest()[:20])
        self.assertEqual(first["application_number"], "000001")
        self.assertEqual(replay["application_number"], "000001")
        self.assertTrue(replay["idempotent_replay"])
        self.assertEqual(repo.application_counters, {"TEST": 1})

    def test_same_key_conflict_does_not_consume_next_number(self):
        repo = FakeRepository()
        first_payload = payload_with_photo(repo, "number-conflict")
        first, _ = submit(first_payload, "number-conflict", repo, "request-first")

        with self.assertRaisesRegex(DomainError, "idempotency_conflict"):
            submit({**first_payload, "full_name": "Changed"}, "number-conflict", repo, "request-conflict")

        next_payload = payload_with_photo(repo, "number-after-conflict", {**P, "phone": "+79990000002"})
        next_record, _ = submit(next_payload, "number-after-conflict", repo, "request-next")
        self.assertEqual(first["application_number"], 1)
        self.assertEqual(next_record["application_number"], 2)

    def test_failed_transaction_does_not_consume_number(self):
        failed_repo = FailingRepository("application_write")
        failed_payload = payload_with_photo(failed_repo, "number-failure")
        with self.assertRaisesRegex(RuntimeError, "injected_application_write"):
            submit(failed_payload, "number-failure", failed_repo, "request-failure")
        self.assertEqual(failed_repo.application_counters, {})
        failed_repo.stage = None

        next_payload = payload_with_photo(failed_repo, "number-after-failure")
        next_record, _ = submit(next_payload, "number-after-failure", failed_repo, "request-next")
        self.assertEqual(next_record["application_number"], 1)

    def test_concurrent_new_applications_are_unique_and_sequential(self):
        repo = FakeRepository()
        outcomes = []
        errors = []
        barrier = threading.Barrier(8)

        def worker(index):
            key = "number-concurrent-" + str(index)
            try:
                payload = payload_with_photo(repo, key, {**P, "phone": "+7999000" + str(index).zfill(4)})
                barrier.wait()
                record, replay = submit(payload, key, repo, "request-" + str(index))
                outcomes.append((record["application_number"], replay))
            except Exception as exc:  # pragma: no cover - assertion reports details
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(index,)) for index in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(errors, [])
        self.assertEqual(sorted(number for number, replay in outcomes), list(range(1, 9)))
        self.assertTrue(all(replay is False for _, replay in outcomes))

    def test_repeat_participant_keeps_original_number_and_application(self):
        repo = FakeRepository()
        first_payload = payload_with_photo(repo, "number-repeat-first")
        second_payload = payload_with_photo(repo, "number-repeat-second")
        first, _ = submit(first_payload, "number-repeat-first", repo, "request-first")
        second, _ = submit(second_payload, "number-repeat-second", repo, "request-second")

        self.assertEqual(first["application_number"], 1)
        self.assertEqual(second["application_number"], 1)
        self.assertEqual(first["application_id"], second["application_id"])
        self.assertTrue(second["duplicate_submission"])
        self.assertEqual(repo.application_counters, {"TEST": 1})
        self.assertTrue(first["application_id"].startswith("APP-"))
        self.assertTrue(second["application_id"].startswith("APP-"))

    def test_migration_007_is_in_ledger(self):
        self.assertEqual(
            validate_migration_id("007_application_number_sequence"),
            "007_application_number_sequence",
        )


if __name__ == "__main__":
    unittest.main()
