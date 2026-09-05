-- GRAVITATION V3 phone registry verification
-- Run after 001_indexes.sql.
-- Both result sets should be empty.

-- Participants with a phone that were not backfilled into the registry.
SELECT
    p.participant_id,
    p.phone
FROM participants AS p
LEFT JOIN participant_phone_keys AS k
ON p.phone = k.phone
WHERE p.phone IS NOT NULL
  AND p.phone != ""
  AND k.phone IS NULL;

-- Registry rows that point to a different phone owner than participants.
SELECT
    k.phone,
    k.participant_id AS registry_participant_id,
    p.participant_id AS participant_id
FROM participant_phone_keys AS k
LEFT JOIN participants AS p
ON k.participant_id = p.participant_id
WHERE p.participant_id IS NULL
   OR p.phone != k.phone;
