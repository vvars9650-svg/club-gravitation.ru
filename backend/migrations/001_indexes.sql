-- GRAVITATION V3 participant phone registry
-- Step 1: create the concurrency/uniqueness registry table.
-- Run only after 000_preflight.sql returns zero duplicate non-empty phones.

CREATE TABLE participant_phone_keys (
    phone Utf8 NOT NULL,
    participant_id Utf8 NOT NULL,
    created_at Timestamp NOT NULL,
    PRIMARY KEY (phone)
);
