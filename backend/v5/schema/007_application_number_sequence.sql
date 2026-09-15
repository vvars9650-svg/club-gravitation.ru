-- Sequential human-facing application numbers. DO NOT apply automatically.
-- Existing applications remain valid and may have a NULL application_number.
ALTER TABLE applications ADD COLUMN application_number Uint64;

CREATE TABLE application_counters (
    environment Utf8 NOT NULL,
    counter_name Utf8 NOT NULL,
    last_value Uint64 NOT NULL,
    PRIMARY KEY (environment, counter_name)
);
