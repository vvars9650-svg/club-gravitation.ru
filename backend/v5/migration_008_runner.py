"""Explicit TEST YDB data-plane rollout. No network access at import time.

Run as python -m backend.v5.migration_008_runner --help.
The operator must pause ALL writers throughout schema/backfill/verify/register.
No credentials, contacts, database paths or SDK errors are emitted to stdout.
"""

import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from .domain import phone as normalize_phone
from .migration_ledger import MIGRATION_IDS


MIGRATION = "008_admin_crm_v2"
COLUMNS = {
    "owner": "Utf8", "priority": "Utf8", "next_action": "Utf8",
    "next_contact_at": "Timestamp", "internal_comment": "Utf8",
    "duplicate_attempt_count": "Uint64", "last_duplicate_at": "Timestamp",
    "last_duplicate_match_basis": "Utf8", "possible_duplicate_count": "Uint64",
    "possible_duplicate_match_basis": "Utf8", "possible_duplicate_application_id": "Utf8",
}
KEY_TABLES = {
    "application_phone_keys": {
        "environment": "Utf8", "normalized_phone": "Utf8", "application_id": "Utf8",
        "participant_id": "Utf8", "created_at": "Timestamp",
    },
    "application_submission_keys": {
        "environment": "Utf8", "submission_id": "Utf8", "application_id": "Utf8",
        "participant_id": "Utf8", "payload_fingerprint": "Utf8", "outcome": "Utf8",
        "created_at": "Timestamp",
    },
}
KEYS = {
    "application_phone_keys": ["environment", "normalized_phone"],
    "application_submission_keys": ["environment", "submission_id"],
}
REQUIRED = {"applications." + c for c in COLUMNS} | set(KEY_TABLES)
LIVE_ACTION = "duplicate_submission|basis=normalized_phone"
EVENT_PREFIX = LIVE_ACTION + "|source=migration_008|reference="


class Stop(RuntimeError):
    """Only fixed, non-PII reason codes may be passed to this exception."""


def guard(environment, endpoint, database):
    if environment != "TEST":
        raise Stop("explicit_TEST_required")
    if not endpoint or not endpoint.startswith("grpcs://") or not database or not database.startswith("/"):
        raise Stop("explicit_secure_endpoint_and_database_required")


def schema_report(schema):
    present, incompatible = set(), []
    app = schema.get("applications", {}).get("columns", {})
    for column, expected in COLUMNS.items():
        if column in app:
            present.add("applications." + column)
            if app[column].rstrip("?") != expected:
                incompatible.append("applications." + column)
    for table, columns in KEY_TABLES.items():
        if table not in schema:
            continue
        present.add(table)
        description = schema[table]
        if (description["keys"] != KEYS[table]
                or any(description["columns"].get(c, "") != t for c, t in columns.items())):
            incompatible.append(table)
    missing = sorted(REQUIRED - present)
    state = "schema_ready" if not missing and not incompatible else "partial" if present else "not_started"
    return {"result": "PASS" if state == "schema_ready" else "FAIL", "state": state,
            "missing": missing, "incompatible": sorted(incompatible)}


def timestamp(value):
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    try:
        return timestamp(datetime.fromisoformat(value.replace("Z", "+00:00")))
    except (ValueError, TypeError, AttributeError):
        raise Stop("invalid_submitted_at") from None


def technical(value, prefix):
    if not isinstance(value, str) or not re.fullmatch(prefix + r"[A-Za-z0-9_-]+", value):
        raise Stop("invalid_technical_identifier")
    return value


def plan(applications):
    groups, ids = {}, set()
    for source in applications:
        row = dict(source)
        technical(row["application_id"], "APP-")
        technical(row["participant_id"], "PT-")
        if row["application_id"] in ids:
            raise Stop("duplicate_application_id")
        ids.add(row["application_id"])
        number = row.get("application_number")
        if number is not None and (type(number) is not int or number < 0):
            raise Stop("invalid_application_number")
        row["submitted_at"] = timestamp(row["submitted_at"])
        try:
            normalized = normalize_phone(row["phone"])
        except Exception:
            raise Stop("invalid_phone") from None
        groups.setdefault(normalized, []).append(row)
    for rows in groups.values():
        rows.sort(key=lambda r: (r["submitted_at"],
            r.get("application_number") if (r.get("application_number") or 0) > 0 else 2**64,
            r["application_id"]))
    return groups


def inventory_output(groups):
    # Group identifiers derive from technical IDs, not low-entropy phone hashes.
    return {"result": "PASS", "applications": sum(map(len, groups.values())),
            "groups": len(groups), "later_rows": sum(len(r) - 1 for r in groups.values()),
            "plan": [{"group_id": hashlib.sha256(rows[0]["application_id"].encode()).hexdigest(),
                      "canonical_application_id": rows[0]["application_id"],
                      "rows": [{k: r.get(k) for k in ("application_id", "participant_id", "application_number", "submitted_at")}
                               for r in rows]} for rows in sorted(groups.values(), key=lambda r: r[0]["application_id"])]}


def evidence(canonical, later):
    digest = hashlib.sha256((MIGRATION + ":" + canonical["application_id"] + ":" + later["application_id"]).encode()).hexdigest()
    return {"audit_id": "AUD-" + digest, "application_id": canonical["application_id"],
            "participant_id": canonical["participant_id"], "timestamp": later["submitted_at"],
            "request_id": "migration-008", "action": EVENT_PREFIX + later["application_id"]}


def expected_state(snapshot):
    groups = plan(snapshot["applications"])
    expected = {e["audit_id"]: e for rows in groups.values() for e in [evidence(rows[0], r) for r in rows[1:]]}
    return groups, expected


def verify(snapshot, schema):
    report = schema_report(schema)
    errors = [] if report["result"] == "PASS" else ["schema_incomplete"]
    groups, expected = expected_state(snapshot)
    keys = snapshot["phone_keys"]
    participants = {p["participant_id"] for p in snapshot["participants"]}
    applications = {a["application_id"]: a for a in snapshot["applications"]}
    actual_events = {e["audit_id"]: e for e in snapshot["events"] if e["action"].startswith(EVENT_PREFIX)}
    if set(actual_events) != set(expected):
        errors.append("reconciliation_evidence_mismatch")
    for event_id in set(actual_events) & set(expected):
        if any(actual_events[event_id].get(k) != expected[event_id][k] for k in ("application_id", "participant_id", "action", "request_id")):
            errors.append("reconciliation_evidence_corrupt")
    if len(actual_events) != sum(e["action"].startswith(EVENT_PREFIX) for e in snapshot["events"]):
        errors.append("repeated_evidence_id")
    if len(keys) != len(groups) or {k["normalized_phone"] for k in keys} != set(groups):
        errors.append("canonical_key_set_mismatch")
    key_map = {k["normalized_phone"]: k for k in keys}
    numbers = []
    for phone, rows in groups.items():
        canonical = rows[0]
        key = key_map.get(phone, {})
        if key.get("application_id") != canonical["application_id"] or key.get("participant_id") != canonical["participant_id"]:
            errors.append("canonical_key_mismatch")
        if canonical["participant_id"] not in participants:
            errors.append("missing_participant")
        number = canonical.get("application_number")
        if not number or number <= 0:
            errors.append("visible_number_not_positive")
        else:
            numbers.append(number)
        live = sum(e["application_id"] == canonical["application_id"] and e["action"] == LIVE_ACTION for e in snapshot["events"])
        if canonical.get("duplicate_attempt_count") != len(rows) - 1 + live:
            errors.append("duplicate_summary_mismatch")
        if not canonical.get("application_status") or not canonical.get("next_action"):
            errors.append("operational_defaults_missing")
    for key in keys:
        if key["application_id"] not in applications or key["participant_id"] not in participants:
            errors.append("dangling_phone_key")
    if len(numbers) != len(set(numbers)):
        errors.append("duplicate_visible_number")
    allocated = max((a.get("application_number") or 0 for a in applications.values()), default=0)
    if snapshot["counter"] is None or snapshot["counter"] < allocated:
        errors.append("counter_below_allocated")
    if any("duplicate" in e["action"] and e["action"] != LIVE_ACTION
           and not e["action"].startswith((EVENT_PREFIX, "possible_duplicate|")) for e in snapshot["events"]):
        errors.append("unrecognized_duplicate_evidence")
    if not set(MIGRATION_IDS[:-1]).issubset(snapshot["ledger"]):
        errors.append("prior_migrations_missing")
    if errors and MIGRATION in snapshot["ledger"]:
        errors.append("migration_incorrectly_registered")
    return {"result": "FAIL" if errors else "PASS", "errors": sorted(set(errors)),
            "applications": len(applications), "canonical_groups": len(groups),
            "phone_keys": len(keys), "expected_events": len(expected),
            "actual_events": len(actual_events), "ledger_complete": MIGRATION in snapshot["ledger"]}


class YdbStore:
    """Thin adapter using the installed YDB SDK only; injectable for offline tests."""

    def __init__(self, environment, endpoint, database):
        guard(environment, endpoint, database)
        import ydb
        token = os.environ.get("YDB_ACCESS_TOKEN")
        if not token:
            raise Stop("YDB_ACCESS_TOKEN_required")
        self.ydb, self.database = ydb, database.rstrip("/")
        self.driver = ydb.Driver(endpoint=endpoint, database=database,
                                 credentials=ydb.AccessTokenCredentials(token))
        try:
            self.driver.wait(timeout=10, fail_fast=True)
            self.pool = ydb.QuerySessionPool(self.driver)
            self.tables = ydb.SessionPool(self.driver)
        except Exception:
            self.driver.stop()
            raise

    def close(self):
        self.tables.stop()
        self.pool.stop()
        self.driver.stop()

    def inspect(self):
        names = {e.name for e in self.driver.scheme_client.list_directory(self.database).children}
        result = {}
        for name in ["applications", *KEY_TABLES]:
            if name not in names:
                continue
            description = self.tables.retry_operation_sync(lambda s: s.describe_table(self.database + "/" + name))
            result[name] = {"columns": {c.name: str(c.type) for c in description.columns},
                            "keys": list(description.primary_key)}
        return result

    def schema_apply(self):
        # Refresh after each successful statement; a crashed/partial run resumes.
        sql = (Path(__file__).parent / "schema" / "008_admin_crm_v2.sql").read_text(encoding="utf-8")
        sql = re.sub(r"--[^\n]*", "", sql)
        for statement in sql.split(";"):
            statement = statement.strip()
            if not statement:
                continue
            schema = self.inspect()
            report = schema_report(schema)
            if report["incompatible"] or "applications" not in schema:
                raise Stop("schema_incompatible_or_baseline_missing")
            match = re.match(r"ALTER TABLE applications ADD COLUMN (\w+)", statement)
            target = "applications." + match[1] if match else re.match(r"CREATE TABLE (\w+)", statement)[1]
            if target not in report["missing"]:
                continue
            self.tables.retry_operation_sync(lambda s: s.execute_scheme(statement + ";"))
        return schema_report(self.inspect())

    def transaction(self, callback):
        def operation(session):
            with session.transaction(self.ydb.QuerySerializableReadWrite()) as tx:
                value = callback(YdbTransaction(tx, self.ydb))
                tx.commit()
                return value
        return self.pool.retry_operation_sync(operation, retry_settings=self.ydb.RetrySettings(max_retries=5, idempotent=True))


class YdbTransaction:
    def __init__(self, tx, sdk):
        self.tx, self.sdk = tx, sdk

    def query(self, sql, params=None):
        with self.tx.execute(sql, params or {}) as stream:
            return [dict(row) for result in stream for row in result.rows]

    def snapshot(self, schema=None):
        # Explicit column allowlist: never read names/emails/form/photo data.
        fields = ["application_id", "participant_id", "application_number", "submitted_at", "phone", "application_status"]
        for name in ("next_action", "duplicate_attempt_count", "last_duplicate_at", "last_duplicate_match_basis"):
            fields.append(name if schema is None or name in schema.get("applications", {}).get("columns", {}) else "NULL AS " + name)
        apps = self.query('SELECT ' + ', '.join(fields) + ' FROM applications WHERE environment="TEST";')
        participants = self.query('SELECT participant_id FROM participants WHERE environment="TEST";')
        keys = self.query('SELECT normalized_phone, application_id, participant_id, created_at FROM application_phone_keys WHERE environment="TEST";') if schema is None or "application_phone_keys" in schema else []
        events = self.query('SELECT audit_id, application_id, participant_id, timestamp, request_id, action FROM audit_log WHERE environment="TEST";')
        counters = self.query('SELECT last_value FROM application_counters WHERE environment="TEST" AND counter_name="applications";')
        ledger = self.query('SELECT migration_id FROM schema_migrations WHERE environment="TEST";')
        return {"applications": apps, "participants": participants, "phone_keys": keys, "events": events,
                "counter": counters[0]["last_value"] if counters else None, "ledger": {r["migration_id"] for r in ledger}}

    def reconcile(self, phone, rows, snapshot):
        canonical = rows[0]
        for later in rows[1:]:
            event = evidence(canonical, later)
            self.query('''DECLARE $id AS Utf8; DECLARE $app AS Utf8; DECLARE $participant AS Utf8;
                DECLARE $time AS Timestamp; DECLARE $action AS Utf8;
                UPSERT INTO audit_log (environment,audit_id,application_id,participant_id,timestamp,request_id,action)
                VALUES ("TEST",$id,$app,$participant,$time,"migration-008",$action);''',
                {"$id": event["audit_id"], "$app": event["application_id"], "$participant": event["participant_id"],
                 "$time": self.sdk.TypedValue(event["timestamp"], self.sdk.PrimitiveType.Timestamp), "$action": event["action"]})
        live = [e for e in snapshot["events"] if e["application_id"] == canonical["application_id"] and e["action"] == LIVE_ACTION]
        count = len(rows) - 1 + len(live)
        latest = max([timestamp(r["submitted_at"]) for r in rows[1:]] + [timestamp(e["timestamp"]) for e in live], default=None)
        created = next((k.get("created_at") for k in snapshot["phone_keys"] if k["normalized_phone"] == phone), None) or canonical["submitted_at"]
        self.query('''DECLARE $phone AS Utf8; DECLARE $app AS Utf8; DECLARE $participant AS Utf8;
            DECLARE $created AS Timestamp; DECLARE $count AS Uint64; DECLARE $last AS Timestamp?;
            UPSERT INTO application_phone_keys (environment,normalized_phone,application_id,participant_id,created_at)
            VALUES ("TEST",$phone,$app,$participant,$created);
            UPDATE applications SET
                application_status=IF(COALESCE(application_status,"")="","Новая заявка",application_status),
                next_action=IF(COALESCE(next_action,"")="","Рассмотреть",next_action),
                duplicate_attempt_count=$count,
                last_duplicate_at=COALESCE($last,last_duplicate_at),
                last_duplicate_match_basis=IF($count>0,"normalized_phone",last_duplicate_match_basis)
            WHERE environment="TEST" AND application_id=$app;''',
            {"$phone": phone, "$app": canonical["application_id"], "$participant": canonical["participant_id"],
             "$created": self.sdk.TypedValue(timestamp(created), self.sdk.PrimitiveType.Timestamp),
             "$count": self.sdk.TypedValue(count, self.sdk.PrimitiveType.Uint64),
             "$last": self.sdk.TypedValue(latest, self.sdk.OptionalType(self.sdk.PrimitiveType.Timestamp))})

    def register(self):
        self.query('''UPSERT INTO schema_migrations (environment,migration_id,applied_at)
                      VALUES ("TEST","008_admin_crm_v2",CurrentUtcTimestamp());''')


def run(store, phase, allow_write=False, writers_paused=False):
    schema = store.inspect()
    report = schema_report(schema)
    if phase == "preflight":
        return report
    writing = allow_write and phase in ("schema", "backfill", "register")
    if writing and not writers_paused:
        raise Stop("all_TEST_writers_must_be_paused")
    if phase == "schema":
        if writing:
            current = store.transaction(lambda tx: tx.snapshot(schema))
            if MIGRATION in current["ledger"] and report["result"] != "PASS":
                raise Stop("migration_incorrectly_registered")
            if not set(MIGRATION_IDS[:-1]).issubset(current["ledger"]):
                raise Stop("prior_migrations_missing")
        return store.schema_apply() if writing else {**report, "dry_run": True}
    if report["result"] != "PASS" and phase not in ("inventory", "verify"):
        raise Stop("schema_not_ready")
    if phase not in ("inventory", "backfill", "verify", "register"):
        raise Stop("unknown_phase")

    def read(tx):
        snapshot = tx.snapshot(schema)
        groups, _ = expected_state(snapshot)
        verification = verify(snapshot, schema)
        return snapshot, groups, verification

    snapshot, groups, verification = store.transaction(read)
    if phase == "inventory" or phase == "backfill" and not writing:
        return {**inventory_output(groups), "dry_run": True, "verification": verification}
    if phase == "verify" or phase == "register" and not writing:
        return {**verification, "dry_run": True}
    if phase == "backfill":
        # Existing ledger + bad data must never be silently repaired/re-blessed.
        fatal = {"prior_migrations_missing", "migration_incorrectly_registered", "counter_below_allocated",
                 "visible_number_not_positive", "duplicate_visible_number", "missing_participant",
                 "unrecognized_duplicate_evidence", "reconciliation_evidence_corrupt"}
        if fatal.intersection(verification["errors"]):
            raise Stop("backfill_preconditions_failed")
        for canonical_id in sorted(r[0]["application_id"] for r in groups.values()):
            def reconcile(tx):
                current, current_groups, checked = read(tx)
                if fatal.intersection(checked["errors"]):
                    raise Stop("backfill_preconditions_failed")
                _, expected = expected_state(current)
                if any(e["action"].startswith(EVENT_PREFIX) and e["audit_id"] not in expected for e in current["events"]):
                    raise Stop("unexpected_reconciliation_evidence")
                if MIGRATION in current["ledger"]:
                    return
                matches = [(p, r) for p, r in current_groups.items() if r[0]["application_id"] == canonical_id]
                if len(matches) != 1:
                    raise Stop("inventory_changed_restart_required")
                phone, rows = matches[0]
                if any(k["normalized_phone"] == phone and (k["application_id"] != canonical_id or k["participant_id"] != rows[0]["participant_id"]) for k in current["phone_keys"]):
                    raise Stop("conflicting_existing_key")
                tx.reconcile(phone, rows, current)
            store.transaction(reconcile)
        return store.transaction(lambda tx: verify(tx.snapshot(), store.inspect()))

    def register(tx):
        # Read verification and ledger insert share ONE serializable transaction.
        current = tx.snapshot()
        checked = verify(current, store.inspect())
        if checked["result"] != "PASS":
            raise Stop("registration_verification_failed")
        already = MIGRATION in current["ledger"]
        if not already:
            tx.register()
        return {**checked, "ledger_complete": True, "already_registered": already}
    return store.transaction(register)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment", required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--phase", choices=("preflight", "schema", "inventory", "backfill", "verify", "register"), default="preflight")
    parser.add_argument("--allow-write", action="store_true")
    parser.add_argument("--writers-paused", action="store_true")
    args = parser.parse_args(argv)
    store = None
    try:
        store = YdbStore(args.environment, args.endpoint, args.database)
        output = run(store, args.phase, args.allow_write, args.writers_paused)
    except Stop as error:
        output = {"result": "FAIL", "reason": str(error)}
    except Exception:
        # SDK exception text can contain query parameters/contacts. Never print it.
        output = {"result": "FAIL", "reason": "ydb_operation_failed"}
    finally:
        if store is not None:
            try:
                store.close()
            except Exception:
                output = {"result": "FAIL", "reason": "ydb_cleanup_failed"}
    print(json.dumps(output, ensure_ascii=False, default=lambda x: x.isoformat()))
    return 0 if output["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
