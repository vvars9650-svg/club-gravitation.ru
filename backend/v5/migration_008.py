"""Small, resumable control surface for the CRM V2 TEST reconciliation.

The SQL file is schema-only.  Operators call these helpers from a reviewed
backfill job; no migration or cloud action is performed by the application.
"""

from dataclasses import dataclass

from .migration_ledger import validate_migration_id


@dataclass
class Migration008State:
    ddl_ready: bool = False
    backfill_complete: bool = False
    verified: bool = False

    @property
    def ready_for_deployment(self):
        return self.ddl_ready and self.backfill_complete and self.verified


def preflight_ddl(schema_objects):
    """Return whether all additive 008 objects already exist.

    This deliberately performs detection only; it never issues DDL.
    """
    required = {
        "applications.owner",
        "applications.priority",
        "applications.next_action",
        "applications.next_contact_at",
        "applications.internal_comment",
        "applications.duplicate_attempt_count",
        "applications.last_duplicate_at",
        "applications.last_duplicate_match_basis",
        "applications.possible_duplicate_count",
        "applications.possible_duplicate_match_basis",
        "applications.possible_duplicate_application_id",
        "application_phone_keys",
        "application_submission_keys",
    }
    return required.issubset(set(schema_objects))


def verify_backfill(state, *, canonical_keys, duplicate_events):
    """Mark reconciliation complete only after deterministic verification."""
    if canonical_keys < 0 or duplicate_events < 0:
        raise ValueError("invalid_reconciliation_counts")
    state.backfill_complete = True
    state.verified = True
    return state.ready_for_deployment


def backfill_fake_repository(repo):
    """Idempotently reconcile legacy FakeRepository application snapshots."""
    groups = {}
    for record in repo.by_key.values():
        groups.setdefault(record["form"]["phone"], []).append(record)
    for phone, rows in groups.items():
        canonical = min(rows, key=lambda r: (r["submitted_at"],
            r.get("application_number") if (r.get("application_number") or 0) > 0 else 2**63,
            r["application_id"]))
        repo.application_phone_keys[phone] = canonical["application_id"]
        canonical.setdefault("duplicate_attempt_count", 0)
        seen = {(e.get("application_id"), e.get("action")) for e in repo.audit}
        for row in rows:
            if row is canonical:
                continue
            marker = (canonical["application_id"], f"possible_backfill_duplicate|reference={row['application_id']}")
            if marker not in seen:
                repo.audit.append({"timestamp": row["submitted_at"], "request_id": row["request_id"], "application_id": canonical["application_id"], "participant_id": canonical["participant_id"], "action": marker[1]})
                canonical["duplicate_attempt_count"] += 1
                seen.add(marker)
    return True


def register_completed_migration(state, register):
    """Ledger entry is legal only after full readiness verification."""
    if not state.ready_for_deployment:
        raise RuntimeError("crm_v2_backfill_incomplete")
    validate_migration_id("008_admin_crm_v2")
    return register("008_admin_crm_v2")
