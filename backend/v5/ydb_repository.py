"""YDB repository for GRAVITATION V5 synthetic TEST."""

import hashlib
import json
import os
import threading

try:
    import ydb
    import ydb.iam
except ImportError:  # unit-only imports must not silently create memory storage
    ydb = None

from .domain import FORM_FIELDS, ids
from .repository import DESTRUCTION_CLASSIFICATION, RepositoryUnavailable


ENVIRONMENT = "TEST"
FORM_VERSION = "FORM-2.0"
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

        SELECT p.participant_id, p.processing_blocked
        FROM participant_phone_keys AS k
        INNER JOIN participants AS p
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

        intake_read_query = """
        DECLARE $environment AS Utf8;
        DECLARE $application_id AS Utf8;
        DECLARE $phone AS Utf8;

        SELECT
            "application" AS record_type,
            application_id,
            participant_id,
            payload_fingerprint,
            false AS processing_blocked
        FROM applications
        WHERE environment = $environment
          AND application_id = $application_id
        UNION ALL
        SELECT
            "phone" AS record_type,
            "" AS application_id,
            p.participant_id AS participant_id,
            "" AS payload_fingerprint,
            p.processing_blocked AS processing_blocked
        FROM participant_phone_keys AS k
        INNER JOIN participants AS p
        ON k.environment = p.environment AND k.participant_id = p.participant_id
        WHERE k.environment = $environment
          AND k.phone = $phone;
        """

        def transaction_body(session):
            tx = session.transaction(ydb.QuerySerializableReadWrite())

            with tx.execute(
                intake_read_query,
                {
                    "$environment": ENVIRONMENT,
                    "$application_id": application_id,
                    "$phone": phone,
                },
            ) as result_stream:
                intake_result_sets = list(result_stream)

            intake_rows = self._rows(intake_result_sets, 0)
            application_rows = [
                row for row in intake_rows
                if self._row_value(row, "record_type", "") == "application"
            ]
            phone_rows = [
                row for row in intake_rows
                if self._row_value(row, "record_type", "") == "phone"
            ]

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

                if self._row_value(phone_rows[0], "processing_blocked", False):
                    tx.commit()
                    raise RepositoryUnavailable("processing_blocked")

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
            "processing_blocked_at": self._row_value(row, "processing_blocked_at", None),
            "processing_block_reason": self._row_value(row, "processing_block_reason", ""),
            "processing_block_request_id": self._row_value(row, "processing_block_request_id", ""),
        }

    def find_participant_by_phone(self, phone):
        """Internal subject locate by already-normalized authoritative phone."""
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
        """Read-only TEST list for the future protected Admin API."""
        filters = filters or {}
        direction = "ASC" if order == "asc" else "DESC"
        allowed_sorts = {
            "submitted_at", "full_name", "age", "city", "lifecycle_status",
            "priority", "next_contact_at",
        }
        if sort not in allowed_sorts:
            raise RepositoryUnavailable("invalid_admin_sort")
        query = """
        DECLARE $environment AS Utf8;
        DECLARE $q AS Utf8;
        DECLARE $lifecycle_status AS Utf8;
        DECLARE $owner AS Utf8;
        DECLARE $priority AS Utf8;
        DECLARE $decision AS Utf8;
        SELECT a.application_id, a.participant_id, a.submitted_at, a.full_name,
               a.age, a.city, a.phone, a.telegram, a.preferred_contact,
               p.lifecycle_status, p.owner, p.priority, p.next_action,
               p.next_contact_at, p.decision
        FROM applications AS a
        INNER JOIN participants AS p
        ON a.environment = p.environment AND a.participant_id = p.participant_id
        WHERE a.environment = $environment
          AND ($q = "" OR a.full_name LIKE "%" || $q || "%" OR a.phone LIKE "%" || $q || "%" OR a.telegram LIKE "%" || $q || "%" OR a.city LIKE "%" || $q || "%")
          AND ($lifecycle_status = "" OR p.lifecycle_status = $lifecycle_status)
          AND ($owner = "" OR p.owner = $owner)
          AND ($priority = "" OR p.priority = $priority)
          AND ($decision = "" OR p.decision = $decision)
        ORDER BY """ + sort + " " + direction + ";"
        result_sets = self.pool.execute_with_retries(query, {
            "$environment": ENVIRONMENT,
            "$q": filters.get("q", ""), "$lifecycle_status": filters.get("lifecycle_status", ""),
            "$owner": filters.get("owner", ""), "$priority": filters.get("priority", ""),
            "$decision": filters.get("decision", ""),
        }, retry_settings=ydb.RetrySettings(max_retries=5, idempotent=True))
        return [{name: self._row_value(row, name, "") for name in (
            "application_id", "participant_id", "submitted_at", "full_name", "age", "city", "phone",
            "telegram", "preferred_contact", "lifecycle_status", "owner", "priority", "next_action",
            "next_contact_at", "decision") } | {"environment": ENVIRONMENT} for row in self._rows(result_sets)]

    def get_admin_participant(self, participant_id):
        query = """
        DECLARE $environment AS Utf8; DECLARE $participant_id AS Utf8;
        SELECT participant_id, phone, full_name, age, gender, city, visit_krasnodar, telegram, email,
               preferred_contact, public_profile_url, lifecycle_status, owner, priority, next_action,
               next_contact_at, decision, internal_comment
        FROM participants WHERE environment = $environment AND participant_id = $participant_id;
        SELECT application_id, submitted_at, form_version, request_id, full_name, age, gender, city,
               visit_krasnodar, phone, telegram, email, preferred_contact, public_profile_url, occupation,
               life_outside_work, interests, what_interested, event_expectations, desired_connections,
               values_in_people, barriers_to_meeting, social_comfort, initiative, acquaintance_scenario,
               successful_evening, return_reason, unacceptable_behavior, convenient_days, comfortable_price, source
        FROM applications WHERE environment = $environment AND participant_id = $participant_id ORDER BY submitted_at DESC;
        SELECT consent_id, application_id, consent_type, consent_version, policy_version, form_version,
               consent_text_hash, granted, granted_at, source, request_id
        FROM consents WHERE environment = $environment AND participant_id = $participant_id;
        """
        result_sets = self.pool.execute_with_retries(query, {"$environment": ENVIRONMENT, "$participant_id": participant_id}, retry_settings=ydb.RetrySettings(max_retries=5, idempotent=True))
        participant_rows = self._rows(result_sets, 0)
        if not participant_rows:
            return None
        participant_fields = ("participant_id", "phone", "full_name", "age", "gender", "city", "visit_krasnodar", "telegram", "email", "preferred_contact", "public_profile_url", "lifecycle_status", "owner", "priority", "next_action", "next_contact_at", "decision", "internal_comment")
        application_fields = ("application_id", "submitted_at", "form_version", "request_id", *FORM_FIELDS)
        consent_fields = ("consent_id", "application_id", "consent_type", "consent_version", "policy_version", "form_version", "consent_text_hash", "granted", "granted_at", "source", "request_id")
        return {"environment": ENVIRONMENT, "participant": {name: self._row_value(participant_rows[0], name, "") for name in participant_fields}, "applications": [{"application_id": self._row_value(row, "application_id", ""), "submitted_at": self._row_value(row, "submitted_at", ""), "form_version": self._row_value(row, "form_version", ""), "request_id": self._row_value(row, "request_id", ""), "form": {name: self._row_value(row, name, [] if name in ("desired_connections", "convenient_days") else "") for name in FORM_FIELDS}} for row in self._rows(result_sets, 1)], "consents": [{name: self._row_value(row, name, "") for name in consent_fields} for row in self._rows(result_sets, 2)]}

    def update_admin_participant(self, participant_id, changes, actor, request_id):
        """Atomic operational-only update plus minimal audit evidence."""
        from .admin import OPERATIONAL_FIELDS
        names = tuple(name for name in changes if name in OPERATIONAL_FIELDS)
        if not names:
            return None
        audit_id = "AUD-" + hashlib.sha256((ENVIRONMENT + participant_id + request_id).encode("utf-8")).hexdigest()[:24]
        assignments = ", ".join(name + " = $" + name for name in names)
        action = "participant_operational_updated|actor={}|fields={}".format(actor, ",".join(sorted(names)))
        declarations = []
        for name in names:
            type_name = "Optional<Timestamp>" if name == "next_contact_at" else "Utf8"
            declarations.append("DECLARE $" + name + " AS " + type_name + ";")
        query = """
        DECLARE $environment AS Utf8; DECLARE $participant_id AS Utf8; DECLARE $audit_id AS Utf8;
        DECLARE $request_id AS Utf8; DECLARE $action AS Utf8;
        """ + "\n".join(declarations) + """
        UPDATE participants SET """ + assignments + """, updated_at = CurrentUtcTimestamp()
        WHERE environment = $environment AND participant_id = $participant_id;
        INSERT INTO audit_log (environment, audit_id, timestamp, request_id, application_id, participant_id, action)
        VALUES ($environment, $audit_id, CurrentUtcTimestamp(), $request_id, NULL, $participant_id, $action);
        """
        params = {"$environment": ENVIRONMENT, "$participant_id": participant_id, "$audit_id": audit_id, "$request_id": request_id, "$action": action}
        params.update({"$" + name: "" if changes[name] is None else str(changes[name]) for name in names})
        def operation(session):
            tx = session.transaction(ydb.QuerySerializableReadWrite())
            with tx.execute(query, params, commit_tx=True) as stream:
                for _ in stream:
                    pass
            return True
        self.pool.retry_operation_sync(operation, retry_settings=ydb.RetrySettings(max_retries=5, idempotent=True))
        card = self.get_admin_participant(participant_id)
        return card["participant"] if card else None

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
