-- Wave 1 Phase B additive participant foundation only. DO NOT apply automatically.
-- Existing lifecycle/decision columns and historical rows are retained.
ALTER TABLE participants ADD COLUMN participant_status Utf8;
ALTER TABLE participants ADD COLUMN profile_or_messenger_url Utf8;
ALTER TABLE participants ADD COLUMN occupation Utf8;
ALTER TABLE applications ADD COLUMN application_status Utf8;
ALTER TABLE applications ADD COLUMN decision Utf8;
