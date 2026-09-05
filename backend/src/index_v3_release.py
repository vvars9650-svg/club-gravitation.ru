import json

import requests
import ydb

import index_v3 as core


# =========================================================
# PARTICIPANT PHONE REGISTRY
# =========================================================


def _rows(result_sets, index=0):
    if not result_sets or len(result_sets) <= index:
        return []
    return result_sets[index].rows or []


def _value(row, key, default=""):
    try:
        value = row[key]
    except (KeyError, TypeError):
        return default
    return value if value is not None else default


def find_phone_owner(phone):
    """Resolve the canonical participant owner of a normalized phone."""
    if not phone:
        return None

    query = """
    DECLARE $phone AS Utf8;

    SELECT participant_id
    FROM participant_phone_keys
    WHERE phone = $phone;
    """
    result_sets = core.get_pool().execute_with_retries(query, {"$phone": phone})
    rows = _rows(result_sets)
    if not rows:
        return None
    return core.clean_string(_value(rows[0], "participant_id")) or None


def find_secondary_contact_owners(email="", telegram=""):
    """
    Return participant ids matched by optional secondary contacts.

    Phone is authoritative because it is mandatory. Email and Telegram are
    conflict signals only: they never silently move an existing person to a
    newly submitted phone number.
    """
    if not email and not telegram:
        return set()

    query = """
    DECLARE $email AS Utf8;
    DECLARE $telegram AS Utf8;

    SELECT participant_id
    FROM participants
    WHERE ($email != "" AND email = $email)
       OR ($telegram != "" AND telegram = $telegram)
    LIMIT 5;
    """
    result_sets = core.get_pool().execute_with_retries(
        query,
        {"$email": email, "$telegram": telegram},
    )
    return {
        core.clean_string(_value(row, "participant_id"))
        for row in _rows(result_sets)
        if core.clean_string(_value(row, "participant_id"))
    }


def resolve_participant(phone, email="", telegram=""):
    """
    Resolve a participant safely.

    Rules:
    - an existing phone registry owner is authoritative;
    - secondary contacts may confirm the same owner;
    - secondary contacts pointing elsewhere cause manual-review conflict;
    - a new phone that matches an existing email/Telegram is also a conflict,
      not an automatic phone-number change.
    """
    phone_owner = find_phone_owner(phone)
    secondary_owners = find_secondary_contact_owners(email, telegram)

    if phone_owner:
        foreign = secondary_owners - {phone_owner}
        if foreign:
            raise core.ParticipantConflictError(
                "Контактные данные совпадают с несколькими участниками"
            )
        return phone_owner

    if secondary_owners:
        raise core.ParticipantConflictError(
            "Новый телефон совпал с контактами существующего участника"
        )

    return None


# =========================================================
# IDEMPOTENCY LOOKUP
# =========================================================


def find_existing_application(application_id):
    query = """
    DECLARE $application_id AS Utf8;

    SELECT participant_id, raw_payload
    FROM applications
    WHERE application_id = $application_id;
    """
    result_sets = core.get_pool().execute_with_retries(
        query,
        {"$application_id": application_id},
    )
    rows = _rows(result_sets)
    if not rows:
        return None

    row = rows[0]
    return {
        "participant_id": core.clean_string(_value(row, "participant_id")),
        "raw_payload": _value(row, "raw_payload", None),
    }


# =========================================================
# YANDEX DISK
# =========================================================


def upload_photo_to_disk(photo_bytes, application_id, fingerprint, extension):
    """
    Store one immutable application photo path.

    Fingerprint in the path prevents a concurrent request that reuses the same
    idempotency key with changed payload from overwriting the winning photo.
    """
    suffix = fingerprint[:16]
    disk_path = f"{core.DISK_PHOTO_DIR}/{application_id}-{suffix}{extension}"

    link_response = core.disk_api_request(
        "GET",
        "https://cloud-api.yandex.net/v1/disk/resources/upload",
        params={"path": disk_path, "overwrite": "true"},
        timeout=15,
    )
    upload_url = core.clean_string(link_response.json().get("href"))
    if not upload_url:
        raise RuntimeError("Yandex Disk did not return upload URL")

    response = requests.put(
        upload_url,
        data=photo_bytes,
        headers={"Content-Type": "application/octet-stream"},
        timeout=30,
    )
    response.raise_for_status()
    return disk_path


# =========================================================
# YDB WRITE
# =========================================================


def write_application(
    *,
    validated,
    participant_id,
    participant_reused,
    application_id,
    pd_consent_id,
    rules_consent_id,
    contact_consent_id,
    audit_id,
    file_id,
    disk_path,
    mime_type,
    raw_payload_json,
    audit_changes_json,
):
    declarations = """
    DECLARE $participant_id AS Utf8;
    DECLARE $application_id AS Utf8;
    DECLARE $pd_consent_id AS Utf8;
    DECLARE $rules_consent_id AS Utf8;
    DECLARE $contact_consent_id AS Utf8;
    DECLARE $audit_id AS Utf8;
    DECLARE $file_id AS Utf8;

    DECLARE $full_name AS Utf8;
    DECLARE $age AS Int64;
    DECLARE $gender AS Utf8;
    DECLARE $city AS Utf8;
    DECLARE $visit_krasnodar AS Utf8;
    DECLARE $phone AS Utf8;
    DECLARE $telegram AS Utf8;
    DECLARE $vk AS Utf8;
    DECLARE $instagram AS Utf8;
    DECLARE $email AS Utf8;
    DECLARE $preferred_contact AS Utf8;
    DECLARE $photo_path AS Utf8;

    DECLARE $occupation AS Utf8;
    DECLARE $life_outside_work AS Utf8;
    DECLARE $interests AS Utf8;
    DECLARE $relationship_context AS Utf8;
    DECLARE $desired_connections AS Utf8;
    DECLARE $values_in_people AS Utf8;
    DECLARE $barriers_to_meeting AS Utf8;
    DECLARE $source AS Utf8;
    DECLARE $what_interested AS Utf8;
    DECLARE $event_expectations AS Utf8;
    DECLARE $successful_evening AS Utf8;
    DECLARE $return_reason AS Utf8;
    DECLARE $social_comfort AS Utf8;
    DECLARE $initiative AS Utf8;
    DECLARE $acquaintance_scenario AS Utf8;
    DECLARE $unacceptable_behavior AS Utf8;
    DECLARE $convenient_days AS Utf8;
    DECLARE $comfortable_price AS Utf8;

    DECLARE $contact_consent AS Bool;
    DECLARE $pd_consent AS Bool;
    DECLARE $rules_accepted AS Bool;
    DECLARE $pd_consent_version AS Utf8;
    DECLARE $rules_version AS Utf8;
    DECLARE $contact_consent_version AS Utf8;

    DECLARE $application_channel AS Utf8;
    DECLARE $page_url AS Utf8;
    DECLARE $utm_source AS Utf8;
    DECLARE $utm_medium AS Utf8;
    DECLARE $utm_campaign AS Utf8;
    DECLARE $utm_content AS Utf8;
    DECLARE $utm_term AS Utf8;
    DECLARE $referrer AS Utf8;
    DECLARE $user_agent AS Utf8;
    DECLARE $mime_type AS Utf8;

    DECLARE $raw_payload AS JsonDocument;
    DECLARE $audit_changes AS JsonDocument;
    """

    if participant_reused:
        participant_write = """
        UPDATE participants SET
            full_name = $full_name,
            age = CAST($age AS Uint16),
            gender = $gender,
            city = $city,
            visit_krasnodar = IF(
                $visit_krasnodar != "",
                $visit_krasnodar,
                visit_krasnodar
            ),
            phone = $phone,
            telegram = IF($telegram != "", $telegram, telegram),
            vk = IF($vk != "", $vk, vk),
            instagram = IF($instagram != "", $instagram, instagram),
            email = IF($email != "", $email, email),
            preferred_contact = IF(
                $preferred_contact != "",
                $preferred_contact,
                preferred_contact
            ),
            photo_path = $photo_path,
            updated_at = CurrentUtcTimestamp()
        WHERE participant_id = $participant_id;
        """
    else:
        participant_write = """
        INSERT INTO participant_phone_keys (
            phone, participant_id, created_at
        ) VALUES (
            $phone, $participant_id, CurrentUtcTimestamp()
        );

        INSERT INTO participants (
            participant_id, full_name, age, gender, city,
            visit_krasnodar, phone, telegram, vk, instagram,
            email, preferred_contact, photo_path,
            status, created_at, updated_at
        ) VALUES (
            $participant_id, $full_name, CAST($age AS Uint16), $gender, $city,
            $visit_krasnodar, $phone, $telegram, $vk, $instagram,
            $email, $preferred_contact, $photo_path,
            "new", CurrentUtcTimestamp(), CurrentUtcTimestamp()
        );
        """

    dependent_writes = """
    INSERT INTO applications (
        application_id, participant_id, submitted_at,
        full_name, age, gender, city, visit_krasnodar,
        phone, telegram, vk, instagram, email, preferred_contact,
        occupation, life_outside_work, interests, relationship_context,
        desired_connections, values_in_people, barriers_to_meeting,
        source, what_interested, event_expectations, successful_evening,
        return_reason, social_comfort, initiative, acquaintance_scenario,
        unacceptable_behavior, convenient_days, comfortable_price,
        contact_consent, pd_consent, rules_accepted,
        application_channel, page_url,
        utm_source, utm_medium, utm_campaign, utm_content, utm_term,
        referrer, user_agent, raw_payload, created_at
    ) VALUES (
        $application_id, $participant_id, CurrentUtcTimestamp(),
        $full_name, CAST($age AS Uint16), $gender, $city, $visit_krasnodar,
        $phone, $telegram, $vk, $instagram, $email, $preferred_contact,
        $occupation, $life_outside_work, $interests, $relationship_context,
        $desired_connections, $values_in_people, $barriers_to_meeting,
        $source, $what_interested, $event_expectations, $successful_evening,
        $return_reason, $social_comfort, $initiative, $acquaintance_scenario,
        $unacceptable_behavior, $convenient_days, $comfortable_price,
        $contact_consent, $pd_consent, $rules_accepted,
        $application_channel, $page_url,
        $utm_source, $utm_medium, $utm_campaign, $utm_content, $utm_term,
        $referrer, $user_agent, $raw_payload, CurrentUtcTimestamp()
    );

    INSERT INTO consents (
        consent_id, participant_id, application_id,
        consent_type, consent_version, granted, granted_at, source, created_at
    ) VALUES (
        $pd_consent_id, $participant_id, $application_id,
        "personal_data_processing", $pd_consent_version, $pd_consent,
        CurrentUtcTimestamp(), $application_channel, CurrentUtcTimestamp()
    );

    INSERT INTO consents (
        consent_id, participant_id, application_id,
        consent_type, consent_version, granted, granted_at, source, created_at
    ) VALUES (
        $rules_consent_id, $participant_id, $application_id,
        "rules_acceptance", $rules_version, $rules_accepted,
        CurrentUtcTimestamp(), $application_channel, CurrentUtcTimestamp()
    );

    INSERT INTO consents (
        consent_id, participant_id, application_id,
        consent_type, consent_version, granted, granted_at, source, created_at
    ) VALUES (
        $contact_consent_id, $participant_id, $application_id,
        "contact", $contact_consent_version, $contact_consent,
        IF($contact_consent, CurrentUtcTimestamp()),
        $application_channel, CurrentUtcTimestamp()
    );

    INSERT INTO files (
        file_id, participant_id, application_id,
        file_type, storage, file_path, mime_type, archived, created_at
    ) VALUES (
        $file_id, $participant_id, $application_id,
        "profile_photo", "yandex_disk", $photo_path, $mime_type,
        false, CurrentUtcTimestamp()
    );

    INSERT INTO audit_log (
        audit_id, actor_type, actor_id, action,
        entity_type, entity_id, participant_id, changes, created_at
    ) VALUES (
        $audit_id, "system", "gravitation-v3-api", "application_created",
        "application", $application_id, $participant_id,
        $audit_changes, CurrentUtcTimestamp()
    );
    """

    params = {
        "$participant_id": participant_id,
        "$application_id": application_id,
        "$pd_consent_id": pd_consent_id,
        "$rules_consent_id": rules_consent_id,
        "$contact_consent_id": contact_consent_id,
        "$audit_id": audit_id,
        "$file_id": file_id,
        "$full_name": validated["full_name"],
        "$age": validated["age"],
        "$gender": validated["gender"],
        "$city": validated["city"],
        "$visit_krasnodar": validated["visit_krasnodar"],
        "$phone": validated["phone"],
        "$telegram": validated["telegram"],
        "$vk": validated["vk"],
        "$instagram": validated["instagram"],
        "$email": validated["email"],
        "$preferred_contact": validated["preferred_contact"],
        "$photo_path": disk_path,
        "$occupation": validated["occupation"],
        "$life_outside_work": validated["life_outside_work"],
        "$interests": validated["interests"],
        "$relationship_context": validated["relationship_context"],
        "$desired_connections": validated["desired_connections"],
        "$values_in_people": validated["values_in_people"],
        "$barriers_to_meeting": validated["barriers_to_meeting"],
        "$source": validated["source"],
        "$what_interested": validated["what_interested"],
        "$event_expectations": validated["event_expectations"],
        "$successful_evening": validated["successful_evening"],
        "$return_reason": validated["return_reason"],
        "$social_comfort": validated["social_comfort"],
        "$initiative": validated["initiative"],
        "$acquaintance_scenario": validated["acquaintance_scenario"],
        "$unacceptable_behavior": validated["unacceptable_behavior"],
        "$convenient_days": validated["convenient_days"],
        "$comfortable_price": validated["comfortable_price"],
        "$contact_consent": validated["contact_consent"],
        "$pd_consent": validated["pd_consent"],
        "$rules_accepted": validated["rules_accepted"],
        "$pd_consent_version": core.PD_CONSENT_VERSION,
        "$rules_version": core.RULES_VERSION,
        "$contact_consent_version": core.CONTACT_CONSENT_VERSION,
        "$application_channel": validated["application_channel"],
        "$page_url": validated["page_url"],
        "$utm_source": validated["utm_source"],
        "$utm_medium": validated["utm_medium"],
        "$utm_campaign": validated["utm_campaign"],
        "$utm_content": validated["utm_content"],
        "$utm_term": validated["utm_term"],
        "$referrer": validated["referrer"],
        "$user_agent": validated["user_agent"],
        "$mime_type": mime_type,
        "$raw_payload": ydb.TypedValue(
            raw_payload_json,
            ydb.PrimitiveType.JsonDocument,
        ),
        "$audit_changes": ydb.TypedValue(
            audit_changes_json,
            ydb.PrimitiveType.JsonDocument,
        ),
    }

    query = declarations + participant_write + dependent_writes
    core.get_pool().execute_with_retries(query, params)


# =========================================================
# SAVE APPLICATION
# =========================================================


def _replay_result(existing, application_id, file_id, fingerprint):
    stored_fingerprint = core.extract_stored_fingerprint(existing.get("raw_payload"))
    if not stored_fingerprint or stored_fingerprint != fingerprint:
        raise core.IdempotencyConflictError(
            "Idempotency-Key уже использован для другой заявки"
        )
    return {
        "participant_id": existing["participant_id"],
        "application_id": application_id,
        "file_id": file_id,
        "participant_reused": True,
        "idempotent_replay": True,
    }


def save_application(data, idempotency_key, request_id):
    if core.clean_string(data.get("website")):
        raise core.SpamDetectedError()

    normalized = core.normalize_payload(data)
    validated = core.validate_application(normalized)
    photo_bytes, mime_type, extension = core.decode_photo(normalized)

    snapshot_source = dict(normalized)
    snapshot_source.update(validated)
    payload_snapshot, fingerprint = core.build_payload_snapshot(
        snapshot_source,
        photo_bytes,
    )
    raw_payload_json = json.dumps(
        payload_snapshot,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    application_id = core.stable_id("APP", idempotency_key, "application", 20)
    pd_consent_id = core.stable_id("CONS", idempotency_key, "consent-pd", 20)
    rules_consent_id = core.stable_id("CONS", idempotency_key, "consent-rules", 20)
    contact_consent_id = core.stable_id("CONS", idempotency_key, "consent-contact", 20)
    audit_id = core.stable_id("AUD", idempotency_key, "audit-application", 20)
    file_id = core.stable_id("FILE", idempotency_key, "profile-photo", 20)

    existing = find_existing_application(application_id)
    if existing:
        return _replay_result(existing, application_id, file_id, fingerprint)

    participant_id = resolve_participant(
        validated["phone"],
        validated["email"],
        validated["telegram"],
    )
    participant_reused = participant_id is not None
    if not participant_id:
        participant_id = core.create_participant_id()

    audit_changes_json = json.dumps(
        {
            "application_id": application_id,
            "channel": validated["application_channel"],
            "status": "new",
            "photo_storage": "yandex_disk",
            "participant_reused": participant_reused,
            "request_id": request_id,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )

    disk_path = upload_photo_to_disk(
        photo_bytes,
        application_id,
        fingerprint,
        extension,
    )

    try:
        write_application(
            validated=validated,
            participant_id=participant_id,
            participant_reused=participant_reused,
            application_id=application_id,
            pd_consent_id=pd_consent_id,
            rules_consent_id=rules_consent_id,
            contact_consent_id=contact_consent_id,
            audit_id=audit_id,
            file_id=file_id,
            disk_path=disk_path,
            mime_type=mime_type,
            raw_payload_json=raw_payload_json,
            audit_changes_json=audit_changes_json,
        )
    except Exception:
        # First, handle an ambiguous network/commit outcome or concurrent retry
        # of the same Idempotency-Key.
        existing = find_existing_application(application_id)
        if existing:
            try:
                return _replay_result(
                    existing,
                    application_id,
                    file_id,
                    fingerprint,
                )
            except core.IdempotencyConflictError:
                core.delete_disk_file(disk_path, request_id=request_id)
                raise

        # If this was a concurrent creation of the same mandatory phone, the
        # participant_phone_keys primary key elects one winner. Retry the
        # losing application against that winner instead of creating a second
        # Participant.
        if not participant_reused:
            owner = find_phone_owner(validated["phone"])
            if owner and owner != participant_id:
                participant_id = resolve_participant(
                    validated["phone"],
                    validated["email"],
                    validated["telegram"],
                )
                write_application(
                    validated=validated,
                    participant_id=participant_id,
                    participant_reused=True,
                    application_id=application_id,
                    pd_consent_id=pd_consent_id,
                    rules_consent_id=rules_consent_id,
                    contact_consent_id=contact_consent_id,
                    audit_id=audit_id,
                    file_id=file_id,
                    disk_path=disk_path,
                    mime_type=mime_type,
                    raw_payload_json=raw_payload_json,
                    audit_changes_json=audit_changes_json,
                )
                participant_reused = True
            else:
                core.delete_disk_file(disk_path, request_id=request_id)
                raise
        else:
            core.delete_disk_file(disk_path, request_id=request_id)
            raise

    return {
        "participant_id": participant_id,
        "application_id": application_id,
        "file_id": file_id,
        "photo_path": disk_path,
        "participant_reused": participant_reused,
        "idempotent_replay": False,
    }


# =========================================================
# CLOUD FUNCTION
# =========================================================


def handler(event, context):
    request_id = core.request_id_from_context(context)

    try:
        method = core.clean_string(event.get("httpMethod")).upper()
        if method != "POST":
            return core.json_response(
                405,
                {
                    "success": False,
                    "error": "Method not allowed",
                    "code": "method_not_allowed",
                },
                request_id,
            )

        data = core.parse_event_body(event)
        idempotency_key = core.validate_idempotency_key(
            core.header_value(event, "idempotency-key")
            or data.get("idempotency_key")
        )

        result = save_application(data, idempotency_key, request_id)
        status_code = 200 if result["idempotent_replay"] else 201

        core.log_event(
            request_id,
            "application_accepted",
            participant_id=result["participant_id"],
            application_id=result["application_id"],
            participant_reused=result["participant_reused"],
            idempotent_replay=result["idempotent_replay"],
        )

        return core.json_response(
            status_code,
            {
                "success": True,
                "message": "Заявка принята",
                "participant_id": result["participant_id"],
                "application_id": result["application_id"],
                "file_id": result["file_id"],
                "participant_reused": result["participant_reused"],
                "idempotent_replay": result["idempotent_replay"],
            },
            request_id,
        )

    except OverflowError as error:
        return core.json_response(
            413,
            {"success": False, "error": str(error), "code": "payload_too_large"},
            request_id,
        )
    except (ValueError, TypeError) as error:
        return core.json_response(
            400,
            {"success": False, "error": str(error), "code": "validation_error"},
            request_id,
        )
    except core.SpamDetectedError:
        core.log_event(request_id, "spam_rejected")
        return core.json_response(
            202,
            {"success": True, "message": "Заявка принята"},
            request_id,
        )
    except core.ParticipantConflictError as error:
        core.log_event(
            request_id,
            "participant_conflict",
            level="WARNING",
            error_type=type(error).__name__,
        )
        return core.json_response(
            409,
            {
                "success": False,
                "error": "Контактные данные требуют ручной проверки",
                "code": "participant_conflict",
            },
            request_id,
        )
    except core.IdempotencyConflictError as error:
        core.log_event(
            request_id,
            "idempotency_conflict",
            level="WARNING",
            error_type=type(error).__name__,
        )
        return core.json_response(
            409,
            {
                "success": False,
                "error": "Повторный запрос отличается от исходного",
                "code": "idempotency_conflict",
            },
            request_id,
        )
    except requests.HTTPError as error:
        status = error.response.status_code if error.response is not None else 0
        core.log_event(
            request_id,
            "external_http_error",
            level="ERROR",
            status=status,
        )
        return core.json_response(
            502,
            {"success": False, "error": "Ошибка файлового хранилища", "code": "storage_error"},
            request_id,
        )
    except Exception as error:
        core.log_event(
            request_id,
            "internal_error",
            level="ERROR",
            error_type=type(error).__name__,
        )
        return core.json_response(
            500,
            {"success": False, "error": "Внутренняя ошибка сервера", "code": "internal_error"},
            request_id,
        )
