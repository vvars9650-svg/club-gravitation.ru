-- Wave 2 Phase A protected-photo schema preparation only. DO NOT apply automatically.
-- Additive only: historical Application rows and Participant rows remain unchanged.
ALTER TABLE applications ADD COLUMN photo_object_id Utf8;
ALTER TABLE participants ADD COLUMN current_photo_object_id Utf8;
ALTER TABLE participants ADD COLUMN photo_required_blocked Bool;

CREATE TABLE photo_objects (
    environment Utf8 NOT NULL,
    photo_object_id Utf8 NOT NULL,
    storage_key Utf8 NOT NULL,
    lifecycle_state Utf8 NOT NULL,
    owner_context_hash Utf8 NOT NULL,
    application_id Utf8,
    participant_id Utf8,
    detected_format Utf8 NOT NULL,
    mime_type Utf8 NOT NULL,
    byte_size Uint64 NOT NULL,
    created_at Timestamp NOT NULL,
    deleted_at Timestamp,
    PRIMARY KEY (environment, photo_object_id)
);
