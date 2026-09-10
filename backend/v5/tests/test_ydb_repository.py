import threading
import unittest
from pathlib import Path

import ydb

from backend.v5.repository import DESTRUCTION_CLASSIFICATION
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
            "telegram": "@ivan_test",
            "email": "ivan@example.test",
            "preferred_contact": "Telegram",
            "public_profile_url": "https://example.test/ivan",
            "occupation": "test",
            "life_outside_work": "test",
            "interests": "test",
            "what_interested": "test",
            "event_expectations": "test",
            "desired_connections": ["Новые друзья"],
            "values_in_people": "test",
            "barriers_to_meeting": "test",
            "social_comfort": "3",
            "initiative": "3",
            "acquaintance_scenario": "test",
            "successful_evening": "test",
            "return_reason": "test",
            "unacceptable_behavior": "test",
            "convenient_days": ["Суббота"],
            "source": "website",
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
            "FORM-2.1",
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

        self.assertIn(
            "UPDATE participants SET",
            write_query,
        )

        self.assertNotIn(
            "INSERT INTO participant_phone_keys",
            write_query,
        )

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


if __name__ == "__main__":
    unittest.main()

