import copy
import threading
import unittest

from backend.v5.domain import DomainError
from backend.v5.handler import handler
from backend.v5.migration_ledger import MIGRATION_IDS
from backend.v5.participant_model import (
    APPLICATION_DECISIONS,
    APPLICATION_STATUSES,
    PARTICIPANT_STATUSES,
    PROCESSING_STATES,
)
from backend.v5.repository import FakeRepository, RepositoryConflict
from backend.v5.service import submit
from backend.v5.tests.test_v5 import P, e, payload_with_photo


class PhaseBParticipantTests(unittest.TestCase):
    def test_approved_state_sets_are_exact(self):
        self.assertEqual(PARTICIPANT_STATUSES, ("Кандидат", "Одобрен", "Не одобрен", "Неактивен"))
        self.assertEqual(PROCESSING_STATES, ("Разрешена", "Заблокирована"))
        self.assertEqual(APPLICATION_STATUSES, ("Новая", "На рассмотрении", "Интервью назначено", "Интервью проведено", "Закрыта"))
        self.assertEqual(APPLICATION_DECISIONS, ("Одобрен", "Отклонён", "На обсуждение"))

    def test_new_application_creates_canonical_participant_and_phone_key(self):
        repo = FakeRepository()
        record, replay = submit(payload_with_photo(repo, "phase-b-new"), "phase-b-new", repo, "request-new")
        participant = repo.find_participant(record["participant_id"])
        self.assertFalse(replay)
        self.assertEqual(repo.by_phone, {"+79990000001": record["participant_id"]})
        self.assertEqual(participant["phone"], "+79990000001")
        self.assertEqual(participant["participant_status"], "Кандидат")
        self.assertEqual(participant["processing_state"], "Разрешена")
        self.assertEqual(record["application_status"], "Новая")
        self.assertEqual(record["decision"], "")

    def test_second_application_reuses_participant_without_overwrite(self):
        repo = FakeRepository()
        first_payload = payload_with_photo(repo, "phase-b-first")
        first, _ = submit(first_payload, "phase-b-first", repo, "request-first")
        first_snapshot = copy.deepcopy(repo.by_key["phase-b-first"])
        participant_before = repo.find_participant(first["participant_id"])
        changed = {
            **P,
            "phone": "+7 (999) 000-00-01",
            "full_name": "Другое Имя",
            "email": "changed@example.test",
            "city": "Сочи",
            "visit_krasnodar": "Да, регулярно",
            "profile_or_messenger_url": "https://changed.example/profile",
            "occupation": "Другая сфера",
        }
        second, _ = submit(payload_with_photo(repo, "phase-b-second", changed), "phase-b-second", repo, "request-second")
        self.assertEqual(second["participant_id"], first["participant_id"])
        self.assertEqual(len(repo.by_key), 2)
        self.assertEqual(len(repo.participants), 1)
        self.assertEqual(len(repo.by_phone), 1)
        self.assertEqual(repo.find_participant(first["participant_id"]), participant_before)
        self.assertEqual(repo.by_key["phase-b-first"], first_snapshot)
        self.assertEqual(repo.by_key["phase-b-second"]["form"]["full_name"], "Другое Имя")
        self.assertEqual(repo.by_key["phase-b-second"]["form"]["occupation"], "Другая сфера")

    def test_participant_admin_change_does_not_mutate_application(self):
        repo = FakeRepository()
        record, _ = submit(payload_with_photo(repo, "phase-b-admin"), "phase-b-admin", repo, "request")
        snapshot = copy.deepcopy(repo.by_key["phase-b-admin"]["form"])
        repo.update_admin_participant(record["participant_id"], {"owner": "Лара"}, "actor", "admin-request")
        self.assertEqual(repo.by_key["phase-b-admin"]["form"], snapshot)

    def test_idempotent_replay_and_conflicting_replay(self):
        repo = FakeRepository()
        payload = payload_with_photo(repo, "phase-b-idempotent")
        first, replay = submit(payload, "phase-b-idempotent", repo, "request-1")
        second, replay_second = submit(payload, "phase-b-idempotent", repo, "request-2")
        self.assertFalse(replay)
        self.assertTrue(replay_second)
        self.assertEqual(second["application_id"], first["application_id"])
        self.assertEqual((len(repo.by_key), len(repo.participants), len(repo.by_phone)), (1, 1, 1))
        with self.assertRaises(DomainError) as raised:
            submit({**payload, "full_name": "Changed"}, "phase-b-idempotent", repo, "request-3")
        self.assertEqual((raised.exception.code, raised.exception.status), ("idempotency_conflict", 409))

    def test_broken_phone_key_fails_without_reassignment(self):
        repo = FakeRepository()
        repo.by_phone["+79990000001"] = "PT-MISSING"
        response = handler(e(payload_with_photo(repo, "phase-b-broken"), "phase-b-broken"), repo=repo)
        self.assertEqual(response["statusCode"], 409)
        self.assertEqual(len(repo.by_key), 0)
        self.assertEqual(repo.by_phone["+79990000001"], "PT-MISSING")
        with self.assertRaises(RepositoryConflict):
            repo.resolve_phone("8 (999) 000-00-01")

    def test_concurrent_first_applications_share_one_participant(self):
        repo = FakeRepository()
        barrier = threading.Barrier(2)
        errors = []

        def create(key):
            try:
                barrier.wait()
                submit(payload_with_photo(repo, key), key, repo, "request-" + key)
            except Exception as error:  # pragma: no cover - assertion reports details
                errors.append(error)

        threads = [threading.Thread(target=create, args=(key,)) for key in ("race-a", "race-b")]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])
        self.assertEqual((len(repo.by_key), len(repo.participants), len(repo.by_phone)), (2, 1, 1))
        self.assertEqual(len({record["participant_id"] for record in repo.by_key.values()}), 1)

    def test_migration_ledger_is_stable_idempotent_and_pii_free(self):
        repo = FakeRepository()
        for migration_id in MIGRATION_IDS:
            self.assertTrue(repo.register_migration(migration_id))
            self.assertFalse(repo.register_migration(migration_id))
        self.assertEqual(repo.applied_migrations(), MIGRATION_IDS)
        self.assertNotIn("+7", repr(repo.applied_migrations()))
        with self.assertRaisesRegex(ValueError, "unknown_migration_id"):
            repo.register_migration("user@example.test")


if __name__ == "__main__":
    unittest.main()
