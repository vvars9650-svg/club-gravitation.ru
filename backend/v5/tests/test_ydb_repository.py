import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path

import ydb

from backend.v5.repository import DESTRUCTION_CLASSIFICATION, RepositoryConflict
from backend.v5.ydb_repository import YdbRepository


class FakeResultSet:
    def __init__(self, rows=None):
        self.rows = rows or []


class FakeExecuteResult:
    def __init__(self, result_sets, on_success=None):
        self.result_sets = result_sets
        self.on_success = on_success
        self.entered = False
        self.exited = False
        self.consumed = False
        self.index = 0

    def __enter__(self):
        self.entered = True
        return self

    def __iter__(self):
        return self

    def __next__(self):
        if self.index >= len(self.result_sets):
            self.consumed = True
            raise StopIteration

        item = self.result_sets[self.index]
        self.index += 1
        return item

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.exited = True
        if exc_type is None and self.consumed and self.on_success:
            self.on_success()
        return False


class FakeTransaction:
    def __init__(self, read_result_sets):
        self.read_result_sets = read_result_sets
        self.read_index = 0
        self.queries = []
        self.params = []
        self.commit_flags = []
        self.streams = []
        self.committed = False

    def execute(self, query, params=None, commit_tx=False):
        self.queries.append(query)
        self.params.append(params or {})
        self.commit_flags.append(commit_tx)

        if '"application" AS record_type' in query:
            result = self.read_result_sets[self.read_index:self.read_index + 1]
            self.read_index += 1
            stream = FakeExecuteResult(result)
        elif "FROM applications" in query and "participant_phone_keys" not in query:
            result = self.read_result_sets[self.read_index:self.read_index + 1]
            self.read_index += 1
            stream = FakeExecuteResult(result)
        elif "FROM participant_phone_keys" in query:
            result = self.read_result_sets[self.read_index:self.read_index + 1]
            self.read_index += 1
            stream = FakeExecuteResult(result)
        elif "SELECT processing_blocked FROM participants" in query:
            stream = FakeExecuteResult(self.read_result_sets)
        elif "FROM schema_migrations" in query:
            result = self.read_result_sets[self.read_index:self.read_index + 1]
            self.read_index += 1
            stream = FakeExecuteResult(result)
        else:
            stream = FakeExecuteResult(
                [],
                on_success=(
                    lambda: setattr(self, "committed", True)
                ) if commit_tx else None,
            )

        self.streams.append(stream)
        return stream

    def commit(self):
        self.committed = True



class FakeSession:
    def __init__(self, transaction):
        self.tx = transaction
        self.tx_mode = None

    def transaction(self, tx_mode=None):
        self.tx_mode = tx_mode
        return self.tx


class FakePool:
    def __init__(self, session):
        self.session = session
        self.retry_settings = None
        self.stop_calls = 0

    def retry_operation_sync(self, callee, retry_settings=None):
        self.retry_settings = retry_settings
        return callee(self.session)

    def stop(self):
        self.stop_calls += 1


class AdminReadPool:
    def __init__(self):
        self.queries = []

    def execute_with_retries(self, query, params, retry_settings=None):
        self.queries.append((query, params))
        return [
            FakeResultSet([{
                "application_id": "APP-ADMIN", "participant_id": "PT-ADMIN",
                "submitted_at": "2026-09-09T00:00:00Z", "full_name": "Тест",
                "age": 30, "city": "Краснодар", "phone": "+79990000001",
                "telegram": "@test", "preferred_contact": "Telegram",
                "lifecycle_status": "Новая заявка", "owner": "", "priority": "",
                "next_action": "", "next_contact_at": None, "decision": "",
            }])
        ]


def make_record():
    return {
        "environment": "PROD",
        "application_id": "CLIENT-SPOOF",
        "participant_id": "PT-TEST001",
        "consent_id": "CONS-TEST001",
        "payload_fingerprint": "fingerprint-test",
        "request_id": "REQ-TEST001",
        "form": {
            "full_name": "Иван Тестов",
            "age": 30,
            "gender": "Мужчина",
            "city": "Краснодар",
            "visit_krasnodar": "",
            "phone": "+79990000001",
            "email": "ivan@example.test",
            "preferred_contact": "по email",
            "profile_or_messenger_url": "https://example.test/profile",
            "public_profile_url": "https://example.test/ivan",
            "occupation": "test",
            "life_outside_work": "test",
            "what_interested": "test",
            "what_participant_brings": "test",
            "what_friends_value": "test",
            "desired_connections": ["Новые друзья"],
            "desired_connections_other": "",
            "values_in_people": "test",
            "barriers_to_meeting": "test",
            "acquaintance_methods": ["Через живой разговор"],
            "acquaintance_methods_other": "",
            "return_reason": "test",
            "source": "Сайт / поиск",
        },
        "consent": {
            "participant_id": "PT-TEST001",
            "application_id": "CLIENT-SPOOF",
            "consent_id": "CONS-TEST001",
            "consent_text_hash": "CLIENT-SPOOF",
            "form_version": "CLIENT-SPOOF",
            "granted": False,
            "source": "CLIENT-SPOOF",
        },
    }


class YdbRepositoryTests(unittest.TestCase):
    def make_repo(self, transaction):
        repo = YdbRepository.__new__(YdbRepository)
        repo.endpoint = "test"
        repo.database = "test"
        repo.consent_hash = "TEST-HASH-ONLY"
        repo.driver = object()
        repo.pool = FakePool(FakeSession(transaction))
        return repo

    def test_new_application_uses_serializable_transaction(self):
        tx = FakeTransaction(
            [
                FakeResultSet([]),
            ]
        )

        repo = self.make_repo(tx)
        record = make_record()

        result = repo.save(
            "test-key-00000001",
            record,
        )

        self.assertTrue(result)
        self.assertIsInstance(
            repo.pool.session.tx_mode,
            ydb.QuerySerializableReadWrite,
        )
        self.assertEqual(tx.commit_flags, [False, True])
        self.assertTrue(tx.committed)

        for stream in tx.streams:
            self.assertTrue(stream.entered)
            self.assertTrue(stream.consumed)
            self.assertTrue(stream.exited)

    def test_server_owned_values_override_client(self):
        tx = FakeTransaction(
            [
                FakeResultSet([]),
            ]
        )

        repo = self.make_repo(tx)
        record = make_record()

        repo.save(
            "test-key-00000002",
            record,
        )

        self.assertEqual(
            record["environment"],
            "TEST",
        )

        self.assertEqual(
            record["consent"]["consent_text_hash"],
            "TEST-HASH-ONLY",
        )

        self.assertEqual(
            record["consent"]["form_version"],
            "FORM-2.2",
        )

        self.assertTrue(
            record["consent"]["granted"]
        )

        self.assertEqual(
            record["consent"]["source"],
            "website",
        )

        self.assertNotEqual(
            record["application_id"],
            "CLIENT-SPOOF",
        )

    def test_transaction_writes_expected_tables(self):
        tx = FakeTransaction(
            [
                FakeResultSet([]),
            ]
        )

        repo = self.make_repo(tx)

        repo.save(
            "test-key-00000003",
            make_record(),
        )

        self.assertEqual(
            len(tx.queries),
            2,
        )

        write_query = tx.queries[1]

        for table in (
            "participants",
            "participant_phone_keys",
            "applications",
            "consents",
            "technical_logs",
            "audit_log",
        ):
            self.assertIn(
                table,
                write_query,
            )

        self.assertNotIn(
            "raw_payload",
            write_query,
        )

        self.assertNotIn(
            "yandex_disk",
            write_query.lower(),
        )

        self.assertNotIn(
            "photo",
            write_query.lower(),
        )

    def test_participant_is_written_before_application(self):
        tx = FakeTransaction(
            [
                FakeResultSet([]),
            ]
        )

        repo = self.make_repo(tx)

        repo.save(
            "test-key-00000004",
            make_record(),
        )

        write_query = tx.queries[1]

        participant_pos = write_query.index(
            "INSERT INTO participants"
        )

        application_pos = write_query.index(
            "INSERT INTO applications"
        )

        self.assertLess(
            participant_pos,
            application_pos,
        )

    def test_existing_phone_reuses_participant(self):
        tx = FakeTransaction(
            [
                FakeResultSet(
                    [
                        {
                            "record_type": "phone",
                            "application_id": "",
                            "key_participant_id": "PT-EXISTING",
                            "participant_id": "PT-EXISTING",
                            "payload_fingerprint": "",
                            "processing_blocked": False,
                        }
                    ]
                ),
            ]
        )

        repo = self.make_repo(tx)
        record = make_record()

        result = repo.save(
            "test-key-00000005",
            record,
        )

        self.assertTrue(result)

        self.assertEqual(
            record["participant_id"],
            "PT-EXISTING",
        )

        self.assertEqual(
            record["consent"]["participant_id"],
            "PT-EXISTING",
        )

        write_query = tx.queries[1]

        self.assertNotIn("UPDATE participants SET", write_query)
        self.assertNotIn("INSERT INTO participants", write_query)

        self.assertNotIn(
            "INSERT INTO participant_phone_keys",
            write_query,
        )

    def test_broken_phone_key_fails_without_writes(self):
        tx = FakeTransaction([FakeResultSet([{
            "record_type": "phone", "application_id": "",
            "key_participant_id": "PT-MISSING", "participant_id": "",
            "payload_fingerprint": "", "processing_blocked": False,
        }])])
        repo = self.make_repo(tx)
        with self.assertRaisesRegex(RepositoryConflict, "phone_key_inconsistent"):
            repo.save("broken-phone-key", make_record())
        self.assertEqual(len(tx.queries), 1)
        self.assertTrue(tx.committed)

    def test_proposed_participant_id_collision_fails_without_writes(self):
        tx = FakeTransaction([FakeResultSet([{
            "record_type": "candidate", "application_id": "",
            "key_participant_id": "", "participant_id": "PT-COLLISION",
            "payload_fingerprint": "", "processing_blocked": False,
        }])])
        repo = self.make_repo(tx)
        with self.assertRaisesRegex(RepositoryConflict, "participant_id_conflict"):
            repo.save("participant-id-collision", make_record())
        self.assertEqual(len(tx.queries), 1)
        self.assertTrue(tx.committed)

    def test_existing_application_is_not_written_again(self):
        tx = FakeTransaction(
            [
                FakeResultSet(
                    [
                        {
                            "record_type": "application",
                            "application_id": "APP-EXISTING",
                            "participant_id": "PT-EXISTING",
                            "payload_fingerprint": "fingerprint-test",
                            "processing_blocked": False,
                        }
                    ]
                ),
            ]
        )

        repo = self.make_repo(tx)

        result = repo.save(
            "test-key-00000006",
            make_record(),
        )

        self.assertFalse(result)
        self.assertTrue(tx.committed)

        # Only the initial read query should execute.
        self.assertEqual(
            len(tx.queries),
            1,
        )
        self.assertEqual(tx.commit_flags, [False])
        self.assertTrue(tx.streams[0].entered)
        self.assertTrue(tx.streams[0].consumed)
        self.assertTrue(tx.streams[0].exited)

    def test_close_stops_pool_then_driver_once(self):
        events = []

        class OrderedPool:
            def stop(self):
                events.append("pool")

        class OrderedDriver:
            def stop(self):
                events.append("driver")

        repo = YdbRepository.__new__(YdbRepository)
        repo.pool = OrderedPool()
        repo.driver = OrderedDriver()
        repo._close_lock = threading.Lock()
        repo._closed = False

        repo.close()
        repo.close()

        self.assertEqual(events, ["pool", "driver"])

    def test_admin_list_query_is_test_scoped_and_has_no_raw_payload(self):
        repo = YdbRepository.__new__(YdbRepository)
        repo.pool = AdminReadPool()
        rows = repo.list_admin_applications(
            {"q": "Тест", "lifecycle_status": "Новая заявка"},
            "submitted_at", "desc",
        )
        query, params = repo.pool.queries[0]
        self.assertEqual(rows[0]["environment"], "TEST")
        self.assertEqual(params["$environment"], "TEST")
        self.assertIn("FROM applications", query)
        self.assertIn("INNER JOIN participants", query)
        self.assertNotIn("raw_payload", query)
        self.assertNotIn("internal_comment", query)

    def test_admin_patch_writes_only_operational_fields_and_audit(self):
        tx = FakeTransaction([FakeResultSet([])])
        repo = self.make_repo(tx)
        repo.get_admin_participant = lambda participant_id: {
            "participant": {"participant_id": participant_id, "owner": "Влад"}
        }
        participant = repo.update_admin_participant(
            "PT-ADMIN", {"owner": "Влад", "internal_comment": "TEST note"},
            "auth-test", "REQ-ADMIN",
        )
        query = tx.queries[0]
        self.assertEqual(participant["participant_id"], "PT-ADMIN")
        self.assertIn("UPDATE participants SET", query)
        self.assertIn("INSERT INTO audit_log", query)
        self.assertIn("fields=internal_comment,owner", tx.params[0]["$action"])
        self.assertNotIn("TEST note", tx.params[0]["$action"])
        self.assertNotIn("phone", query.lower())
        self.assertEqual(tx.commit_flags, [True])

    def test_admin_patch_priority_with_unchanged_next_contact_uses_optional_timestamp(self):
        tx = FakeTransaction([FakeResultSet([])])
        repo = self.make_repo(tx)
        repo.get_admin_participant = lambda participant_id: {
            "participant": {"participant_id": participant_id, "priority": "Высокий", "next_contact_at": None}
        }

        participant = repo.update_admin_participant(
            "PT-ADMIN", {"priority": "Высокий", "next_contact_at": None},
            "auth-test", "REQ-PRIORITY",
        )

        self.assertEqual(participant["participant_id"], "PT-ADMIN")
        timestamp = tx.params[0]["$next_contact_at"]
        self.assertIsInstance(timestamp, ydb.TypedValue)
        self.assertIsNone(timestamp.value)
        self.assertEqual(str(timestamp.value_type), "Timestamp?")

    def test_admin_patch_null_next_contact_clears_timestamp_and_is_audited(self):
        tx = FakeTransaction([FakeResultSet([])])
        repo = self.make_repo(tx)
        repo.get_admin_participant = lambda participant_id: {
            "participant": {"participant_id": participant_id, "next_contact_at": None}
        }

        repo.update_admin_participant(
            "PT-ADMIN", {"next_contact_at": None}, "auth-test", "REQ-NULL",
        )

        self.assertIsNone(tx.params[0]["$next_contact_at"].value)
        self.assertIn("fields=next_contact_at", tx.params[0]["$action"])
        self.assertIn("INSERT INTO audit_log", tx.queries[0])

    def test_admin_patch_valid_next_contact_binds_utc_datetime_and_reads_back(self):
        tx = FakeTransaction([FakeResultSet([])])
        repo = self.make_repo(tx)
        repo.get_admin_participant = lambda participant_id: {
            "participant": {"participant_id": participant_id, "next_contact_at": "2026-09-13T12:34:56Z"}
        }

        participant = repo.update_admin_participant(
            "PT-ADMIN", {"next_contact_at": "2026-09-13T12:34:56Z"},
            "auth-test", "REQ-DATE",
        )

        bound = tx.params[0]["$next_contact_at"]
        self.assertEqual(bound.value, datetime(2026, 9, 13, 12, 34, 56, tzinfo=timezone.utc))
        self.assertEqual(str(bound.value_type), "Timestamp?")
        self.assertEqual(participant["next_contact_at"], "2026-09-13T12:34:56Z")

    def test_block_processing_is_serializable_idempotent_and_audited_without_reason(self):
        tx = FakeTransaction([FakeResultSet([{"processing_blocked": False}])])
        repo = self.make_repo(tx)
        self.assertTrue(repo.block_processing("PT-BLOCK", "REQ-BLOCK", "internal_request"))
        self.assertIsInstance(repo.pool.session.tx_mode, ydb.QuerySerializableReadWrite)
        self.assertEqual(tx.commit_flags, [False, True])
        self.assertTrue(tx.committed)
        self.assertIn("processing_blocked", tx.queries[1])
        self.assertIn("INSERT INTO audit_log", tx.queries[1])
        self.assertNotIn("internal_request", tx.queries[1])
        self.assertTrue(all(stream.consumed for stream in tx.streams))

        already = FakeTransaction([FakeResultSet([{"processing_blocked": True}])])
        repo = self.make_repo(already)
        self.assertFalse(repo.block_processing("PT-BLOCK", "REQ-BLOCK", "internal_request"))
        self.assertEqual(len(already.queries), 1)

    def test_blocked_submit_writes_no_application_or_consent(self):
        tx = FakeTransaction([FakeResultSet([{
            "record_type": "phone",
            "application_id": "",
            "key_participant_id": "PT-BLOCK",
            "participant_id": "PT-BLOCK",
            "payload_fingerprint": "",
            "processing_blocked": True,
        }])])
        repo = self.make_repo(tx)
        with self.assertRaisesRegex(Exception, "processing_blocked"):
            repo.save("blocked-key", make_record())
        self.assertEqual(len(tx.queries), 1)
        self.assertTrue(tx.committed)

    def test_destruction_plan_query_is_dry_run_and_pii_free(self):
        class PlanPool:
            def __init__(self): self.query = ""
            def execute_with_retries(self, query, params, retry_settings=None):
                self.query = query
                return [FakeResultSet([{"participant_id": "PT-PLAN"}]), FakeResultSet([{"participant_id": "PT-PLAN"}]), FakeResultSet([{"application_id": "APP-1"}]), FakeResultSet([{"consent_id": "CONS-1"}]), FakeResultSet([{"log_id": "LOG-1"}]), FakeResultSet([{"audit_id": "AUD-1"}])]
        repo = YdbRepository.__new__(YdbRepository)
        repo.pool = PlanPool()
        plan = repo.destruction_plan("PT-PLAN")
        self.assertTrue(plan["dry_run"])
        self.assertFalse(plan["delete_performed"])
        self.assertEqual(plan["records"]["applications"]["count"], 1)
        self.assertTrue(plan["records"]["applications"]["contains_personal_data"])
        self.assertTrue(plan["records"]["consents"]["retention_decision_required"])
        self.assertTrue(plan["records"]["technical_logs"]["contains_linkable_identifiers"])
        self.assertTrue(plan["records"]["audit_log"]["contains_personal_data"])
        for name, expected in DESTRUCTION_CLASSIFICATION.items():
            self.assertEqual({key: plan["records"][name][key] for key in expected}, expected)
            self.assertNotIn("contains_pii", plan["records"][name])
        self.assertNotIn("DELETE", repo.pool.query.upper())
        self.assertNotIn("raw_payload", repo.pool.query)

    def test_lifecycle_migration_only_adds_nonbreaking_columns(self):
        migration = (Path(__file__).resolve().parents[1] / "schema" / "002_v5_test_lifecycle.sql").read_text(encoding="utf-8")
        for column in ("processing_blocked Bool", "processing_blocked_at Timestamp", "processing_block_reason Utf8", "processing_block_request_id Utf8"):
            self.assertIn("ADD COLUMN " + column, migration)
        self.assertNotIn("DROP", migration.upper())

    def test_form_2_2_migration_is_additive_and_retains_legacy_columns(self):
        migration = (Path(__file__).resolve().parents[1] / "schema" / "003_form_2_2_additive.sql").read_text(encoding="utf-8")
        for column in (
            "profile_or_messenger_url", "what_participant_brings", "what_friends_value",
            "desired_connections_other", "acquaintance_methods", "acquaintance_methods_other",
        ):
            self.assertIn("ADD COLUMN " + column, migration)
        for forbidden in ("DROP", "RENAME", "ALTER COLUMN", "telegram Json", "acquaintance_scenario Json"):
            self.assertNotIn(forbidden, migration.upper() if forbidden in ("DROP", "RENAME", "ALTER COLUMN") else migration)

    def test_phase_b_migration_adds_foundation_and_ledger_only(self):
        ledger = (Path(__file__).resolve().parents[1] / "schema" / "004_schema_migration_ledger.sql").read_text(encoding="utf-8")
        migration = (Path(__file__).resolve().parents[1] / "schema" / "005_wave1_participant_foundation.sql").read_text(encoding="utf-8")
        for statement in (
            "ADD COLUMN participant_status Utf8", "ADD COLUMN profile_or_messenger_url Utf8",
            "ADD COLUMN occupation Utf8", "ADD COLUMN application_status Utf8",
            "ADD COLUMN decision Utf8",
        ):
            self.assertIn(statement, migration)
        for statement in ("CREATE TABLE schema_migrations", "migration_id Utf8 NOT NULL", "applied_at Timestamp NOT NULL"):
            self.assertIn(statement, ledger)
        for forbidden in ("DROP", "RENAME", "ALTER COLUMN", "photo"):
            self.assertNotIn(forbidden, migration.lower() if forbidden == "photo" else migration.upper())

    def test_wave2_photo_migration_is_additive_private_reference_only(self):
        migration = (Path(__file__).resolve().parents[1] / "schema" / "006_wave2_photo_foundation.sql").read_text(encoding="utf-8")
        for statement in (
            "ADD COLUMN photo_object_id Utf8",
            "ADD COLUMN current_photo_object_id Utf8",
            "CREATE TABLE photo_objects",
            "storage_key Utf8 NOT NULL",
            "owner_context_hash Utf8 NOT NULL",
            "lifecycle_state Utf8 NOT NULL",
        ):
            self.assertIn(statement, migration)
        for forbidden in ("DROP", "RENAME", "ALTER COLUMN", "public_url", "original_filename", "base64", " BLOB"):
            self.assertNotIn(forbidden, migration.upper() if forbidden in ("DROP", "RENAME", "ALTER COLUMN", " BLOB") else migration.lower())

    def test_ydb_photo_operations_fail_closed_until_phase_b(self):
        repo = YdbRepository.__new__(YdbRepository)
        with self.assertRaisesRegex(Exception, "photo_repository_phase_b_required"):
            repo.reserve_photo_for_submission("PHOTO-0000000000000001", "context", "APP-1")

    def test_ydb_migration_registration_is_idempotent(self):
        created = FakeTransaction([FakeResultSet([])])
        repo = self.make_repo(created)
        self.assertTrue(repo.register_migration("005_wave1_participant_foundation"))
        self.assertIn("INSERT INTO schema_migrations", created.queries[1])
        self.assertIn("CurrentUtcTimestamp()", created.queries[1])

        existing = FakeTransaction([FakeResultSet([{"migration_id": "005_wave1_participant_foundation"}])])
        repo = self.make_repo(existing)
        self.assertFalse(repo.register_migration("005_wave1_participant_foundation"))
        self.assertEqual(len(existing.queries), 1)

    def test_ydb_applied_migrations_returns_stable_ids_only(self):
        class LedgerPool:
            def execute_with_retries(self, query, params, retry_settings=None):
                self.query, self.params = query, params
                return [FakeResultSet([
                    {"migration_id": "001_v5_test"},
                    {"migration_id": "004_schema_migration_ledger"},
                ])]

        repo = YdbRepository.__new__(YdbRepository)
        repo.pool = LedgerPool()
        self.assertEqual(repo.applied_migrations(), (
            "001_v5_test", "004_schema_migration_ledger",
        ))
        self.assertIn("ORDER BY migration_id", repo.pool.query)
        self.assertEqual(repo.pool.params, {"$environment": "TEST"})


if __name__ == "__main__":
    unittest.main()

