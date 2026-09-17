-- GRAVITATION V5 / Admin CRM V2. Apply only to the reviewed TEST database.
-- DDL only: this file never runs from application startup, tests, or builders.
-- Migrations 001-007 must already be verified and registered.

-- Operational state belongs to the Application, never to the Participant.
-- application_status and decision already exist from migration 005.
ALTER TABLE applications ADD COLUMN owner Utf8;
ALTER TABLE applications ADD COLUMN priority Utf8;
ALTER TABLE applications ADD COLUMN next_action Utf8;
ALTER TABLE applications ADD COLUMN next_contact_at Timestamp;
ALTER TABLE applications ADD COLUMN internal_comment Utf8;

-- Denormalized duplicate summary for the list/card warning. Detailed attempts
-- remain minimal audit_log events linked to the original Application.
ALTER TABLE applications ADD COLUMN duplicate_attempt_count Uint64;
ALTER TABLE applications ADD COLUMN last_duplicate_at Timestamp;
ALTER TABLE applications ADD COLUMN last_duplicate_match_basis Utf8;
ALTER TABLE applications ADD COLUMN possible_duplicate_count Uint64;
ALTER TABLE applications ADD COLUMN possible_duplicate_match_basis Utf8;
ALTER TABLE applications ADD COLUMN possible_duplicate_application_id Utf8;

-- The normalized phone is the sole automatic identity key for the pilots.
-- Its primary key is the database-level guard against concurrent duplicate
-- submissions. The value always points at the original club Application.
CREATE TABLE application_phone_keys (
    environment Utf8 NOT NULL,
    normalized_phone Utf8 NOT NULL,
    application_id Utf8 NOT NULL,
    participant_id Utf8 NOT NULL,
    created_at Timestamp NOT NULL,
    PRIMARY KEY (environment, normalized_phone)
);

-- Duplicate submissions do not create Application rows. This minimal mapping
-- preserves idempotency for those requests without retaining a second form.
CREATE TABLE application_submission_keys (
    environment Utf8 NOT NULL,
    submission_id Utf8 NOT NULL,
    application_id Utf8 NOT NULL,
    participant_id Utf8 NOT NULL,
    payload_fingerprint Utf8 NOT NULL,
    outcome Utf8 NOT NULL,
    created_at Timestamp NOT NULL,
    PRIMARY KEY (environment, submission_id)
);

-- Existing synthetic TEST rows are intentionally not backfilled here. Before
-- the new runtime is deployed, run the reviewed inventory/backfill procedure
-- in backend/v5/README.md. It preserves the earliest Application and converts
-- every later row into duplicate-attempt evidence without blind merging.
