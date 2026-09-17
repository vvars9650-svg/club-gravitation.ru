import json
import threading
import unittest
from pathlib import Path

from backend.v5.handler import handler
from backend.v5.migration_ledger import validate_migration_id
from backend.v5.migration_008 import Migration008State, backfill_fake_repository, preflight_ddl, register_completed_migration, verify_backfill
from backend.v5.repository import FakeRepository
from backend.v5.service import submit
from backend.v5.tests.test_v5 import P, e, payload_with_photo


class CrmV2AcceptanceTests(unittest.TestCase):
    def test_secondary_email_warning_keeps_two_applications(self):
        repo = FakeRepository()
        first, _ = submit(payload_with_photo(repo, "email-a"), "email-a", repo, "request-email-a")
        second_payload = payload_with_photo(repo, "email-b", {**P, "phone": "+79990000002", "email": P["email"]})
        second, _ = submit(second_payload, "email-b", repo, "request-email-b")
        self.assertEqual(len(repo.by_key), 2)
        card = repo.get_admin_application(second["application_id"])["application"]
        self.assertEqual(card["possible_duplicate_match_basis"], "email")
        self.assertEqual(card["possible_duplicate_application_id"], first["application_id"])
        self.assertFalse(second.get("duplicate_submission", False))
        self.assertTrue(any("possible_duplicate|basis=email" in e["action"] for e in repo.audit))

    def test_secondary_profile_warning_and_name_only_no_warning(self):
        repo = FakeRepository()
        first, _ = submit(payload_with_photo(repo, "profile-a", {**P, "profile_or_messenger_url": "https://example.test/same"}), "profile-a", repo, "request-profile-a")
        second, _ = submit(payload_with_photo(repo, "profile-b", {**P, "phone": "+79990000002", "email": "profile-b@example.test", "profile_or_messenger_url": "https://example.test/same"}), "profile-b", repo, "request-profile-b")
        self.assertEqual(repo.get_admin_application(second["application_id"])["application"]["possible_duplicate_match_basis"], "profile_or_messenger")
        third, _ = submit(payload_with_photo(repo, "name-only", {**P, "phone": "+79990000003", "email": "other@example.test", "profile_or_messenger_url": "https://example.test/other"}), "name-only", repo, "request-name-only")
        self.assertEqual(repo.get_admin_application(third["application_id"])["application"]["possible_duplicate_count"], 0)

    def test_migration_008_preflight_backfill_is_resumable_and_ready_guarded(self):
        self.assertTrue(preflight_ddl({"applications.owner", "applications.priority", "applications.next_action", "applications.next_contact_at", "applications.internal_comment", "applications.duplicate_attempt_count", "applications.last_duplicate_at", "applications.last_duplicate_match_basis", "applications.possible_duplicate_count", "applications.possible_duplicate_match_basis", "applications.possible_duplicate_application_id", "application_phone_keys", "application_submission_keys"}))
        repo = FakeRepository()
        first, _ = submit(payload_with_photo(repo, "legacy-a"), "legacy-a", repo, "request-a")
        duplicate = dict(first); duplicate["application_id"] = "APP-LEGACY-2"; duplicate["application_number"] = 0; duplicate["submitted_at"] = "9999-01-01T00:00:00Z"; repo.by_key["legacy-b"] = duplicate
        repo.application_phone_keys.clear()
        backfill_fake_repository(repo)
        count = len(repo.audit); warnings = next(iter(repo.by_key.values()))["duplicate_attempt_count"]
        backfill_fake_repository(repo)
        self.assertEqual(len(repo.audit), count); self.assertEqual(next(iter(repo.by_key.values()))["duplicate_attempt_count"], warnings)
        state = Migration008State(ddl_ready=True)
        self.assertFalse(state.ready_for_deployment)
        self.assertTrue(verify_backfill(state, canonical_keys=1, duplicate_events=1))
        self.assertTrue(register_completed_migration(state, repo.register_migration))
        self.assertIn("008_admin_crm_v2", repo.applied_migrations())
    def test_phone_format_variants_resolve_to_one_original_application(self):
        repo = FakeRepository()
        variants = (
            "+7 999 000 00 01",
            "8 (999) 000-00-01",
            "+7(999)000-00-01",
            "89990000001",
        )
        records = []
        for index, value in enumerate(variants):
            key = "variant-" + str(index)
            records.append(submit(
                payload_with_photo(repo, key, {**P, "phone": value}),
                key, repo, "request-" + str(index),
            )[0])
        self.assertEqual(len(repo.by_key), 1)
        self.assertEqual(len({item["application_id"] for item in records}), 1)
        self.assertEqual(repo.application_counters, {"TEST": 1})
        self.assertEqual(next(iter(repo.by_key.values()))["duplicate_attempt_count"], 3)

    def test_duplicate_does_not_consume_number_and_unique_person_gets_next(self):
        repo = FakeRepository()
        first, _ = submit(payload_with_photo(repo, "first"), "first", repo, "request-first")
        duplicate, _ = submit(payload_with_photo(repo, "duplicate"), "duplicate", repo, "request-duplicate")
        second_payload = payload_with_photo(repo, "second", {**P, "phone": "+79990000002"})
        second, _ = submit(second_payload, "second", repo, "request-second")
        self.assertEqual((first["application_number"], duplicate["application_number"], second["application_number"]), (1, 1, 2))
        self.assertEqual(repo.application_counters, {"TEST": 2})
        self.assertTrue(duplicate["duplicate_submission"])

    def test_concurrent_duplicate_posts_create_one_application(self):
        repo = FakeRepository()
        barrier = threading.Barrier(2)
        outcomes = []
        errors = []

        def worker(key, phone):
            try:
                payload = payload_with_photo(repo, key, {**P, "phone": phone})
                barrier.wait()
                outcomes.append(submit(payload, key, repo, "request-" + key)[0])
            except Exception as error:  # pragma: no cover
                errors.append(error)

        threads = [
            threading.Thread(target=worker, args=("race-a", "+7 (999) 000-00-01")),
            threading.Thread(target=worker, args=("race-b", "8 999 000 00 01")),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])
        self.assertEqual(len(repo.by_key), 1)
        self.assertEqual(len({item["application_id"] for item in outcomes}), 1)
        self.assertEqual(repo.application_counters, {"TEST": 1})
        self.assertEqual(sum(item.get("duplicate_submission") is True for item in outcomes), 1)

    def test_duplicate_api_response_is_neutral_and_original_success_has_number(self):
        repo = FakeRepository()
        first_payload = payload_with_photo(repo, "api-first")
        first = json.loads(handler(e(first_payload, "api-first"), repo=repo)["body"])
        duplicate_payload = payload_with_photo(repo, "api-duplicate")
        duplicate_response = handler(e(duplicate_payload, "api-duplicate"), repo=repo)
        duplicate = json.loads(duplicate_response["body"])
        self.assertEqual(first["message"], "Ваша заявка принята. №000001")
        self.assertEqual(duplicate_response["statusCode"], 200)
        self.assertEqual(duplicate["message"], "Ваша заявка уже зарегистрирована. №000001")
        self.assertTrue(duplicate["already_registered"])
        self.assertEqual(duplicate["application_id"], first["application_id"])

    def test_application_updates_never_mutate_another_application(self):
        repo = FakeRepository()
        first, _ = submit(payload_with_photo(repo, "scope-first"), "scope-first", repo, "request-first")
        second_payload = payload_with_photo(repo, "scope-second", {**P, "phone": "+79990000002"})
        second, _ = submit(second_payload, "scope-second", repo, "request-second")
        repo.update_admin_application(first["application_id"], {"owner": "Влад", "decision": "Одобрен", "next_action": "Пригласить"}, "actor", "request-update")
        first_card = repo.get_admin_application(first["application_id"])["application"]
        second_card = repo.get_admin_application(second["application_id"])["application"]
        self.assertEqual((first_card["owner"], first_card["status"]), ("Влад", "Одобрен"))
        self.assertEqual((second_card["owner"], second_card["status"]), ("", "Новая заявка"))

    def test_crm_v2_migration_is_registered_and_additive(self):
        self.assertEqual(validate_migration_id("008_admin_crm_v2"), "008_admin_crm_v2")
        sql = Path("backend/v5/schema/008_admin_crm_v2.sql").read_text(encoding="utf-8")
        self.assertIn("CREATE TABLE application_phone_keys", sql)
        self.assertIn("CREATE TABLE application_submission_keys", sql)
        self.assertIn("ALTER TABLE applications ADD COLUMN owner", sql)
        self.assertNotIn("DROP TABLE", sql.upper())
        self.assertNotIn("DELETE FROM", sql.upper())


if __name__ == "__main__":
    unittest.main()
