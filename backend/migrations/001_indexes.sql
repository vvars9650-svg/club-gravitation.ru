-- GRAVITATION V3 participant phone registry
-- YDB does not allow adding a UNIQUE secondary index to this existing table.
-- We enforce phone uniqueness with a dedicated table whose PRIMARY KEY is phone.
-- Run after 000_preflight.sql returns zero duplicate non-empty phones.

CREATE TABLE participant_phone_keys (
    phone Utf8 NOT NULL,
    participant_id Utf8 NOT NULL,
    created_at Timestamp NOT NULL,
    PRIMARY KEY (phone)
);

-- Backfill existing participants that already have a phone.
-- The preflight duplicate check must be clean before this statement is run.
UPSERT INTO participant_phone_keys (
    phone,
    participant_id,
    created_at
)
SELECT
    phone,
    participant_id,
    CurrentUtcTimestamp()
FROM participants
WHERE phone IS NOT NULL AND phone != "";
