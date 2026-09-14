-- Wave 1 Phase B migration-ledger bootstrap only. DO NOT apply automatically.
-- The ledger contains operational schema metadata only and no personal data.
CREATE TABLE schema_migrations (
    environment Utf8 NOT NULL,
    migration_id Utf8 NOT NULL,
    applied_at Timestamp NOT NULL,
    PRIMARY KEY (environment, migration_id)
);
