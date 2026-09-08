"""YDB repository for GRAVITATION V5 synthetic TEST."""

import hashlib
import json
import os

try:
    import ydb
    import ydb.iam
except ImportError:  # unit-only imports must not silently create memory storage
    ydb = None

from .domain import ids
from .repository import RepositoryUnavailable


ENVIRONMENT = "TEST"
FORM_VERSION = "FORM-2.0"


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

        if driver is None:
            if ydb is None:
                raise RepositoryUnavailable("ydb_sdk_not_installed")
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
            application_id,
            participant_id,
            payload_fingerprint,
            request_id
        FROM applications
        WHERE environment = $environment
          AND application_id = $application_id
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
            "participant_id": self._row_value(
                row, "participant_id", ""
            ),
            "payload_fingerprint": self._row_value(
                row, "payload_fingerprint", ""
            ),
            "request_id": self._row_value(
                row, "request_id", ""
            ),
        }

    def resolve_phone(self, phone):
        query = """
        DECLARE $environment AS Utf8;
        DECLARE $phone AS Utf8;

        SELECT participant_id
        FROM participant_phone_keys
        WHERE environment = $environment
          AND phone = $phone
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
        - creates or safely updates participant;
        - inserts immutable application;
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

        log_id = "LOG-" + hashlib.sha256(
            f"{ENVIRONMENT}:{application_id}:created".encode("utf-8")
        ).hexdigest()[:24]

        audit_id = "AUD-" + hashlib.sha256(
            f"{ENVIRONMENT}:{application_id}:created".encode("utf-8")
        ).hexdigest()[:24]

        read_query = """
        DECLARE $environment AS Utf8;
        DECLARE $application_id AS Utf8;
        DECLARE $phone AS Utf8;

        SELECT
            application_id,
            participant_id,
            payload_fingerprint
        FROM applications
        WHERE environment = $environment
          AND application_id = $application_id
        LIMIT 1;

        SELECT participant_id
        FROM participant_phone_keys
        WHERE environment = $environment
          AND phone = $phone
        LIMIT 1;
        """

        def transaction_body(session):
            tx = session.transaction(ydb.QuerySerializableReadWrite())

            with tx.execute(
                read_query,
                {
                    "$environment": ENVIRONMENT,
                    "$application_id": application_id,
                    "$phone": phone,
                },
            ) as result_stream:
                result_sets = list(result_stream)

            application_rows = self._rows(result_sets, 0)
            phone_rows = self._rows(result_sets, 1)

            if application_rows:
                tx.commit()
                return False

            existing_participant_id = None

            if phone_rows:
                existing_participant_id = self._row_value(
                    phone_rows[0],
                    "participant_id",
                    None,
                )

            if existing_participant_id:
                participant_id = existing_participant_id

                participant_write = """
                UPDATE participants SET
                    full_name = $full_name,
                    age = $age,
                    gender = $gender,
                    city = $city,
                    visit_krasnodar = $visit_krasnodar,
                    telegram = IF(
                        $telegram != "",
                        $telegram,
                        telegram
                    ),
                    email = IF(
                        $email != "",
                        $email,
                        email
                    ),
                    preferred_contact = IF(
                        $preferred_contact != "",
                        $preferred_contact,
                        preferred_contact
                    ),
                    public_profile_url = IF(
                        $public_profile_url != "",
                        $public_profile_url,
                        public_profile_url
                    ),
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
                    public_profile_url,
                    lifecycle_status,
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
                    $public_profile_url,
                    "Новая заявка",
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

            write_query = (
                """
                DECLARE $environment AS Utf8;
                DECLARE $participant_id AS Utf8;
                DECLARE $application_id AS Utf8;
                DECLARE $consent_id AS Utf8;
                DECLARE $request_id AS Utf8;
                DECLARE $payload_fingerprint AS Utf8;

                DECLARE $full_name AS Utf8;
                DECLARE $age AS Int32;
                DECLARE $gender AS Utf8;
                DECLARE $city AS Utf8;
                DECLARE $visit_krasnodar AS Utf8;
                DECLARE $phone AS Utf8;
                DECLARE $telegram AS Utf8;
                DECLARE $email AS Utf8;
                DECLARE $preferred_contact AS Utf8;
                DECLARE $public_profile_url AS Utf8;

                DECLARE $occupation AS Utf8;
                DECLARE $life_outside_work AS Utf8;
                DECLARE $interests AS Utf8;
                DECLARE $what_interested AS Utf8;
                DECLARE $event_expectations AS Utf8;
                DECLARE $desired_connections AS Json;
                DECLARE $values_in_people AS Utf8;
                DECLARE $barriers_to_meeting AS Utf8;
                DECLARE $social_comfort AS Utf8;
                DECLARE $initiative AS Utf8;
                DECLARE $acquaintance_scenario AS Utf8;
                DECLARE $successful_evening AS Utf8;
                DECLARE $return_reason AS Utf8;
                DECLARE $unacceptable_behavior AS Utf8;
                DECLARE $convenient_days AS Json;
                DECLARE $comfortable_price AS Utf8;
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
                INSERT INTO applications (
                    environment,
                    application_id,
                    participant_id,
                    submitted_at,
                    payload_fingerprint,
                    form_version,
                    request_id,
                    full_name,
                    age,
                    gender,
                    city,
                    visit_krasnodar,
                    phone,
                    telegram,
                    email,
                    preferred_contact,
                    public_profile_url,
                    occupation,
                    life_outside_work,
                    interests,
                    what_interested,
                    event_expectations,
                    desired_connections,
                    values_in_people,
                    barriers_to_meeting,
                    social_comfort,
                    initiative,
                    acquaintance_scenario,
                    successful_evening,
                    return_reason,
                    unacceptable_behavior,
                    convenient_days,
                    comfortable_price,
                    source
                ) VALUES (
                    $environment,
                    $application_id,
                    $participant_id,
                    CurrentUtcTimestamp(),
                    $payload_fingerprint,
                    $form_version,
                    $request_id,
                    $full_name,
                    $age,
                    $gender,
                    $city,
                    $visit_krasnodar,
                    $phone,
                    $telegram,
                    $email,
                    $preferred_contact,
                    $public_profile_url,
                    $occupation,
                    $life_outside_work,
                    $interests,
                    $what_interested,
                    $event_expectations,
                    $desired_connections,
                    $values_in_people,
                    $barriers_to_meeting,
                    $social_comfort,
                    $initiative,
                    $acquaintance_scenario,
                    $successful_evening,
                    $return_reason,
                    $unacceptable_behavior,
                    $convenient_days,
                    $comfortable_price,
                    $source
                );

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
                "$consent_id": record["consent_id"],
                "$request_id": record["request_id"],
                "$payload_fingerprint": record["payload_fingerprint"],

                "$full_name": form["full_name"],
                "$age": ydb.TypedValue(
                    form["age"],
                    ydb.PrimitiveType.Int32,
                ),
                "$gender": form["gender"],
                "$city": form["city"],
                "$visit_krasnodar": form["visit_krasnodar"],
                "$phone": form["phone"],
                "$telegram": form["telegram"],
                "$email": form["email"],
                "$preferred_contact": form["preferred_contact"],
                "$public_profile_url": form["public_profile_url"],

                "$occupation": form["occupation"],
                "$life_outside_work": form["life_outside_work"],
                "$interests": form["interests"],
                "$what_interested": form["what_interested"],
                "$event_expectations": form["event_expectations"],
                "$desired_connections": ydb.TypedValue(
                    json.dumps(
                        form["desired_connections"],
                        ensure_ascii=False,
                    ),
                    ydb.PrimitiveType.Json,
                ),
                "$values_in_people": form["values_in_people"],
                "$barriers_to_meeting": form["barriers_to_meeting"],
                "$social_comfort": form["social_comfort"],
                "$initiative": form["initiative"],
                "$acquaintance_scenario": form["acquaintance_scenario"],
                "$successful_evening": form["successful_evening"],
                "$return_reason": form["return_reason"],
                "$unacceptable_behavior": form["unacceptable_behavior"],
                "$convenient_days": ydb.TypedValue(
                    json.dumps(
                        form["convenient_days"],
                        ensure_ascii=False,
                    ),
                    ydb.PrimitiveType.Json,
                ),
                "$comfortable_price": form["comfortable_price"],
                "$source": form["source"],

                "$consent_type": "personal_data_application",
                "$consent_version": "CONSENT-PD-2.0",
                "$policy_version": "PPD-2.0",
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
            return True

        return self.pool.retry_operation_sync(
            transaction_body,
            retry_settings=ydb.RetrySettings(
                max_retries=5,
                idempotent=True,
            ),
        )

    def find_participant(self, participant_id):
        query = """
        DECLARE $environment AS Utf8;
        DECLARE $participant_id AS Utf8;

        SELECT
            participant_id,
            lifecycle_status,
            owner,
            priority,
            next_action,
            next_contact_at,
            decision
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
        }

    def block_processing(self, participant_id):
        raise RepositoryUnavailable(
            "processing_block_schema_required"
        )

    def destruction_plan(self, participant_id):
        return {
            "participant_id": participant_id,
            "applications": "separate command required",
            "consents": "retention policy required",
            "audit_log": "retention policy required",
        }
