-- Apply only to the named TEST database after review; not run by CI.
-- Non-breaking lifecycle foundation. No existing column is removed or rewritten.
ALTER TABLE participants ADD COLUMN processing_blocked Bool;
ALTER TABLE participants ADD COLUMN processing_blocked_at Timestamp;
ALTER TABLE participants ADD COLUMN processing_block_reason Utf8;
ALTER TABLE participants ADD COLUMN processing_block_request_id Utf8;
