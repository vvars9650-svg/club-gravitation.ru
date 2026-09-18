"""Offline rollout tests: real adapter/YQL paths with an atomic data-plane double."""

import copy
import io
import json
import unittest
from contextlib import contextmanager, redirect_stdout
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import ydb

from backend.v5 import migration_008_runner as runner
from backend.v5.migration_008 import preflight_ddl
from backend.v5.migration_ledger import MIGRATION_IDS


def schema():
    return {"applications": {"columns": {**runner.COLUMNS, "application_status": "Utf8", "application_number": "Uint64"}, "keys": ["environment", "application_id"]},
            **{name: {"columns": dict(columns), "keys": runner.KEYS[name][:]} for name, columns in runner.KEY_TABLES.items()}}


def app(suffix, phone="+79990000001", number=1, day=1, **values):
    return {"application_id": "APP-" + suffix, "participant_id": "PT-" + suffix,
            "phone": phone, "application_number": number, "submitted_at": datetime(2026, 1, day, tzinfo=timezone.utc),
            "application_status": None, "next_action": None, "duplicate_attempt_count": None,
            "owner": "Влад", "priority": "Высокий", "internal_comment": "preserve",
            "email": "private@example.test", "full_name": "Private Person",
            "profile": "https://private.example.test/profile", **values}


def state(rows):
    return {"applications": rows, "participants": [{"participant_id": r["participant_id"], "preserve": True} for r in rows],
            "phone_keys": [], "events": [], "counter": max((r["application_number"] or 0 for r in rows), default=0),
            "ledger": set(MIGRATION_IDS[:-1]), "consents": [{"sentinel": "consent"}], "photos": [{"sentinel": "photo"}]}


class WireTransaction:
    """Models YDB statement effects; copy-on-commit supplied by MemoryStore."""
    def __init__(self, data, queries):
        self.data, self.queries = data, queries

    @contextmanager
    def execute(self, sql, parameters=None):
        self.queries.append(sql)
        p = {k: getattr(v, "value", v) for k, v in (parameters or {}).items()}
        rows = []
        if sql.lstrip().startswith("SELECT"):
            for table, key in (("applications", "applications"), ("participants", "participants"),
                               ("application_phone_keys", "phone_keys"), ("audit_log", "events")):
                if "FROM " + table + " " in sql:
                    rows = copy.deepcopy(self.data[key])
            if "FROM application_counters " in sql:
                rows = [{"last_value": self.data["counter"]}] if self.data["counter"] is not None else []
            if "FROM schema_migrations " in sql:
                rows = [{"migration_id": mid} for mid in self.data["ledger"]]
        elif "UPSERT INTO audit_log" in sql:
            event = {"audit_id": p["$id"], "application_id": p["$app"], "participant_id": p["$participant"],
                     "timestamp": p["$time"], "request_id": "migration-008", "action": p["$action"]}
            self.data["events"] = [e for e in self.data["events"] if e["audit_id"] != event["audit_id"]] + [event]
        elif "UPSERT INTO application_phone_keys" in sql:
            key = {"normalized_phone": p["$phone"], "application_id": p["$app"], "participant_id": p["$participant"], "created_at": p["$created"]}
            self.data["phone_keys"] = [k for k in self.data["phone_keys"] if k["normalized_phone"] != p["$phone"]] + [key]
            row = next(r for r in self.data["applications"] if r["application_id"] == p["$app"])
            if "$number" in p:
                row["application_number"] = p["$number"]
            row.update(application_status=row.get("application_status") or "Новая заявка",
                       next_action=row.get("next_action") or "Рассмотреть", duplicate_attempt_count=p["$count"], last_duplicate_at=p["$last"] or row.get("last_duplicate_at"))
            if p["$count"]:
                row["last_duplicate_match_basis"] = "normalized_phone"
        elif "UPSERT INTO application_counters" in sql:
            self.data["counter"] = p["$number"]
        elif "UPSERT INTO schema_migrations" in sql:
            self.data["ledger"].add(runner.MIGRATION)
        else:
            raise AssertionError("Unmodelled statement: " + sql)
        yield [SimpleNamespace(rows=rows)]


class MemoryStore:
    def __init__(self, rows):
        self.data, self.schema = state(rows), schema()
        self.queries, self.commits = [], 0
        self.fail_at = None

    def inspect(self):
        return copy.deepcopy(self.schema)

    def transaction(self, callback):
        pending = copy.deepcopy(self.data)
        tx = runner.YdbTransaction(WireTransaction(pending, self.queries), ydb)
        result = callback(tx)
        self.commits += 1
        if self.commits == self.fail_at:
            raise RuntimeError("simulated transaction failure")
        self.data = pending
        return result


class MigrationRunnerTests(unittest.TestCase):
    def backfill(self, store):
        return runner.run(store, "backfill", True, True)

    def legacy_store(self, rows, counter=2):
        store = MemoryStore(rows)
        store.data["counter"] = counter
        return store

    def test_test_only_guard(self):
        runner.guard("TEST", "grpcs://test.invalid:2135", "/test")
        for env in (None, "", "PROD", "test"):
            with self.subTest(env=env), self.assertRaises(runner.Stop):
                runner.guard(env, "grpcs://test.invalid:2135", "/test")

    def test_explicit_connection_required(self):
        for endpoint, database in ((None, "/test"), ("grpcs://test.invalid", None), ("grpc://test.invalid", "/test")):
            with self.assertRaises(runner.Stop):
                runner.guard("TEST", endpoint, database)

    def test_complete_schema(self):
        self.assertEqual(runner.schema_report(schema())["result"], "PASS")
        self.assertTrue(preflight_ddl(runner.REQUIRED))

    def test_all_missing_columns_and_tables_fail(self):
        for column in runner.COLUMNS:
            partial = schema()
            del partial["applications"]["columns"][column]
            with self.subTest(column=column):
                self.assertEqual(runner.schema_report(partial)["state"], "partial")
                self.assertFalse(preflight_ddl(runner.REQUIRED - {"applications." + column}))
        for table in runner.KEY_TABLES:
            partial = schema()
            del partial[table]
            self.assertEqual(runner.schema_report(partial)["result"], "FAIL")

    def test_schema_not_started_and_incompatible(self):
        self.assertEqual(runner.schema_report({})["state"], "not_started")
        wrong = schema()
        wrong["application_phone_keys"]["keys"] = ["application_id"]
        self.assertEqual(runner.schema_report(wrong)["incompatible"], ["application_phone_keys"])
        wrong = schema()
        wrong["applications"]["columns"]["owner"] = "Uint64"
        self.assertEqual(runner.schema_report(wrong)["result"], "FAIL")

    def test_real_schema_inspection_and_already_applied_no_ddl(self):
        store = runner.YdbStore.__new__(runner.YdbStore)
        store.database = "/test"
        descriptions = schema()
        store.driver = SimpleNamespace(scheme_client=SimpleNamespace(list_directory=lambda _: SimpleNamespace(children=[SimpleNamespace(name=n) for n in descriptions])))
        calls = []
        def describe(path):
            description = descriptions[path.split("/")[-1]]
            return SimpleNamespace(columns=[SimpleNamespace(name=c, type=t) for c, t in description["columns"].items()], primary_key=description["keys"])
        session = SimpleNamespace(describe_table=describe, execute_scheme=lambda sql: calls.append(sql))
        store.tables = SimpleNamespace(retry_operation_sync=lambda fn: fn(session))
        self.assertEqual(store.inspect(), descriptions)
        self.assertEqual(store.schema_apply()["result"], "PASS")
        self.assertEqual(calls, [])

    def test_schema_apply_only_missing_column(self):
        store = runner.YdbStore.__new__(runner.YdbStore)
        partial = schema()
        del partial["applications"]["columns"]["owner"]
        store.inspect = lambda: copy.deepcopy(partial)
        calls = []
        def apply(sql):
            calls.append(sql)
            partial["applications"]["columns"]["owner"] = "Utf8"
        store.tables = SimpleNamespace(retry_operation_sync=lambda fn: fn(SimpleNamespace(execute_scheme=apply)))
        self.assertEqual(store.schema_apply()["result"], "PASS")
        self.assertEqual(calls, ["ALTER TABLE applications ADD COLUMN owner Utf8;"])

    def test_partial_ddl_failure_resumes_without_replaying_success(self):
        store = runner.YdbStore.__new__(runner.YdbStore)
        partial = schema()
        del partial["applications"]["columns"]["owner"]
        del partial["applications"]["columns"]["priority"]
        del partial["application_phone_keys"]
        store.inspect = lambda: copy.deepcopy(partial)
        calls = []
        fail = True
        def apply(sql):
            nonlocal fail
            if "ADD COLUMN priority" in sql and fail:
                fail = False
                raise RuntimeError("DDL interrupted")
            calls.append(sql)
            if "ADD COLUMN owner" in sql:
                partial["applications"]["columns"]["owner"] = "Utf8"
            elif "ADD COLUMN priority" in sql:
                partial["applications"]["columns"]["priority"] = "Utf8"
            else:
                self.assertIn("CREATE TABLE application_phone_keys", sql)
                partial["application_phone_keys"] = schema()["application_phone_keys"]
        store.tables = SimpleNamespace(retry_operation_sync=lambda fn: fn(SimpleNamespace(execute_scheme=apply)))
        with self.assertRaises(RuntimeError):
            store.schema_apply()
        self.assertEqual(store.schema_apply()["result"], "PASS")
        self.assertEqual(sum("ADD COLUMN owner" in q for q in calls), 1)
        self.assertEqual(len(calls), 3)

    def test_single_group(self):
        store = MemoryStore([app("a")])
        self.assertEqual(self.backfill(store)["result"], "PASS")
        self.assertEqual(len(store.data["phone_keys"]), 1)
        self.assertEqual(store.data["applications"][0]["duplicate_attempt_count"], 0)

    def test_all_legacy_canonical_numbers_are_backfilled_above_existing_counter(self):
        store = self.legacy_store([
            app("a", phone="+79990000001", number=None),
            app("b", phone="+79990000002", number=None),
        ], counter=2)
        self.assertEqual(self.backfill(store)["result"], "PASS")
        self.assertEqual(
            {row["application_id"]: row["application_number"] for row in store.data["applications"]},
            {"APP-a": 3, "APP-b": 4},
        )
        self.assertEqual(store.data["counter"], 4)
        self.assertEqual(runner.run(store, "verify")["result"], "PASS")

    def test_reconcile_write_uses_nullable_uint64_and_utf8_yql_types(self):
        store = self.legacy_store([app("a", number=None)])
        self.backfill(store)
        reconcile_query = next(query for query in store.queries if "UPDATE applications SET" in query)

        self.assertIn("application_number=Just($number)", reconcile_query)
        self.assertIn("duplicate_attempt_count=Just($count)", reconcile_query)
        self.assertIn('COALESCE(application_status,CAST(\"\" AS Utf8))', reconcile_query)
        self.assertIn('CAST(\"Новая заявка\" AS Utf8)', reconcile_query)
        self.assertIn('CAST(\"Рассмотреть\" AS Utf8)', reconcile_query)
        self.assertIn('CAST(\"normalized_phone\" AS Utf8)', reconcile_query)

    def test_counter_above_zero_with_no_allocated_rows_is_never_reused(self):
        store = self.legacy_store([app("a", number=None)], counter=7)
        self.backfill(store)
        self.assertEqual(store.data["applications"][0]["application_number"], 8)
        self.assertEqual(store.data["counter"], 8)

    def test_duplicate_group_numbers_only_canonical_and_keeps_later_rows(self):
        rows = [
            app("canonical", number=None, day=1),
            app("later-a", number=None, day=2),
            app("later-b", number=None, day=3),
        ]
        store = self.legacy_store(rows)
        before_ids = {row["application_id"] for row in store.data["applications"]}
        self.backfill(store)
        by_id = {row["application_id"]: row for row in store.data["applications"]}
        self.assertEqual(by_id["APP-canonical"]["application_number"], 3)
        self.assertIsNone(by_id["APP-later-a"]["application_number"])
        self.assertIsNone(by_id["APP-later-b"]["application_number"])
        self.assertEqual({row["application_id"] for row in store.data["applications"]}, before_ids)
        self.assertEqual(len(store.data["events"]), 2)
        self.assertEqual(len(store.data["phone_keys"]), 1)
        self.assertEqual(runner.run(store, "verify")["result"], "PASS")

    def test_existing_positive_canonical_number_is_preserved(self):
        store = self.legacy_store([app("a", number=42)], counter=42)
        before = copy.deepcopy(store.data["applications"])
        self.backfill(store)
        self.assertEqual(store.data["applications"][0]["application_number"], 42)
        self.assertEqual(store.data["counter"], 42)
        self.assertEqual(store.data["applications"][0]["owner"], before[0]["owner"])

    def test_mixed_numbered_and_unnumbered_canonicals_allocate_after_floor(self):
        store = self.legacy_store([
            app("numbered", phone="+79990000001", number=8),
            app("missing", phone="+79990000002", number=None),
        ], counter=8)
        self.backfill(store)
        by_id = {row["application_id"]: row for row in store.data["applications"]}
        self.assertEqual(by_id["APP-numbered"]["application_number"], 8)
        self.assertEqual(by_id["APP-missing"]["application_number"], 9)
        self.assertEqual(store.data["counter"], 9)

    def test_existing_allocated_number_reserves_value_even_when_counter_is_higher(self):
        store = self.legacy_store([
            app("canonical", number=None, day=1),
            app("historical", number=5, day=2),
        ], counter=7)
        self.backfill(store)
        by_id = {row["application_id"]: row for row in store.data["applications"]}
        self.assertEqual(by_id["APP-canonical"]["application_number"], 8)
        self.assertEqual(by_id["APP-historical"]["application_number"], 5)

    def test_deterministic_allocation_order_is_canonical_application_id(self):
        store = self.legacy_store([
            app("z", phone="+79990000001", number=None),
            app("a", phone="+79990000002", number=None),
            app("m", phone="+79990000003", number=None),
        ])
        self.backfill(store)
        by_id = {row["application_id"]: row for row in store.data["applications"]}
        self.assertEqual([by_id["APP-" + suffix]["application_number"] for suffix in ("a", "m", "z")], [3, 4, 5])
        self.assertEqual(runner.allocation_order(runner.plan(store.data["applications"])), ["APP-a", "APP-m", "APP-z"])

    def test_counter_below_existing_allocated_number_fails_closed(self):
        store = self.legacy_store([app("a", number=10)], counter=2)
        report = runner.run(store, "verify")
        self.assertIn("counter_below_allocated", report["errors"])
        with self.assertRaisesRegex(runner.Stop, "backfill_preconditions_failed"):
            self.backfill(store)

    def test_partial_number_allocation_then_rerun_matches_single_run(self):
        rows = [
            app("a", phone="+79990000001", number=None),
            app("b", phone="+79990000002", number=None),
            app("c", phone="+79990000003", number=None),
        ]
        single = self.legacy_store(copy.deepcopy(rows))
        partial = self.legacy_store(copy.deepcopy(rows))
        self.backfill(single)
        partial.fail_at = 3
        with self.assertRaises(RuntimeError):
            self.backfill(partial)
        self.assertEqual(partial.data["counter"], 3)
        self.assertEqual(sum(row["application_number"] is not None for row in partial.data["applications"]), 1)
        partial.fail_at = None
        self.backfill(partial)
        self.assertEqual(partial.data, single.data)

    def test_full_rerun_does_not_consume_or_renumber(self):
        store = self.legacy_store([
            app("a", phone="+79990000001", number=None),
            app("b", phone="+79990000002", number=None),
        ])
        self.backfill(store)
        before = copy.deepcopy(store.data)
        self.backfill(store)
        self.assertEqual(store.data, before)
        self.assertEqual(store.data["counter"], 4)

    def test_verify_fails_on_duplicate_canonical_numbers_and_impossible_counter(self):
        store = self.legacy_store([
            app("a", phone="+79990000001", number=3),
            app("b", phone="+79990000002", number=3),
        ], counter=3)
        self.assertIn("duplicate_visible_number", runner.run(store, "verify")["errors"])
        store.data["applications"][1]["application_number"] = 4
        store.data["counter"] = 2
        self.assertIn("counter_below_allocated", runner.run(store, "verify")["errors"])

    def test_deterministic_selection_and_ties(self):
        rows = [app("b", number=1, day=2), app("z", number=0), app("c", number=3), app("a", number=3)]
        groups = runner.plan(rows)
        self.assertEqual(next(iter(groups.values()))[0]["application_id"], "APP-a")
        rows[1]["application_number"] = 2
        self.assertEqual(next(iter(runner.plan(rows).values()))[0]["application_id"], "APP-z")

    def test_phone_variants_group_together(self):
        rows = [app("a"), app("b", phone="8 (999) 000-00-01", number=2, day=2)]
        self.assertEqual(len(runner.plan(rows)), 1)

    def test_partial_failure_and_resume_equals_single_run(self):
        rows = [app("a"), app("b", number=2, day=2), app("c", phone="+79990000002", number=3)]
        single, partial = MemoryStore(rows), MemoryStore(copy.deepcopy(rows))
        self.backfill(single)
        partial.fail_at = 3  # inventory + first group committed, second group rolled back
        with self.assertRaises(RuntimeError):
            self.backfill(partial)
        self.assertEqual(len(partial.data["phone_keys"]), 1)
        partial.fail_at = None
        self.assertEqual(self.backfill(partial)["result"], "PASS")
        self.assertEqual(partial.data, single.data)

    def test_full_rerun_no_event_or_count_inflation(self):
        store = MemoryStore([app("a"), app("b", number=2, day=2)])
        self.backfill(store)
        before = copy.deepcopy(store.data)
        self.backfill(store)
        self.assertEqual(store.data, before)
        self.assertEqual(len(store.data["events"]), 1)
        self.assertEqual(store.data["applications"][0]["duplicate_attempt_count"], 1)

    def test_live_duplicate_events_preserved_in_count(self):
        store = MemoryStore([app("a"), app("b", number=2, day=2)])
        store.data["events"].append({"audit_id": "AUD-live", "application_id": "APP-a", "action": runner.LIVE_ACTION, "timestamp": datetime(2026, 2, 1, tzinfo=timezone.utc)})
        self.backfill(store)
        self.backfill(store)
        self.assertEqual(store.data["applications"][0]["duplicate_attempt_count"], 2)
        self.assertEqual(len(store.data["events"]), 2)

    def test_preserves_historical_rows_numbers_and_operational_values(self):
        store = MemoryStore([app("a", application_status="Одобрен", next_action="Пригласить"), app("b", number=2, day=2)])
        before = copy.deepcopy(store.data)
        self.backfill(store)
        for key in ("participants", "consents", "photos", "counter"):
            self.assertEqual(store.data[key], before[key])
        self.assertEqual(store.data["applications"][1], before["applications"][1])
        for key, value in before["applications"][0].items():
            if key != "duplicate_attempt_count":
                self.assertEqual(store.data["applications"][0][key], value)
        writes = "\n".join(q for q in store.queries if not q.startswith("SELECT"))
        self.assertNotIn("DELETE", writes)
        self.assertNotIn("application_number", writes)
        self.assertNotIn("application_counters", writes)
        self.assertNotIn("email", writes)

    def test_verify_fail_inconsistent_key(self):
        store = MemoryStore([app("a")])
        self.backfill(store)
        store.data["phone_keys"][0]["application_id"] = "APP-missing"
        report = runner.run(store, "verify")
        self.assertEqual(report["result"], "FAIL")
        self.assertIn("dangling_phone_key", report["errors"])
        with self.assertRaises(runner.Stop):
            self.backfill(store)

    def test_visible_number_uniqueness_and_counter(self):
        store = MemoryStore([app("a"), app("b", phone="+79990000002")])
        self.assertIn("duplicate_visible_number", runner.run(store, "verify")["errors"])
        with self.assertRaises(runner.Stop):
            self.backfill(store)
        store.data["applications"][1]["application_number"] = 2
        self.assertIn("counter_below_allocated", runner.run(store, "verify")["errors"])

    def test_counter_covers_hidden_later_allocations_too(self):
        store = MemoryStore([app("a"), app("b", number=200, day=2)])
        self.backfill(store)
        store.data["counter"] = 1
        self.assertIn("counter_below_allocated", runner.run(store, "verify")["errors"])

    def test_existing_key_created_time_preserved(self):
        store = MemoryStore([app("a")])
        self.backfill(store)
        created = datetime(2026, 5, 1, tzinfo=timezone.utc)
        store.data["phone_keys"][0]["created_at"] = created
        self.backfill(store)
        self.assertEqual(store.data["phone_keys"][0]["created_at"], created)

    def test_extra_evidence_fails_verification(self):
        store = MemoryStore([app("a"), app("b", number=2, day=2)])
        self.backfill(store)
        extra = dict(store.data["events"][0], audit_id="AUD-unexpected")
        store.data["events"].append(extra)
        self.assertIn("reconciliation_evidence_mismatch", runner.run(store, "verify")["errors"])

    def test_missing_participant_and_invalid_number(self):
        store = MemoryStore([app("a", number=0)])
        store.data["participants"] = []
        errors = runner.run(store, "verify")["errors"]
        self.assertIn("missing_participant", errors)
        self.assertIn("visible_number_not_positive", errors)

    def test_write_flag_and_quiescence_required(self):
        store = MemoryStore([app("a")])
        before = copy.deepcopy(store.data)
        for phase in ("preflight", "inventory", "backfill", "verify", "register"):
            runner.run(store, phase)
        self.assertEqual(store.data, before)
        for phase in ("schema", "backfill", "register"):
            with self.assertRaises(runner.Stop):
                runner.run(store, phase, True)

    def test_registration_blocked_then_verified_and_idempotent(self):
        store = MemoryStore([app("a")])
        with self.assertRaises(runner.Stop):
            runner.run(store, "register", True, True)
        self.assertNotIn(runner.MIGRATION, store.data["ledger"])
        self.backfill(store)
        result = runner.run(store, "register", True, True)
        self.assertTrue(result["ledger_complete"])
        self.assertFalse(result["already_registered"])
        before = copy.deepcopy(store.data)
        self.assertTrue(runner.run(store, "register", True, True)["already_registered"])
        self.assertEqual(before, store.data)

    def test_registration_rechecks_inside_write_transaction(self):
        store = MemoryStore([app("a")])
        self.backfill(store)
        original = store.transaction
        count = 0
        def race(callback):
            nonlocal count
            count += 1
            if count == 2:
                store.data["counter"] = 0
            return original(callback)
        store.transaction = race
        with self.assertRaises(runner.Stop):
            runner.run(store, "register", True, True)
        self.assertNotIn(runner.MIGRATION, store.data["ledger"])

    def test_incorrect_ledger_and_partial_schema_fail_closed(self):
        store = MemoryStore([app("a")])
        store.data["ledger"].add(runner.MIGRATION)
        self.assertIn("migration_incorrectly_registered", runner.run(store, "verify")["errors"])
        with self.assertRaises(runner.Stop):
            self.backfill(store)
        del store.schema["applications"]["columns"]["owner"]
        self.assertIn("schema_incomplete", runner.run(store, "verify")["errors"])
        with self.assertRaises(runner.Stop):
            runner.run(store, "register", True, True)

    def test_inventory_before_schema_completion(self):
        store = MemoryStore([app("a")])
        store.schema = {"applications": {"columns": {}, "keys": []}}
        self.assertEqual(runner.run(store, "inventory")["applications"], 1)

    def test_output_excludes_contact_values(self):
        store = MemoryStore([app("a"), app("b", number=2, day=2)])
        output = json.dumps(runner.run(store, "inventory"), default=str)
        for value in ("+7999", "private@", "Private Person", "https://private", '"phone"', '"email"', '"profile"'):
            self.assertNotIn(value, output)
        self.assertIn("APP-a", output)

    def test_cli_redacts_sdk_exception(self):
        with patch.object(runner, "YdbStore", side_effect=RuntimeError("phone=+79990000001 token=secret")):
            output = io.StringIO()
            with redirect_stdout(output):
                code = runner.main(["--environment", "TEST", "--endpoint", "grpcs://test.invalid", "--database", "/test"])
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(output.getvalue()), {"result": "FAIL", "reason": "ydb_operation_failed"})


if __name__ == "__main__":
    unittest.main()
