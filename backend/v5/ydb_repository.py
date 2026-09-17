"""YDB repository for GRAVITATION V5 synthetic TEST."""

import hashlib
import json
import os
import threading
from datetime import datetime, timezone

try:
    import ydb
    import ydb.iam
except ImportError:  # unit-only imports must not silently create memory storage
    ydb = None

from .domain import CONSENT_VERSION, FORM_FIELDS, FORM_VERSION, MULTI_FIELDS, POLICY_VERSION, ids, phone as normalize_phone
from .participant_model import INITIAL_APPLICATION_STATUS, INITIAL_PARTICIPANT_STATUS
from .repository import DESTRUCTION_CLASSIFICATION, RepositoryConflict, RepositoryUnavailable
from .photo_contract import MAX_PHOTO_BYTES, validate_photo_object_id


ENVIRONMENT = "TEST"
LIFECYCLE_AUDIT_ACTIONS = (
    "processing_blocked",
    "destruction_requested",
    "destruction_planned",
)


class YdbRepository:
    def __init__(
        self,
        endpoint=None,
        database=None,
        consent_hash=None,
        driver=None,
    ):
        self.endpoint = endpoint or os.getenv("YDB_ENDPOINT")
        self.database = database or os.getenv("YDB_DATABASE")
        self.consent_hash = (
            consent_hash or os.getenv("V5_TEST_CONSENT_TEXT_HASH")
        )

        if not self.endpoint or not self.database or not self.consent_hash:
            raise RepositoryUnavailable(
                "missing_ydb_test_configuration"
            )

        if not self.consent_hash.startswith("TEST-"):
            raise RepositoryUnavailable(
                "consent_hash_must_be_test_marked"
            )

        if driver is None and ydb is None:
            raise RepositoryUnavailable("ydb_sdk_not_installed")

        try:
            if driver is None:
                driver = ydb.Driver(
                    endpoint=self.endpoint,
                    database=self.database,
                    credentials=ydb.iam.MetadataUrlCredentials(),
                )
                driver.wait(
                    fail_fast=True,
                    timeout=10,
                )

            self.driver = driver
            self.pool = ydb.QuerySessionPool(self.driver)
        except Exception as exc:
            if driver is not None:
                try:
                    driver.stop()
                except Exception:
                    pass
            raise RepositoryUnavailable(
                "ydb_initialization_failed"
            ) from exc

        self._close_lock = threading.Lock()
        self._closed = False

    def close(self):
        """Explicitly release SDK resources for local/tests lifecycle use."""
        with self._close_lock:
            if self._closed:
                return
            self._closed = True

            try:
                self.pool.stop()
            finally:
                self.driver.stop()

    @staticmethod
    def _rows(result_sets, index=0):
        if not result_sets or len(result_sets) <= index:
            return []
        return result_sets[index].rows or []

    @staticmethod
    def _row_value(row, name, default=None):
        if row is None:
            return default

        try:
            value = row[name]
        except (KeyError, TypeError):
            value = getattr(row, name, default)

        return default if value is None else value

    def get_idempotency(self, key):
        application_id, _ = ids(key)
        query = """
        DECLARE $environment AS Utf8;
        DECLARE $application_id AS Utf8;

        SELECT
            a.application_id AS application_id,
            a.application_number AS application_number,
            a.participant_id AS participant_id,
            source.payload_fingerprint AS payload_fingerprint,
            a.request_id AS request_id,
            source.duplicate_submission AS duplicate_submission
        FROM (
            SELECT COALESCE(k.application_id, candidate.application_id) AS application_id,
                   candidate.payload_fingerprint AS payload_fingerprint,
                   false AS duplicate_submission
            FROM applications AS candidate
            LEFT JOIN application_phone_keys AS k
            ON k.environment = candidate.environment
               AND k.normalized_phone = candidate.phone
            WHERE candidate.environment = $environment
              AND candidate.application_id = $application_id
            UNION ALL
            SELECT application_id, payload_fingerprint, true AS duplicate_submission
            FROM application_submission_keys
            WHERE environment = $environment AND submission_id = $application_id
        ) AS source
        INNER JOIN applications AS a
        ON a.environment = $environment AND a.application_id = source.application_id
        LIMIT 1;
        """

        result_sets = self.pool.execute_with_retries(
            query,
            {
                "$environment": ENVIRONMENT,
                "$application_id": application_id,
            },
            retry_settings=ydb.RetrySettings(
                max_retries=5,
                idempotent=True,
            ),
        )

        rows = self._rows(result_sets)
        if not rows:
            return None

        row = rows[0]

        return {
            "environment": ENVIRONMENT,
            "application_id": self._row_value(
                row, "application_id", application_id
            ),
            "application_number": self._row_value(row, "application_number", None),
            "participant_id": self._row_value(
                row, "participant_id", ""
            ),
            "payload_fingerprint": self._row_value(
                row, "payload_fingerprint", ""
            ),
            "request_id": self._row_value(
                row, "request_id", ""
            ),
            "duplicate_submission": self._row_value(
                row, "duplicate_submission", False
            ),
        }

    def create_photo_upload(self, photo_object_id, storage_key, owner_context_hash):
        validate_photo_object_id(photo_object_id)
        read_query = """
        DECLARE $environment AS Utf8;
        DECLARE $photo_object_id AS Utf8;
        SELECT photo_object_id FROM photo_objects
        WHERE environment = $environment AND photo_object_id = $photo_object_id;
        """
        write_query = """
        DECLARE $environment AS Utf8;
        DECLARE $photo_object_id AS Utf8;
        DECLARE $storage_key AS Utf8;
        DECLARE $owner_context_hash AS Utf8;
        INSERT INTO photo_objects (
            environment, photo_object_id, storage_key, lifecycle_state,
            owner_context_hash, detected_format, mime_type, byte_size, created_at
        ) VALUES (
            $environment, $photo_object_id, $storage_key, "PENDING_UPLOAD",
            $owner_context_hash, "", "", 0, CurrentUtcTimestamp()
        );
        """
        params = {
            "$environment": ENVIRONMENT,
            "$photo_object_id": photo_object_id,
            "$storage_key": storage_key,
            "$owner_context_hash": owner_context_hash,
        }

        def operation(session):
            tx = session.transaction(ydb.QuerySerializableReadWrite())
            with tx.execute(read_query, params) as stream:
                rows = self._rows(list(stream))
            if rows:
                tx.commit()
                raise RepositoryConflict("photo_object_id_conflict")
            with tx.execute(write_query, params, commit_tx=True) as stream:
                list(stream)
            return photo_object_id

        return self.pool.retry_operation_sync(
            operation, retry_settings=ydb.RetrySettings(max_retries=5, idempotent=True)
        )

    def get_photo_upload(self, photo_object_id):
        validate_photo_object_id(photo_object_id)
        query = """
        DECLARE $environment AS Utf8;
        DECLARE $photo_object_id AS Utf8;
        SELECT photo_object_id, storage_key, lifecycle_state, owner_context_hash,
               detected_format, mime_type, byte_size
        FROM photo_objects
        WHERE environment = $environment AND photo_object_id = $photo_object_id
        LIMIT 1;
        """
        result_sets = self.pool.execute_with_retries(
            query, {"$environment": ENVIRONMENT, "$photo_object_id": photo_object_id},
            retry_settings=ydb.RetrySettings(max_retries=5, idempotent=True),
        )
        rows = self._rows(result_sets)
        if not rows:
            return None
        row = rows[0]
        return {
            name: self._row_value(row, name, 0 if name == "byte_size" else "")
            for name in (
                "photo_object_id", "storage_key", "lifecycle_state",
                "owner_context_hash", "detected_format", "mime_type", "byte_size",
            )
        }

    def mark_photo_ready(self, photo_object_id, owner_context_hash, metadata):
        byte_size = metadata["byte_size"]
        if isinstance(byte_size, bool) or not isinstance(byte_size, int) or not 0 < byte_size <= MAX_PHOTO_BYTES:
            raise ValueError("invalid normalized photo byte size")
        read_query = """
        DECLARE $environment AS Utf8;
        DECLARE $photo_object_id AS Utf8;
        SELECT photo_object_id, storage_key, lifecycle_state, owner_context_hash,
               detected_format, mime_type, byte_size
        FROM photo_objects
        WHERE environment = $environment AND photo_object_id = $photo_object_id;
        """
        write_query = """
        DECLARE $environment AS Utf8;
        DECLARE $photo_object_id AS Utf8;
        DECLARE $detected_format AS Utf8;
        DECLARE $mime_type AS Utf8;
        DECLARE $byte_size AS Uint64;
        UPDATE photo_objects SET lifecycle_state = "READY",
            detected_format = $detected_format, mime_type = $mime_type,
            byte_size = $byte_size
        WHERE environment = $environment AND photo_object_id = $photo_object_id;
        """
        params = {
            "$environment": ENVIRONMENT,
            "$photo_object_id": photo_object_id,
            "$detected_format": metadata["detected_format"],
            "$mime_type": metadata["mime_type"],
            "$byte_size": ydb.TypedValue(byte_size, ydb.PrimitiveType.Uint64),
        }

        def operation(session):
            tx = session.transaction(ydb.QuerySerializableReadWrite())
            with tx.execute(read_query, params) as stream:
                rows = self._rows(list(stream))
            if not rows:
                tx.commit()
                raise RepositoryConflict("photo_reference_not_found")
            row = rows[0]
            if self._row_value(row, "owner_context_hash", "") != owner_context_hash:
                tx.commit()
                raise RepositoryConflict("photo_reference_not_owned")
            state = self._row_value(row, "lifecycle_state", "")
            if state == "READY":
                tx.commit()
                return {
                    name: self._row_value(row, name, 0 if name == "byte_size" else "")
                    for name in ("photo_object_id", "detected_format", "mime_type", "byte_size")
                }
            if state != "PENDING_UPLOAD":
                tx.commit()
                raise RepositoryConflict("photo_reference_not_available")
            with tx.execute(write_query, params, commit_tx=True) as stream:
                list(stream)
            return {"photo_object_id": photo_object_id, **metadata}

        return self.pool.retry_operation_sync(
            operation, retry_settings=ydb.RetrySettings(max_retries=5, idempotent=True)
        )

    def reject_photo_upload(self, photo_object_id, lifecycle_state):
        query = """
        DECLARE $environment AS Utf8;
        DECLARE $photo_object_id AS Utf8;
        DECLARE $lifecycle_state AS Utf8;
        UPDATE photo_objects SET lifecycle_state = $lifecycle_state
        WHERE environment = $environment AND photo_object_id = $photo_object_id
          AND lifecycle_state != "READY";
        """
        self.pool.execute_with_retries(
            query,
            {"$environment": ENVIRONMENT, "$photo_object_id": photo_object_id,
             "$lifecycle_state": lifecycle_state[:120]},
            retry_settings=ydb.RetrySettings(max_retries=5, idempotent=True),
        )
        return True

    def resolve_phone(self, phone):
        phone = normalize_phone(phone)
        query = """
        DECLARE $environment AS Utf8;
        DECLARE $phone AS Utf8;

        SELECT k.participant_id AS key_participant_id, p.participant_id AS participant_id,
               p.processing_blocked AS processing_blocked
        FROM participant_phone_keys AS k
        LEFT JOIN participants AS p
        ON k.environment = p.environment AND k.participant_id = p.participant_id
        WHERE k.environment = $environment
          AND k.phone = $phone
        LIMIT 1;
        """

        result_sets = self.pool.execute_with_retries(
            query,
            {
                "$environment": ENVIRONMENT,
                "$phone": phone,
            },
            retry_settings=ydb.RetrySettings(
                max_retries=5,
                idempotent=True,
            ),
        )

        rows = self._rows(result_sets)
        if not rows:
            return None

        if not self._row_value(rows[0], "participant_id", None):
            raise RepositoryConflict("phone_key_inconsistent")

        return self._row_value(
            rows[0],
            "participant_id",
            None,
        )

    def save(self, key, record):
        """
        Atomically:
        - checks idempotency;
        - resolves/reserves phone;
        - validates the exact READY photo and hashed ownership context;
        - creates a participant only when no phone key exists;
        - inserts immutable application;
        - attaches the photo and initializes a missing participant current photo;
        - inserts consent evidence;
        - writes technical log;
        - writes audit event.

        Serializable conflicts are retried by YDB SDK.
        """

        application_id, _ = ids(key)

        # Server-owned values override anything supplied upstream.
        record["environment"] = ENVIRONMENT
        record["application_id"] = application_id
        record["consent"]["application_id"] = application_id
        record["consent"]["consent_text_hash"] = self.consent_hash
        record["consent"]["form_version"] = FORM_VERSION
        record["consent"]["granted"] = True
        record["consent"]["source"] = "website"

        form = record["form"]
        phone = form["phone"]
        photo_object_id = validate_photo_object_id(form.get("photo_object_id"))
        owner_context_hash = hashlib.sha256(str(key).encode("utf-8")).hexdigest()

        log_id = "LOG-" + hashlib.sha256(
            f"{ENVIRONMENT}:{application_id}:created".encode("utf-8")
        ).hexdigest()[:24]

        audit_id = "AUD-" + hashlib.sha256(
            f"{ENVIRONMENT}:{application_id}:created".encode("utf-8")
        ).hexdigest()[:24]

        intake_read_query = """
        DECLARE $environment AS Utf8;
        DECLARE $application_id AS Utf8;
        DECLARE $proposed_participant_id AS Utf8;
        DECLARE $phone AS Utf8;
        DECLARE $email AS Utf8;
        DECLARE $profile_or_messenger_url AS Utf8;

        SELECT
            "application" AS record_type,
            application_id,
            "" AS key_participant_id,
            participant_id,
            payload_fingerprint,
            false AS processing_blocked,
            "" AS current_photo_object_id,
            COALESCE(application_number, CAST(0 AS Uint64)) AS application_number
        FROM applications
        WHERE environment = $environment
          AND application_id = $application_id
        UNION ALL
        SELECT
            "submission" AS record_type,
            submission_id AS application_id,
            "" AS key_participant_id,
            participant_id,
            payload_fingerprint,
            false AS processing_blocked,
            "" AS current_photo_object_id,
            CAST(0 AS Uint64) AS application_number
        FROM application_submission_keys
        WHERE environment = $environment
          AND submission_id = $application_id
        UNION ALL
        SELECT
            "phone" AS record_type,
            "" AS application_id,
            k.participant_id AS key_participant_id,
            p.participant_id AS participant_id,
            "" AS payload_fingerprint,
            p.processing_blocked AS processing_blocked,
            COALESCE(p.current_photo_object_id, "") AS current_photo_object_id,
            CAST(0 AS Uint64) AS application_number
        FROM participant_phone_keys AS k
        LEFT JOIN participants AS p
        ON k.environment = p.environment AND k.participant_id = p.participant_id
        WHERE k.environment = $environment
          AND k.phone = $phone
        UNION ALL
        SELECT
            "candidate" AS record_type,
            "" AS application_id,
            "" AS key_participant_id,
            participant_id,
            "" AS payload_fingerprint,
            processing_blocked,
            COALESCE(current_photo_object_id, "") AS current_photo_object_id,
            CAST(0 AS Uint64) AS application_number
        FROM participants
        WHERE environment = $environment
          AND participant_id = $proposed_participant_id
        UNION ALL
        SELECT
            "phone_application" AS record_type,
            application_id,
            "" AS key_participant_id,
            participant_id,
            payload_fingerprint,
            false AS processing_blocked,
            "" AS current_photo_object_id,
            COALESCE(application_number, CAST(0 AS Uint64)) AS application_number
        FROM applications
        WHERE environment = $environment
          AND phone = $phone;
        UNION ALL
        SELECT "secondary_email" AS record_type, application_id, "" AS key_participant_id,
               participant_id, "" AS payload_fingerprint, false AS processing_blocked,
               "" AS current_photo_object_id, CAST(0 AS Uint64) AS application_number
        FROM applications
        WHERE environment = $environment AND email = $email AND phone != $phone
        UNION ALL
        SELECT "secondary_profile" AS record_type, application_id, "" AS key_participant_id,
               participant_id, "" AS payload_fingerprint, false AS processing_blocked,
               "" AS current_photo_object_id, CAST(0 AS Uint64) AS application_number
        FROM applications
        WHERE environment = $environment AND profile_or_messenger_url = $profile_or_messenger_url AND profile_or_messenger_url != "" AND phone != $phone;
        """

        photo_read_query = """
        DECLARE $environment AS Utf8;
        DECLARE $photo_object_id AS Utf8;

        SELECT
            photo_object_id,
            owner_context_hash,
            lifecycle_state,
            application_id,
            participant_id
        FROM photo_objects
        WHERE environment = $environment
          AND photo_object_id = $photo_object_id
        LIMIT 1;
        """

        counter_read_query = """
        DECLARE $environment AS Utf8;
        SELECT last_value
        FROM application_counters
        WHERE environment = $environment
          AND counter_name = "applications"
        LIMIT 1;
        """

        def transaction_body(session):
            tx = session.transaction(ydb.QuerySerializableReadWrite())

            with tx.execute(
                intake_read_query,
                {
                    "$environment": ENVIRONMENT,
                    "$application_id": application_id,
                    "$proposed_participant_id": record["participant_id"],
                    "$phone": phone,
                    "$email": record["form"].get("email", ""),
                    "$profile_or_messenger_url": record["form"].get("profile_or_messenger_url", ""),
                },
            ) as result_stream:
                intake_result_sets = list(result_stream)

            intake_rows = self._rows(intake_result_sets, 0)
            application_rows = [
                row for row in intake_rows
                if self._row_value(row, "record_type", "") in ("application", "submission")
                or (
                    not self._row_value(row, "record_type", "")
                    and self._row_value(row, "application_id", "")
                )
            ]
            existing_application_rows = [
                row for row in intake_rows
                if self._row_value(row, "record_type", "") == "phone_application"
            ]
            existing_application_rows.sort(key=lambda row: (
                self._row_value(row, "application_number", 0) or 0,
                self._row_value(row, "application_id", ""),
            ))
            secondary_rows = [row for row in intake_rows if self._row_value(row, "record_type", "") in ("secondary_email", "secondary_profile")]
            phone_rows = [
                row for row in intake_rows
                if not self._row_value(row, "application_id", "")
                and self._row_value(row, "key_participant_id", "")
            ]
            candidate_rows = [
                row for row in intake_rows
                if self._row_value(row, "record_type", "") == "candidate"
            ]

            if application_rows:
                tx.commit()
                return False

            with tx.execute(
                photo_read_query,
                {
                    "$environment": ENVIRONMENT,
                    "$photo_object_id": photo_object_id,
                },
            ) as result_stream:
                photo_result_sets = list(result_stream)

            photo_rows = self._rows(photo_result_sets, 0)
            if not photo_rows:
                tx.commit()
                raise RepositoryConflict("photo_reference_not_found")
            photo = photo_rows[0]
            if self._row_value(photo, "owner_context_hash", "") != owner_context_hash:
                tx.commit()
                raise RepositoryConflict("photo_reference_not_owned")
            if (
                self._row_value(photo, "lifecycle_state", "") != "READY"
                or self._row_value(photo, "application_id", None) is not None
                or self._row_value(photo, "participant_id", None) is not None
            ):
                tx.commit()
                raise RepositoryConflict("photo_reference_not_available")

            existing_participant_id = None

            if phone_rows:
                if not self._row_value(phone_rows[0], "participant_id", None):
                    tx.commit()
                    raise RepositoryConflict("phone_key_inconsistent")
                existing_participant_id = self._row_value(
                    phone_rows[0],
                    "participant_id",
                    None,
                )

                if self._row_value(phone_rows[0], "processing_blocked", False):
                    tx.commit()
                    raise RepositoryUnavailable("processing_blocked")

            if not existing_participant_id and candidate_rows:
                tx.commit()
                raise RepositoryConflict("participant_id_conflict")

            if existing_application_rows:
                original = existing_application_rows[0]
                original_application_id = self._row_value(original, "application_id", "")
                original_participant_id = self._row_value(original, "participant_id", existing_participant_id or "")
                if not original_application_id or not original_participant_id:
                    tx.commit()
                    raise RepositoryConflict("application_phone_key_inconsistent")
                duplicate_audit_id = "AUD-" + hashlib.sha256(
                    f"{ENVIRONMENT}:{application_id}:duplicate".encode("utf-8")
                ).hexdigest()[:24]
                duplicate_log_id = "LOG-" + hashlib.sha256(
                    f"{ENVIRONMENT}:{application_id}:duplicate".encode("utf-8")
                ).hexdigest()[:24]
                duplicate_write_query = """
                DECLARE $environment AS Utf8;
                DECLARE $submission_id AS Utf8;
                DECLARE $application_id AS Utf8;
                DECLARE $participant_id AS Utf8;
                DECLARE $payload_fingerprint AS Utf8;
                DECLARE $request_id AS Utf8;
                DECLARE $phone AS Utf8;
                DECLARE $photo_object_id AS Utf8;
                DECLARE $audit_id AS Utf8;
                DECLARE $log_id AS Utf8;

                UPSERT INTO application_phone_keys (
                    environment, normalized_phone, application_id,
                    participant_id, created_at
                ) VALUES (
                    $environment, $phone, $application_id,
                    $participant_id, CurrentUtcTimestamp()
                );
                INSERT INTO application_submission_keys (
                    environment, submission_id, application_id, participant_id,
                    payload_fingerprint, outcome, created_at
                ) VALUES (
                    $environment, $submission_id, $application_id, $participant_id,
                    $payload_fingerprint, "duplicate", CurrentUtcTimestamp()
                );
                UPDATE applications
                SET duplicate_attempt_count = COALESCE(duplicate_attempt_count, 0) + 1,
                    last_duplicate_at = CurrentUtcTimestamp(),
                    last_duplicate_match_basis = "normalized_phone"
                WHERE environment = $environment AND application_id = $application_id;
                UPDATE photo_objects
                SET lifecycle_state = "DELETE_SCHEDULED"
                WHERE environment = $environment
                  AND photo_object_id = $photo_object_id
                  AND lifecycle_state = "READY";
                INSERT INTO technical_logs (
                    environment, log_id, request_id, timestamp, application_id,
                    operation, status, error_code
                ) VALUES (
                    $environment, $log_id, $request_id, CurrentUtcTimestamp(),
                    $application_id, "duplicate_submission", "ok", ""
                );
                INSERT INTO audit_log (
                    environment, audit_id, timestamp, request_id, application_id,
                    participant_id, action
                ) VALUES (
                    $environment, $audit_id, CurrentUtcTimestamp(), $request_id,
                    $application_id, $participant_id,
                    "duplicate_submission|basis=normalized_phone"
                );
                """
                duplicate_params = {
                    "$environment": ENVIRONMENT,
                    "$submission_id": application_id,
                    "$application_id": original_application_id,
                    "$participant_id": original_participant_id,
                    "$payload_fingerprint": record["payload_fingerprint"],
                    "$request_id": record["request_id"],
                    "$phone": phone,
                    "$photo_object_id": photo_object_id,
                    "$audit_id": duplicate_audit_id,
                    "$log_id": duplicate_log_id,
                }
                with tx.execute(duplicate_write_query, duplicate_params, commit_tx=True) as result_stream:
                    for _ in result_stream:
                        pass
                return {
                    "duplicate_submission": True,
                    "application_id": original_application_id,
                    "application_number": self._row_value(original, "application_number", None),
                    "participant_id": original_participant_id,
                }

            secondary_basis = ""
            secondary_reference = ""
            if secondary_rows:
                secondary_basis = "email" if self._row_value(secondary_rows[0], "record_type", "") == "secondary_email" else "profile_or_messenger"
                secondary_reference = self._row_value(secondary_rows[0], "application_id", "")

            with tx.execute(
                counter_read_query,
                {"$environment": ENVIRONMENT},
            ) as result_stream:
                counter_result_sets = list(result_stream)
            counter_rows = self._rows(counter_result_sets, 0)
            last_value = self._row_value(counter_rows[0], "last_value", 0) if counter_rows else 0
            if isinstance(last_value, bool) or not isinstance(last_value, int) or last_value < 0:
                tx.commit()
                raise RepositoryConflict("application_counter_invalid")
            application_number = last_value + 1

            if existing_participant_id:
                participant_id = existing_participant_id
                if self._row_value(phone_rows[0], "current_photo_object_id", ""):
                    participant_write = ""
                else:
                    participant_write = """
                    UPDATE participants
                    SET current_photo_object_id = $photo_object_id,
                        photo_required_blocked = false,
                        updated_at = CurrentUtcTimestamp()
                    WHERE environment = $environment
                      AND participant_id = $participant_id;
                    """
            else:
                participant_id = record["participant_id"]

                participant_write = """
                INSERT INTO participants (
                    environment,
                    participant_id,
                    phone,
                    full_name,
                    age,
                    gender,
                    city,
                    visit_krasnodar,
                    telegram,
                    email,
                    preferred_contact,
                    profile_or_messenger_url,
                    public_profile_url,
                    occupation,
                    participant_status,
                    lifecycle_status,
                    current_photo_object_id,
                    photo_required_blocked,
                    created_at,
                    updated_at
                ) VALUES (
                    $environment,
                    $participant_id,
                    $phone,
                    $full_name,
                    $age,
                    $gender,
                    $city,
                    $visit_krasnodar,
                    $telegram,
                    $email,
                    $preferred_contact,
                    $profile_or_messenger_url,
                    $public_profile_url,
                    $occupation,
                    $participant_status,
                    "Новая заявка",
                    $photo_object_id,
                    false,
                    CurrentUtcTimestamp(),
                    CurrentUtcTimestamp()
                );

                INSERT INTO participant_phone_keys (
                    environment,
                    phone,
                    participant_id,
                    created_at
                ) VALUES (
                    $environment,
                    $phone,
                    $participant_id,
                    CurrentUtcTimestamp()
                );
                """

            record["participant_id"] = participant_id
            record["consent"]["participant_id"] = participant_id
            record["photo_object_id"] = photo_object_id
            record["application_status"] = INITIAL_APPLICATION_STATUS
            record["decision"] = ""

            write_query = (
                """
                DECLARE $environment AS Utf8;
                DECLARE $participant_id AS Utf8;
                DECLARE $application_id AS Utf8;
                DECLARE $application_number AS Uint64;
                DECLARE $consent_id AS Utf8;
                DECLARE $request_id AS Utf8;
                DECLARE $payload_fingerprint AS Utf8;
                DECLARE $photo_object_id AS Utf8;
                DECLARE $owner_context_hash AS Utf8;

                DECLARE $full_name AS Utf8;
                DECLARE $age AS Int32;
                DECLARE $gender AS Utf8;
                DECLARE $city AS Utf8;
                DECLARE $visit_krasnodar AS Utf8;
                DECLARE $phone AS Utf8;
                DECLARE $telegram AS Utf8;
                DECLARE $email AS Utf8;
                DECLARE $preferred_contact AS Utf8;
                DECLARE $profile_or_messenger_url AS Utf8;
                DECLARE $public_profile_url AS Utf8;
                DECLARE $participant_status AS Utf8;
                DECLARE $application_status AS Utf8;
                DECLARE $decision AS Utf8;

                DECLARE $occupation AS Utf8;
                DECLARE $life_outside_work AS Utf8;
                DECLARE $what_interested AS Utf8;
                DECLARE $what_participant_brings AS Utf8;
                DECLARE $what_friends_value AS Utf8;
                DECLARE $desired_connections AS Json;
                DECLARE $desired_connections_other AS Utf8;
                DECLARE $values_in_people AS Utf8;
                DECLARE $barriers_to_meeting AS Utf8;
                DECLARE $acquaintance_methods AS Json;
                DECLARE $acquaintance_methods_other AS Utf8;
                DECLARE $return_reason AS Utf8;
                DECLARE $source AS Utf8;

                DECLARE $consent_type AS Utf8;
                DECLARE $consent_version AS Utf8;
                DECLARE $policy_version AS Utf8;
                DECLARE $form_version AS Utf8;
                DECLARE $consent_text_hash AS Utf8;
                DECLARE $consent_source AS Utf8;

                DECLARE $log_id AS Utf8;
                DECLARE $audit_id AS Utf8;
                """
                + participant_write
                + """
                INSERT INTO application_phone_keys (
                    environment,
                    normalized_phone,
                    application_id,
                    participant_id,
                    created_at
                ) VALUES (
                    $environment,
                    $phone,
                    $application_id,
                    $participant_id,
                    CurrentUtcTimestamp()
                );

                UPSERT INTO application_counters (
                    environment,
                    counter_name,
                    last_value
                ) VALUES (
                    $environment,
                    "applications",
                    $application_number
                );

                INSERT INTO applications (
                    environment,
                    application_id,
                    application_number,
                    participant_id,
                    submitted_at,
                    payload_fingerprint,
                    form_version,
                    request_id,
                    application_status,
                    decision,
                    owner,
                    priority,
                    next_action,
                    next_contact_at,
                    internal_comment,
                    duplicate_attempt_count,
                    last_duplicate_match_basis,
                    possible_duplicate_count,
                    possible_duplicate_match_basis,
                    possible_duplicate_application_id,
                    photo_object_id,
                    full_name,
                    age,
                    gender,
                    city,
                    visit_krasnodar,
                    phone,
                    email,
                    preferred_contact,
                    profile_or_messenger_url,
                    public_profile_url,
                    occupation,
                    life_outside_work,
                    what_interested,
                    what_participant_brings,
                    what_friends_value,
                    desired_connections,
                    desired_connections_other,
                    values_in_people,
                    barriers_to_meeting,
                    acquaintance_methods,
                    acquaintance_methods_other,
                    return_reason,
                    source
                ) VALUES (
                    $environment,
                    $application_id,
                    $application_number,
                    $participant_id,
                    CurrentUtcTimestamp(),
                    $payload_fingerprint,
                    $form_version,
                    $request_id,
                    $application_status,
                    $decision,
                    "",
                    "",
                    "Рассмотреть",
                    NULL,
                    "",
                    0,
                    "",
                    CASE WHEN $possible_duplicate_application_id = "" THEN 0 ELSE 1 END,
                    $possible_duplicate_match_basis,
                    $possible_duplicate_application_id,
                    $photo_object_id,
                    $full_name,
                    $age,
                    $gender,
                    $city,
                    $visit_krasnodar,
                    $phone,
                    $email,
                    $preferred_contact,
                    $profile_or_messenger_url,
                    $public_profile_url,
                    $occupation,
                    $life_outside_work,
                    $what_interested,
                    $what_participant_brings,
                    $what_friends_value,
                    $desired_connections,
                    $desired_connections_other,
                    $values_in_people,
                    $barriers_to_meeting,
                    $acquaintance_methods,
                    $acquaintance_methods_other,
                    $return_reason,
                    $source
                );

                UPDATE photo_objects
                SET lifecycle_state = "ATTACHED",
                    application_id = $application_id,
                    participant_id = $participant_id
                WHERE environment = $environment
                  AND photo_object_id = $photo_object_id
                  AND owner_context_hash = $owner_context_hash
                  AND lifecycle_state = "READY"
                  AND application_id IS NULL
                  AND participant_id IS NULL;

                INSERT INTO consents (
                    environment,
                    consent_id,
                    participant_id,
                    application_id,
                    consent_type,
                    consent_version,
                    policy_version,
                    form_version,
                    consent_text_hash,
                    granted,
                    granted_at,
                    source,
                    request_id
                ) VALUES (
                    $environment,
                    $consent_id,
                    $participant_id,
                    $application_id,
                    $consent_type,
                    $consent_version,
                    $policy_version,
                    $form_version,
                    $consent_text_hash,
                    true,
                    CurrentUtcTimestamp(),
                    $consent_source,
                    $request_id
                );

                INSERT INTO technical_logs (
                    environment,
                    log_id,
                    request_id,
                    timestamp,
                    application_id,
                    operation,
                    status,
                    error_code
                ) VALUES (
                    $environment,
                    $log_id,
                    $request_id,
                    CurrentUtcTimestamp(),
                    $application_id,
                    "application_created",
                    "ok",
                    ""
                );

                INSERT INTO audit_log (
                    environment,
                    audit_id,
                    timestamp,
                    request_id,
                    application_id,
                    participant_id,
                    action
                ) VALUES (
                    $environment,
                    $audit_id,
                    CurrentUtcTimestamp(),
                    $request_id,
                    $application_id,
                    $participant_id,
                    "application_created"
                );
                """
            )

            params = {
                "$environment": ENVIRONMENT,
                "$participant_id": participant_id,
                "$application_id": application_id,
                "$application_number": ydb.TypedValue(
                    application_number,
                    ydb.PrimitiveType.Uint64,
                ),
                "$consent_id": record["consent_id"],
                "$request_id": record["request_id"],
                "$payload_fingerprint": record["payload_fingerprint"],
                "$photo_object_id": photo_object_id,
                "$owner_context_hash": owner_context_hash,
                "$possible_duplicate_match_basis": secondary_basis,
                "$possible_duplicate_application_id": secondary_reference,

                "$full_name": form["full_name"],
                "$age": ydb.TypedValue(
                    form["age"],
                    ydb.PrimitiveType.Int32,
                ),
                "$gender": form["gender"],
                "$city": form["city"],
                "$visit_krasnodar": form["visit_krasnodar"],
                "$phone": form["phone"],
                "$telegram": form["profile_or_messenger_url"],
                "$email": form["email"],
                "$preferred_contact": form["preferred_contact"],
                "$profile_or_messenger_url": form["profile_or_messenger_url"],
                "$public_profile_url": form["public_profile_url"],
                "$participant_status": INITIAL_PARTICIPANT_STATUS,
                "$application_status": INITIAL_APPLICATION_STATUS,
                "$decision": "",

                "$occupation": form["occupation"],
                "$life_outside_work": form["life_outside_work"],
                "$what_interested": form["what_interested"],
                "$what_participant_brings": form["what_participant_brings"],
                "$what_friends_value": form["what_friends_value"],
                "$desired_connections": ydb.TypedValue(
                    json.dumps(
                        form["desired_connections"],
                        ensure_ascii=False,
                    ),
                    ydb.PrimitiveType.Json,
                ),
                "$desired_connections_other": form["desired_connections_other"],
                "$values_in_people": form["values_in_people"],
                "$barriers_to_meeting": form["barriers_to_meeting"],
                "$acquaintance_methods": ydb.TypedValue(
                    json.dumps(form["acquaintance_methods"], ensure_ascii=False),
                    ydb.PrimitiveType.Json,
                ),
                "$acquaintance_methods_other": form["acquaintance_methods_other"],
                "$return_reason": form["return_reason"],
                "$source": form["source"],

                "$consent_type": "personal_data_application",
                "$consent_version": CONSENT_VERSION,
                "$policy_version": POLICY_VERSION,
                "$form_version": FORM_VERSION,
                "$consent_text_hash": self.consent_hash,
                "$consent_source": "website",

                "$log_id": log_id,
                "$audit_id": audit_id,
            }

            with tx.execute(
                write_query,
                params,
                commit_tx=True,
            ) as result_stream:
                for _ in result_stream:
                    pass
            record["application_number"] = application_number
            return True

        outcome = self.pool.retry_operation_sync(
            transaction_body,
            retry_settings=ydb.RetrySettings(
                max_retries=5,
                idempotent=True,
            ),
        )
        if isinstance(outcome, dict) and outcome.get("duplicate_submission"):
            record.update(outcome)
            return True
        return outcome

    def find_participant(self, participant_id):
        query = """
        DECLARE $environment AS Utf8;
        DECLARE $participant_id AS Utf8;

        SELECT
            participant_id,
            participant_status,
            lifecycle_status,
            owner,
            priority,
            next_action,
            next_contact_at,
            decision
            ,processing_blocked,
            processing_blocked_at,
            processing_block_reason,
            processing_block_request_id
        FROM participants
        WHERE environment = $environment
          AND participant_id = $participant_id
        LIMIT 1;
        """

        result_sets = self.pool.execute_with_retries(
            query,
            {
                "$environment": ENVIRONMENT,
                "$participant_id": participant_id,
            },
            retry_settings=ydb.RetrySettings(
                max_retries=5,
                idempotent=True,
            ),
        )

        rows = self._rows(result_sets)
        if not rows:
            return None

        row = rows[0]

        return {
            "participant_id": self._row_value(
                row, "participant_id", ""
            ),
            "participant_status": self._row_value(row, "participant_status", ""),
            "lifecycle_status": self._row_value(
                row, "lifecycle_status", ""
            ),
            "owner": self._row_value(row, "owner", ""),
            "priority": self._row_value(row, "priority", ""),
            "next_action": self._row_value(
                row, "next_action", ""
            ),
            "next_contact_at": self._row_value(
                row, "next_contact_at", None
            ),
            "decision": self._row_value(
                row, "decision", ""
            ),
            "processing_blocked": self._row_value(row, "processing_blocked", False),
            "processing_state": "Заблокирована" if self._row_value(row, "processing_blocked", False) else "Разрешена",
            "processing_blocked_at": self._row_value(row, "processing_blocked_at", None),
            "processing_block_reason": self._row_value(row, "processing_block_reason", ""),
            "processing_block_request_id": self._row_value(row, "processing_block_request_id", ""),
        }

    def applied_migrations(self):
        query = """
        DECLARE $environment AS Utf8;
        SELECT migration_id
        FROM schema_migrations
        WHERE environment = $environment
        ORDER BY migration_id;
        """
        result_sets = self.pool.execute_with_retries(
            query,
            {"$environment": ENVIRONMENT},
            retry_settings=ydb.RetrySettings(max_retries=5, idempotent=True),
        )
        return tuple(
            self._row_value(row, "migration_id", "")
            for row in self._rows(result_sets)
        )

    def register_migration(self, migration_id):
        from .migration_ledger import validate_migration_id
        validate_migration_id(migration_id)
        read_query = """
        DECLARE $environment AS Utf8;
        DECLARE $migration_id AS Utf8;
        SELECT migration_id
        FROM schema_migrations
        WHERE environment = $environment AND migration_id = $migration_id;
        """
        write_query = """
        DECLARE $environment AS Utf8;
        DECLARE $migration_id AS Utf8;
        INSERT INTO schema_migrations (environment, migration_id, applied_at)
        VALUES ($environment, $migration_id, CurrentUtcTimestamp());
        """
        params = {"$environment": ENVIRONMENT, "$migration_id": migration_id}

        def operation(session):
            tx = session.transaction(ydb.QuerySerializableReadWrite())
            with tx.execute(read_query, params) as stream:
                rows = self._rows(list(stream))
            if rows:
                tx.commit()
                return False
            with tx.execute(write_query, params, commit_tx=True) as stream:
                for _ in stream:
                    pass
            return True

        return self.pool.retry_operation_sync(
            operation,
            retry_settings=ydb.RetrySettings(max_retries=5, idempotent=True),
        )

    def find_participant_by_phone(self, phone):
        """Internal subject lookup using the authoritative phone normalizer."""
        participant_id = self.resolve_phone(phone)
        return self.find_participant(participant_id) if participant_id else None

    def find_application(self, application_id):
        """Internal application-to-subject locate; never exposed as a public route."""
        query = """
        DECLARE $environment AS Utf8;
        DECLARE $application_id AS Utf8;
        SELECT application_id, participant_id, request_id
        FROM applications
        WHERE environment = $environment AND application_id = $application_id
        LIMIT 1;
        """
        result_sets = self.pool.execute_with_retries(query, {"$environment": ENVIRONMENT, "$application_id": application_id}, retry_settings=ydb.RetrySettings(max_retries=5, idempotent=True))
        rows = self._rows(result_sets)
        if not rows:
            return None
        row = rows[0]
        return {name: self._row_value(row, name, "") for name in ("application_id", "participant_id", "request_id")}

    def list_admin_applications(self, filters=None, sort="submitted_at", order="desc"):
        """Read-only TEST list for the protected Admin API."""
        filters = filters or {}
        direction = "ASC" if order == "asc" else "DESC"
        sort_columns = {
            "submitted_at": "submitted_at",
            "application_number": "application_number",
            "full_name": "full_name",
            "age": "age",
            "city": "city",
            "status": "application_status",
            "priority": "priority",
            "next_contact_at": "next_contact_at",
        }
        if sort not in sort_columns:
            raise RepositoryUnavailable("invalid_admin_sort")
        query = """
        DECLARE $environment AS Utf8;
        DECLARE $q AS Utf8;
        DECLARE $status AS Utf8;
        DECLARE $owner AS Utf8;
        DECLARE $priority AS Utf8;
        DECLARE $decision AS Utf8;
        SELECT a.application_id AS application_id,
               a.application_number AS application_number,
               a.participant_id AS participant_id,
               a.submitted_at AS submitted_at,
               a.full_name AS full_name,
               a.age AS age,
               a.city AS city,
               a.phone AS phone,
               a.profile_or_messenger_url AS profile_or_messenger_url,
               a.preferred_contact AS preferred_contact,
               a.application_status AS application_status,
               a.owner AS owner,
               a.priority AS priority,
               a.next_action AS next_action,
               a.next_contact_at AS next_contact_at,
               a.decision AS decision,
               COALESCE(a.duplicate_attempt_count, 0) AS duplicate_attempt_count,
               a.last_duplicate_at AS last_duplicate_at,
               a.last_duplicate_match_basis AS last_duplicate_match_basis,
               COALESCE(a.possible_duplicate_count, 0) AS possible_duplicate_count,
               a.possible_duplicate_match_basis AS possible_duplicate_match_basis,
               a.possible_duplicate_application_id AS possible_duplicate_application_id
        FROM applications AS a
        INNER JOIN application_phone_keys AS k
        ON k.environment = a.environment AND k.application_id = a.application_id
        WHERE a.environment = $environment
          AND (
              $q = ""
              OR Unicode::Find(Unicode::ToLower(COALESCE(a.full_name, "")), $q) IS NOT NULL
              OR Unicode::Find(Unicode::ToLower(COALESCE(a.city, "")), $q) IS NOT NULL
              OR Unicode::Find(Unicode::ToLower(COALESCE(a.phone, "")), $q) IS NOT NULL
              OR Unicode::Find(Unicode::ToLower(COALESCE(a.email, "")), $q) IS NOT NULL
              OR Unicode::Find(Unicode::ToLower(COALESCE(a.profile_or_messenger_url, "")), $q) IS NOT NULL
              OR Unicode::Find(Unicode::ToLower(COALESCE(a.preferred_contact, "")), $q) IS NOT NULL
              OR Unicode::Find(Unicode::ToLower(COALESCE(a.application_status, "")), $q) IS NOT NULL
              OR Unicode::Find(Unicode::ToLower(COALESCE(a.owner, "")), $q) IS NOT NULL
              OR Unicode::Find(Unicode::ToLower(COALESCE(a.priority, "")), $q) IS NOT NULL
              OR Unicode::Find(Unicode::ToLower(COALESCE(a.next_action, "")), $q) IS NOT NULL
              OR Unicode::Find(Unicode::ToLower(COALESCE(a.decision, "")), $q) IS NOT NULL
              OR CAST(a.age AS Utf8) LIKE "%" || $q || "%"
              OR CAST(a.application_number AS Utf8) LIKE "%" || $q || "%"
          )
          AND ($status = "" OR a.application_status = $status)
          AND ($owner = "" OR a.owner = $owner)
          AND ($priority = "" OR a.priority = $priority)
          AND ($decision = "" OR a.decision = $decision)
        ORDER BY """ + sort_columns[sort] + " " + direction + ";"
        result_sets = self.pool.execute_with_retries(query, {
            "$environment": ENVIRONMENT,
            "$q": str(filters.get("q", "")).lower(), "$status": filters.get("status", ""),
            "$owner": filters.get("owner", ""), "$priority": filters.get("priority", ""),
            "$decision": filters.get("decision", ""),
        }, retry_settings=ydb.RetrySettings(max_retries=5, idempotent=True))
        rows = []
        for row in self._rows(result_sets):
            item = {name: self._row_value(row, name, "") for name in (
                "application_id", "application_number", "participant_id", "submitted_at",
                "full_name", "age", "city", "phone", "profile_or_messenger_url",
                "preferred_contact", "owner", "priority", "next_action",
                "next_contact_at", "decision", "duplicate_attempt_count",
                "last_duplicate_at", "last_duplicate_match_basis",
                "email", "possible_duplicate_count", "possible_duplicate_match_basis",
                "possible_duplicate_application_id",
            )}
            item["status"] = self._row_value(row, "application_status", INITIAL_APPLICATION_STATUS)
            item["environment"] = ENVIRONMENT
            rows.append(item)
        return rows

    def get_admin_application(self, application_id):
        query = """
        DECLARE $environment AS Utf8; DECLARE $application_id AS Utf8;
        SELECT application_id, application_number, participant_id, submitted_at,
               form_version, application_status, owner, priority, next_action,
               next_contact_at, decision, internal_comment,
               COALESCE(duplicate_attempt_count, 0) AS duplicate_attempt_count,
               last_duplicate_at, last_duplicate_match_basis,
               COALESCE(possible_duplicate_count, 0) AS possible_duplicate_count,
               possible_duplicate_match_basis, possible_duplicate_application_id,
               request_id, full_name, age, gender, city,
               visit_krasnodar, phone, email, preferred_contact, profile_or_messenger_url,
               public_profile_url, occupation, life_outside_work, what_interested,
               what_participant_brings, what_friends_value, desired_connections,
               desired_connections_other, values_in_people, barriers_to_meeting,
               acquaintance_methods, acquaintance_methods_other, return_reason, source,
               photo_object_id
        FROM applications WHERE environment = $environment AND application_id = $application_id;
        SELECT consent_id, application_id, consent_type, consent_version, policy_version, form_version,
               consent_text_hash, granted, granted_at, source, request_id
        FROM consents WHERE environment = $environment AND application_id = $application_id;
        SELECT timestamp, request_id, application_id, participant_id, action
        FROM audit_log
        WHERE environment = $environment AND application_id = $application_id
        ORDER BY timestamp DESC;
        """
        result_sets = self.pool.execute_with_retries(query, {"$environment": ENVIRONMENT, "$application_id": application_id}, retry_settings=ydb.RetrySettings(max_retries=5, idempotent=True))
        application_rows = self._rows(result_sets, 0)
        if not application_rows:
            return None
        row = application_rows[0]
        application = {name: self._row_value(row, name, "") for name in (
            "application_id", "application_number", "participant_id", "submitted_at",
            "owner", "priority", "next_action", "next_contact_at", "decision",
            "internal_comment", "duplicate_attempt_count", "last_duplicate_at",
            "last_duplicate_match_basis",
        )}
        application["status"] = self._row_value(row, "application_status", INITIAL_APPLICATION_STATUS)
        application["form"] = {name: self._row_value(row, name, [] if name in MULTI_FIELDS else "") for name in FORM_FIELDS}
        consent_fields = ("consent_id", "application_id", "consent_type", "consent_version", "policy_version", "form_version", "consent_text_hash", "granted", "granted_at", "source", "request_id")
        event_fields = ("timestamp", "request_id", "application_id", "participant_id", "action")
        return {
            "environment": ENVIRONMENT,
            "application": application,
            "consents": [{name: self._row_value(item, name, "") for name in consent_fields} for item in self._rows(result_sets, 1)],
            "events": [{name: self._row_value(item, name, "") for name in event_fields} for item in self._rows(result_sets, 2)],
        }

    def update_admin_application(self, application_id, changes, actor, request_id):
        """Atomic operational-only update plus minimal audit evidence."""
        from .admin import OPERATIONAL_FIELDS, validate_workflow
        names = tuple(name for name in changes if name in OPERATIONAL_FIELDS)
        if not names:
            return None
        card = self.get_admin_application(application_id)
        if not card:
            return None
        current = card["application"]
        participant_id = current["participant_id"]
        validate_workflow(
            changes.get("decision") or current.get("status", INITIAL_APPLICATION_STATUS),
            changes.get("next_action", current.get("next_action", "")),
            changes.get("next_contact_at", current.get("next_contact_at")),
            strict=bool({"decision", "next_action", "next_contact_at"}.intersection(changes)),
        )
        audit_id = "AUD-" + hashlib.sha256((ENVIRONMENT + application_id + request_id).encode("utf-8")).hexdigest()[:24]
        assignments = ", ".join(name + " = $" + name for name in names)
        if changes.get("decision"):
            assignments += ", application_status = $application_status"
        action = "application_operational_updated|actor={}|fields={}".format(actor, ",".join(sorted(names)))
        declarations = []
        for name in names:
            type_name = "Optional<Timestamp>" if name == "next_contact_at" else "Utf8"
            declarations.append("DECLARE $" + name + " AS " + type_name + ";")
        query = """
        DECLARE $environment AS Utf8; DECLARE $application_id AS Utf8; DECLARE $participant_id AS Utf8; DECLARE $audit_id AS Utf8;
        DECLARE $request_id AS Utf8; DECLARE $action AS Utf8;
        """ + ("DECLARE $application_status AS Utf8;\n" if changes.get("decision") else "") + "\n".join(declarations) + """
        UPDATE applications SET """ + assignments + """
        WHERE environment = $environment AND application_id = $application_id;
        INSERT INTO audit_log (environment, audit_id, timestamp, request_id, application_id, participant_id, action)
        VALUES ($environment, $audit_id, CurrentUtcTimestamp(), $request_id, $application_id, $participant_id, $action);
        """
        params = {"$environment": ENVIRONMENT, "$application_id": application_id, "$participant_id": participant_id, "$audit_id": audit_id, "$request_id": request_id, "$action": action}
        if changes.get("decision"):
            params["$application_status"] = changes["decision"]
        for name in names:
            value = changes[name]
            if name == "next_contact_at":
                if value in (None, ""):
                    value = None
                else:
                    value = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
                    if value.tzinfo is None:
                        value = value.replace(tzinfo=timezone.utc)
                    else:
                        value = value.astimezone(timezone.utc)
                params["$" + name] = ydb.TypedValue(
                    value,
                    ydb.OptionalType(ydb.PrimitiveType.Timestamp),
                )
            else:
                params["$" + name] = "" if value is None else str(value)
        def operation(session):
            tx = session.transaction(ydb.QuerySerializableReadWrite())
            with tx.execute(query, params, commit_tx=True) as stream:
                for _ in stream:
                    pass
            return True
        self.pool.retry_operation_sync(operation, retry_settings=ydb.RetrySettings(max_retries=5, idempotent=True))
        card = self.get_admin_application(application_id)
        return card["application"] if card else None

    def get_admin_participant(self, participant_id):
        """Deprecated internal adapter; protected Admin routes are application-scoped."""
        query = """
        DECLARE $environment AS Utf8; DECLARE $participant_id AS Utf8;
        SELECT application_id FROM applications
        WHERE environment = $environment AND participant_id = $participant_id
        ORDER BY submitted_at ASC LIMIT 1;
        """
        result_sets = self.pool.execute_with_retries(query, {"$environment": ENVIRONMENT, "$participant_id": participant_id}, retry_settings=ydb.RetrySettings(max_retries=5, idempotent=True))
        rows = self._rows(result_sets)
        return self.get_admin_application(self._row_value(rows[0], "application_id", "")) if rows else None

    def update_admin_participant(self, participant_id, changes, actor, request_id):
        card = self.get_admin_participant(participant_id)
        return self.update_admin_application(card["application"]["application_id"], changes, actor, request_id) if card else None

    def block_processing(self, participant_id, request_id="REQ-INTERNAL", reason="internal_lifecycle"):
        """Atomically persist an internal TEST processing block and minimal audit evidence."""
        if not isinstance(reason, str) or not reason or len(reason) > 64 or not all(char.isalnum() or char in "_-" for char in reason):
            raise RepositoryUnavailable("invalid_processing_block_reason")
        audit_id = "AUD-" + hashlib.sha256((ENVIRONMENT + participant_id + request_id + "processing_blocked").encode("utf-8")).hexdigest()[:24]
        read_query = """
        DECLARE $environment AS Utf8; DECLARE $participant_id AS Utf8;
        SELECT processing_blocked FROM participants
        WHERE environment = $environment AND participant_id = $participant_id LIMIT 1;
        """
        write_query = """
        DECLARE $environment AS Utf8; DECLARE $participant_id AS Utf8; DECLARE $request_id AS Utf8;
        DECLARE $reason AS Utf8; DECLARE $audit_id AS Utf8;
        UPDATE participants SET processing_blocked = true, processing_blocked_at = CurrentUtcTimestamp(),
            processing_block_reason = $reason, processing_block_request_id = $request_id, updated_at = CurrentUtcTimestamp()
        WHERE environment = $environment AND participant_id = $participant_id;
        INSERT INTO audit_log (environment, audit_id, timestamp, request_id, application_id, participant_id, action)
        VALUES ($environment, $audit_id, CurrentUtcTimestamp(), $request_id, NULL, $participant_id, "processing_blocked");
        """
        params = {"$environment": ENVIRONMENT, "$participant_id": participant_id, "$request_id": request_id, "$reason": reason, "$audit_id": audit_id}
        def operation(session):
            tx = session.transaction(ydb.QuerySerializableReadWrite())
            with tx.execute(read_query, {"$environment": ENVIRONMENT, "$participant_id": participant_id}) as stream:
                rows = self._rows(list(stream))
            if not rows or self._row_value(rows[0], "processing_blocked", False):
                tx.commit()
                return False
            with tx.execute(write_query, params, commit_tx=True) as stream:
                for _ in stream:
                    pass
            return True
        return self.pool.retry_operation_sync(operation, retry_settings=ydb.RetrySettings(max_retries=5, idempotent=True))

    def destruction_plan(self, participant_id):
        """Return a dry-run inventory with explicit data classification; never delete."""
        query = """
        DECLARE $environment AS Utf8; DECLARE $participant_id AS Utf8;
        SELECT participant_id FROM participants WHERE environment = $environment AND participant_id = $participant_id;
        SELECT participant_id FROM participant_phone_keys WHERE environment = $environment AND participant_id = $participant_id;
        SELECT application_id FROM applications WHERE environment = $environment AND participant_id = $participant_id;
        SELECT consent_id FROM consents WHERE environment = $environment AND participant_id = $participant_id;
        SELECT t.log_id FROM technical_logs AS t INNER JOIN applications AS a
        ON t.environment = a.environment AND t.application_id = a.application_id
        WHERE t.environment = $environment AND a.participant_id = $participant_id;
        SELECT u.audit_id FROM audit_log AS u
        LEFT JOIN applications AS a ON u.environment = a.environment AND u.application_id = a.application_id
        WHERE u.environment = $environment AND (u.participant_id = $participant_id OR a.participant_id = $participant_id);
        """
        result_sets = self.pool.execute_with_retries(query, {"$environment": ENVIRONMENT, "$participant_id": participant_id}, retry_settings=ydb.RetrySettings(max_retries=5, idempotent=True))
        if not self._rows(result_sets, 0):
            return None
        application_ids = [self._row_value(row, "application_id", "") for row in self._rows(result_sets, 2)]
        consent_ids = [self._row_value(row, "consent_id", "") for row in self._rows(result_sets, 3)]
        counts = {"participant": 1, "participant_phone_keys": len(self._rows(result_sets, 1)), "applications": len(application_ids), "consents": len(consent_ids), "technical_logs": len(self._rows(result_sets, 4)), "audit_log": len(self._rows(result_sets, 5))}
        inventory = {name: {"count": count, **DESTRUCTION_CLASSIFICATION[name]} for name, count in counts.items()}
        return {"participant_id": participant_id, "dry_run": True, "delete_performed": False, "planned_audit_action": "destruction_planned", "records": inventory, "application_ids": application_ids, "consent_ids": consent_ids}

