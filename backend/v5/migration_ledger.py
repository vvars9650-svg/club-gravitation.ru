"""Stable application-level migration identifiers; contains no personal data."""

MIGRATION_IDS = (
    "001_v5_test",
    "002_v5_test_lifecycle",
    "003_form_2_2_additive",
    "004_schema_migration_ledger",
    "005_wave1_participant_foundation",
    "006_wave2_photo_foundation",
    "007_application_number_sequence",
    "008_admin_crm_v2",
)


def validate_migration_id(migration_id):
    if migration_id not in MIGRATION_IDS:
        raise ValueError("unknown_migration_id")
    return migration_id
