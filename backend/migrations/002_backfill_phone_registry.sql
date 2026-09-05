-- GRAVITATION V3 participant phone registry
-- Step 2: backfill existing participants that already have a non-empty phone.
-- Run after 001_indexes.sql creates participant_phone_keys.
-- participants.phone is nullable in the existing schema, so COALESCE is used
-- to provide a non-optional Utf8 value for participant_phone_keys.phone.

UPSERT INTO participant_phone_keys (
    phone,
    participant_id,
    created_at
)
SELECT
    COALESCE(phone, "") AS phone,
    participant_id,
    CurrentUtcTimestamp()
FROM participants
WHERE phone IS NOT NULL AND phone != "";
