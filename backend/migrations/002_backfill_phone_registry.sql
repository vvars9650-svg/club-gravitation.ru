-- GRAVITATION V3 participant phone registry
-- Step 2: backfill existing participants that already have a non-empty phone.
-- Run after 001_indexes.sql creates participant_phone_keys.

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
