-- GRAVITATION V3 YDB preflight
-- Run before 001_indexes.sql.
-- The duplicate-phone query MUST return zero rows.

SELECT
    phone,
    COUNT(*) AS duplicate_count
FROM participants
WHERE phone IS NOT NULL AND phone != ""
GROUP BY phone
HAVING COUNT(*) > 1;

-- Informational only. Existing test/system participants without phone are not
-- backfilled into participant_phone_keys. New website applications require phone.
SELECT
    participant_id,
    full_name,
    phone
FROM participants
WHERE phone IS NULL OR phone = "";
