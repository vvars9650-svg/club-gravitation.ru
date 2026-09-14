-- FORM 2.2 Wave 1 Phase A schema preparation only.
-- DO NOT apply automatically. Existing legacy columns are intentionally retained.
ALTER TABLE applications ADD COLUMN profile_or_messenger_url Utf8;
ALTER TABLE applications ADD COLUMN what_participant_brings Utf8;
ALTER TABLE applications ADD COLUMN what_friends_value Utf8;
ALTER TABLE applications ADD COLUMN desired_connections_other Utf8;
ALTER TABLE applications ADD COLUMN acquaintance_methods Json;
ALTER TABLE applications ADD COLUMN acquaintance_methods_other Utf8;
