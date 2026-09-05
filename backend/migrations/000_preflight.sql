-- GRAVITATION V3 YDB preflight
-- Run before 001_indexes.sql.
-- Expected result for duplicate phone query: zero rows.

SELECT
    phone,
    COUNT(*) AS duplicate_count
FROM participants
WHERE phone IS NOT NULL AND phone != ""
GROUP BY phone
HAVING COUNT(*) > 1;

-- Informational: participants without phone should be reviewed separately.
SELECT
    participant_id,
    full_name,
    phone
FROM participants
WHERE phone IS NULL OR phone = "";
