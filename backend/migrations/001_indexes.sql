-- GRAVITATION V3 backend indexes
-- Apply to YDB gravitation-v3 before deploying backend/src/index_v3.py.
-- Existing test data must not contain duplicate non-NULL phone values.

ALTER TABLE participants
ADD INDEX idx_participants_phone GLOBAL UNIQUE SYNC ON (phone);

ALTER TABLE participants
ADD INDEX idx_participants_email GLOBAL SYNC ON (email);

ALTER TABLE participants
ADD INDEX idx_participants_telegram GLOBAL SYNC ON (telegram);

ALTER TABLE applications
ADD INDEX idx_applications_participant GLOBAL SYNC ON (participant_id);

ALTER TABLE files
ADD INDEX idx_files_application GLOBAL SYNC ON (application_id);

ALTER TABLE consents
ADD INDEX idx_consents_application GLOBAL SYNC ON (application_id);
