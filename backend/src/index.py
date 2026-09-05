import os
import re
import json
import uuid
import base64
import secrets
from datetime import datetime, timezone

import requests
import ydb
import ydb.iam


# =========================================================
# CONFIG
# =========================================================

PD_CONSENT_VERSION = "pd-test-v1"
RULES_VERSION = "rules-test-v1"
CONTACT_CONSENT_VERSION = "contact-test-v1"

MAX_REQUEST_BYTES = 2_300_000
MAX_PHOTO_BYTES = 1_500_000
DISK_PHOTO_DIR = "/ГРАВИТАЦИЯ/Участники/Фото"

PHONE_RE = re.compile(r"^\+7\d{10}$")
EMAIL_RE = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+"
    r"@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$"
)

FIELD_LIMITS = {
    "full_name": 150,
    "gender": 50,
    "city": 150,
    "phone": 12,
    "telegram": 150,
    "email": 254,
    "preferred_contact": 100,
    "occupation": 1000,
    "life_outside_work": 2000,
    "interests": 2000,
    "relationship_context": 2000,
    "desired_connections": 2000,
    "values_in_people": 2000,
    "barriers_to_meeting": 2000,
    "source": 500,
    "what_interested": 2000,
    "event_expectations": 2000,
    "successful_evening": 2000,
    "return_reason": 2000,
    "social_comfort": 1000,
    "initiative": 1000,
    "acquaintance_scenario": 2000,
    "unacceptable_behavior": 2000,
    "convenient_days": 500,
    "comfortable_price": 500,
    "application_channel": 100,
    "page_url": 2000,
    "utm_source": 500,
    "utm_medium": 500,
    "utm_campaign": 500,
    "utm_content": 500,
    "utm_term": 500,
    "referrer": 2000,
    "user_agent": 2000,
}


# =========================================================
# YDB
# =========================================================

driver = ydb.Driver(
    endpoint=os.getenv("YDB_ENDPOINT"),
    database=os.getenv("YDB_DATABASE"),
    credentials=ydb.iam.MetadataUrlCredentials(),
)

driver.wait(fail_fast=True, timeout=5)
pool = ydb.QuerySessionPool(driver)


# =========================================================
# HELPERS
# =========================================================

def json_response(status_code, data):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json; charset=utf-8",
        },
        "body": json.dumps(data, ensure_ascii=False),
    }


def clean_string(value):
    if value is None:
        return ""
    return str(value).strip()


def parse_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value == 1
    if isinstance(value, str):
        value = value.strip().lower()
        if value in ("true", "1", "yes", "on", "да"):
            return True
        if value in ("false", "0", "no", "off", "нет", ""):
            return False
    return False


def validate_string(name, value):
    value = clean_string(value)
    limit = FIELD_LIMITS.get(name)
    if limit and len(value) > limit:
        raise ValueError(f"Поле {name} превышает допустимую длину")
    return value


def create_participant_id():
    now = datetime.now(timezone.utc)
    suffix = secrets.randbelow(90) + 10
    return f"GR-{now:%y%m%d-%H%M%S}-{suffix}"


def create_application_id():
    return "APP-" + uuid.uuid4().hex[:16].upper()


def create_consent_id():
    return "CONS-" + uuid.uuid4().hex[:20].upper()


def create_audit_id():
    return "AUD-" + uuid.uuid4().hex[:20].upper()


def create_file_id():
    return "FILE-" + uuid.uuid4().hex[:20].upper()


# =========================================================
# PHOTO
# =========================================================

def detect_image_type(photo_bytes):
    if photo_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", ".jpg"
    if photo_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", ".png"
    if (
        len(photo_bytes) >= 12
        and photo_bytes[:4] == b"RIFF"
        and photo_bytes[8:12] == b"WEBP"
    ):
        return "image/webp", ".webp"
    raise ValueError("Фотография должна быть JPG, PNG или WEBP")


def decode_photo(data):
    photo_data = clean_string(data.get("photo_data"))
    if not photo_data:
        raise ValueError("Фотография обязательна")

    if photo_data.startswith("data:"):
        try:
            photo_data = photo_data.split(",", 1)[1]
        except IndexError as exc:
            raise ValueError("Некорректные данные фотографии") from exc

    try:
        photo_bytes = base64.b64decode(photo_data, validate=True)
    except Exception as exc:
        raise ValueError("Некорректные данные фотографии") from exc

    if not photo_bytes:
        raise ValueError("Фотография обязательна")

    if len(photo_bytes) > MAX_PHOTO_BYTES:
        raise ValueError("Фотография слишком большая. Максимум 1,5 МБ после обработки")

    mime_type, extension = detect_image_type(photo_bytes)
    return photo_bytes, mime_type, extension


def disk_headers():
    token = os.getenv("YANDEX_DISK_ACCESS_TOKEN")
    if not token:
        raise RuntimeError("YANDEX_DISK_ACCESS_TOKEN is not configured")
    return {"Authorization": f"OAuth {token}"}


def upload_photo_to_disk(photo_bytes, participant_id, extension):
    disk_path = f"{DISK_PHOTO_DIR}/{participant_id}{extension}"

    link_response = requests.get(
        "https://cloud-api.yandex.net/v1/disk/resources/upload",
        headers=disk_headers(),
        params={
            "path": disk_path,
            "overwrite": "true",
        },
        timeout=15,
    )
    link_response.raise_for_status()
    upload_url = link_response.json().get("href")
    if not upload_url:
        raise RuntimeError("Yandex Disk did not return upload URL")

    upload_response = requests.put(
        upload_url,
        data=photo_bytes,
        headers={"Content-Type": "application/octet-stream"},
        timeout=30,
    )
    upload_response.raise_for_status()

    return disk_path


def delete_disk_file(disk_path):
    if not disk_path:
        return
    try:
        requests.delete(
            "https://cloud-api.yandex.net/v1/disk/resources",
            headers=disk_headers(),
            params={
                "path": disk_path,
                "permanently": "true",
            },
            timeout=15,
        )
    except Exception as error:
        print("DISK CLEANUP ERROR:", repr(error))


# =========================================================
# SAVE APPLICATION
# =========================================================

def save_application(data):
    participant_id = create_participant_id()
    application_id = create_application_id()
    pd_consent_id = create_consent_id()
    rules_consent_id = create_consent_id()
    contact_consent_id = create_consent_id()
    audit_id = create_audit_id()
    file_id = create_file_id()

    payload_snapshot = dict(data)
    payload_snapshot.pop("photo_data", None)
    payload_snapshot["photo_attached"] = bool(data.get("photo_data"))
    raw_payload_json = json.dumps(
        payload_snapshot,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    full_name = validate_string("full_name", data.get("full_name"))
    gender = validate_string("gender", data.get("gender"))
    city = validate_string("city", data.get("city"))
    phone = validate_string("phone", data.get("phone"))
    telegram = validate_string("telegram", data.get("telegram"))
    email = validate_string("email", data.get("email"))
    preferred_contact = validate_string("preferred_contact", data.get("preferred_contact"))
    occupation = validate_string("occupation", data.get("occupation"))
    life_outside_work = validate_string("life_outside_work", data.get("life_outside_work"))
    interests = validate_string("interests", data.get("interests"))
    relationship_context = validate_string("relationship_context", data.get("relationship_context"))
    desired_connections = validate_string("desired_connections", data.get("desired_connections"))
    values_in_people = validate_string("values_in_people", data.get("values_in_people"))
    barriers_to_meeting = validate_string("barriers_to_meeting", data.get("barriers_to_meeting"))
    source = validate_string("source", data.get("source"))
    what_interested = validate_string("what_interested", data.get("what_interested"))
    event_expectations = validate_string("event_expectations", data.get("event_expectations"))
    successful_evening = validate_string("successful_evening", data.get("successful_evening"))
    return_reason = validate_string("return_reason", data.get("return_reason"))
    social_comfort = validate_string("social_comfort", data.get("social_comfort"))
    initiative = validate_string("initiative", data.get("initiative"))
    acquaintance_scenario = validate_string("acquaintance_scenario", data.get("acquaintance_scenario"))
    unacceptable_behavior = validate_string("unacceptable_behavior", data.get("unacceptable_behavior"))
    convenient_days = validate_string("convenient_days", data.get("convenient_days"))
    comfortable_price = validate_string("comfortable_price", data.get("comfortable_price"))

    application_channel = validate_string(
        "application_channel",
        data.get("application_channel") or "website",
    )
    page_url = validate_string("page_url", data.get("page_url"))
    utm_source = validate_string("utm_source", data.get("utm_source"))
    utm_medium = validate_string("utm_medium", data.get("utm_medium"))
    utm_campaign = validate_string("utm_campaign", data.get("utm_campaign"))
    utm_content = validate_string("utm_content", data.get("utm_content"))
    utm_term = validate_string("utm_term", data.get("utm_term"))
    referrer = validate_string("referrer", data.get("referrer"))
    user_agent = validate_string("user_agent", data.get("user_agent"))

    if not full_name:
        raise ValueError("Не указаны имя и фамилия")
    if len(full_name) < 2:
        raise ValueError("Имя указано некорректно")

    try:
        age = int(data.get("age"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Некорректный возраст") from exc

    if age < 25 or age > 52:
        raise ValueError("Возраст должен быть от 25 до 52 лет")
    if not gender:
        raise ValueError("Не указан пол")
    if not city:
        raise ValueError("Не указан город")
    if not phone:
        raise ValueError("Не указан телефон")
    if not PHONE_RE.fullmatch(phone):
        raise ValueError("Телефон должен быть в формате +7XXXXXXXXXX")
    if email and not EMAIL_RE.fullmatch(email):
        raise ValueError("Некорректный формат email")

    pd_consent = parse_bool(data.get("pd_consent"))
    rules_accepted = parse_bool(data.get("rules_accepted"))
    contact_consent = parse_bool(data.get("contact_consent"))

    if not pd_consent:
        raise ValueError("Необходимо согласие на обработку персональных данных")
    if not rules_accepted:
        raise ValueError("Необходимо принять правила участия")

    photo_bytes, mime_type, extension = decode_photo(data)

    audit_changes_json = json.dumps(
        {
            "application_id": application_id,
            "channel": application_channel,
            "status": "new",
            "photo_storage": "yandex_disk",
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )

    disk_path = ""
    try:
        disk_path = upload_photo_to_disk(photo_bytes, participant_id, extension)

        query = """
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
        DECLARE $phone AS Utf8;
        DECLARE $telegram AS Utf8;
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

        UPSERT INTO participants (
            participant_id, full_name, age, gender, city,
            phone, telegram, email, preferred_contact, photo_path,
            status, created_at, updated_at
        ) VALUES (
            $participant_id, $full_name, CAST($age AS Uint16), $gender, $city,
            $phone, $telegram, $email, $preferred_contact, $photo_path,
            "new", CurrentUtcTimestamp(), CurrentUtcTimestamp()
        );

        UPSERT INTO applications (
            application_id, participant_id, submitted_at,
            full_name, age, gender, city,
            phone, telegram, email, preferred_contact,
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
            $full_name, CAST($age AS Uint16), $gender, $city,
            $phone, $telegram, $email, $preferred_contact,
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

        UPSERT INTO consents (
            consent_id, participant_id, application_id,
            consent_type, consent_version, granted, granted_at, source, created_at
        ) VALUES (
            $pd_consent_id, $participant_id, $application_id,
            "personal_data_processing", $pd_consent_version, $pd_consent,
            CurrentUtcTimestamp(), $application_channel, CurrentUtcTimestamp()
        );

        UPSERT INTO consents (
            consent_id, participant_id, application_id,
            consent_type, consent_version, granted, granted_at, source, created_at
        ) VALUES (
            $rules_consent_id, $participant_id, $application_id,
            "rules_acceptance", $rules_version, $rules_accepted,
            CurrentUtcTimestamp(), $application_channel, CurrentUtcTimestamp()
        );

        UPSERT INTO consents (
            consent_id, participant_id, application_id,
            consent_type, consent_version, granted, granted_at, source, created_at
        ) VALUES (
            $contact_consent_id, $participant_id, $application_id,
            "contact", $contact_consent_version, $contact_consent,
            IF($contact_consent, CurrentUtcTimestamp()),
            $application_channel, CurrentUtcTimestamp()
        );

        UPSERT INTO files (
            file_id, participant_id, application_id,
            file_type, storage, file_path, mime_type, archived, created_at
        ) VALUES (
            $file_id, $participant_id, $application_id,
            "profile_photo", "yandex_disk", $photo_path, $mime_type,
            false, CurrentUtcTimestamp()
        );

        UPSERT INTO audit_log (
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
            "$full_name": full_name,
            "$age": age,
            "$gender": gender,
            "$city": city,
            "$phone": phone,
            "$telegram": telegram,
            "$email": email,
            "$preferred_contact": preferred_contact,
            "$photo_path": disk_path,
            "$occupation": occupation,
            "$life_outside_work": life_outside_work,
            "$interests": interests,
            "$relationship_context": relationship_context,
            "$desired_connections": desired_connections,
            "$values_in_people": values_in_people,
            "$barriers_to_meeting": barriers_to_meeting,
            "$source": source,
            "$what_interested": what_interested,
            "$event_expectations": event_expectations,
            "$successful_evening": successful_evening,
            "$return_reason": return_reason,
            "$social_comfort": social_comfort,
            "$initiative": initiative,
            "$acquaintance_scenario": acquaintance_scenario,
            "$unacceptable_behavior": unacceptable_behavior,
            "$convenient_days": convenient_days,
            "$comfortable_price": comfortable_price,
            "$contact_consent": contact_consent,
            "$pd_consent": pd_consent,
            "$rules_accepted": rules_accepted,
            "$pd_consent_version": PD_CONSENT_VERSION,
            "$rules_version": RULES_VERSION,
            "$contact_consent_version": CONTACT_CONSENT_VERSION,
            "$application_channel": application_channel,
            "$page_url": page_url,
            "$utm_source": utm_source,
            "$utm_medium": utm_medium,
            "$utm_campaign": utm_campaign,
            "$utm_content": utm_content,
            "$utm_term": utm_term,
            "$referrer": referrer,
            "$user_agent": user_agent,
            "$mime_type": mime_type,
            "$raw_payload": ydb.TypedValue(raw_payload_json, ydb.PrimitiveType.JsonDocument),
            "$audit_changes": ydb.TypedValue(audit_changes_json, ydb.PrimitiveType.JsonDocument),
        }

        pool.execute_with_retries(query, params)

    except Exception:
        delete_disk_file(disk_path)
        raise

    return {
        "participant_id": participant_id,
        "application_id": application_id,
        "file_id": file_id,
        "photo_path": disk_path,
    }


# =========================================================
# CLOUD FUNCTION
# =========================================================

def handler(event, context):
    try:
        method = event.get("httpMethod", "")
        if method != "POST":
            return json_response(405, {"success": False, "error": "Method not allowed"})

        body = event.get("body")
        if not body:
            return json_response(400, {"success": False, "error": "Пустое тело запроса"})

        if isinstance(body, str):
            body_size = len(body.encode("utf-8"))
            if body_size > MAX_REQUEST_BYTES:
                return json_response(
                    413,
                    {"success": False, "error": "Размер заявки превышает допустимый"},
                )
            data = json.loads(body)
        elif isinstance(body, dict):
            data = body
        else:
            return json_response(
                400,
                {"success": False, "error": "Некорректный формат тела запроса"},
            )

        if not isinstance(data, dict):
            return json_response(400, {"success": False, "error": "JSON должен содержать объект"})

        result = save_application(data)

        return json_response(
            201,
            {
                "success": True,
                "message": "Заявка принята",
                "participant_id": result["participant_id"],
                "application_id": result["application_id"],
                "file_id": result["file_id"],
            },
        )

    except json.JSONDecodeError:
        return json_response(400, {"success": False, "error": "Некорректный JSON"})
    except ValueError as error:
        return json_response(400, {"success": False, "error": str(error)})
    except requests.HTTPError as error:
        response = error.response
        status = response.status_code if response is not None else "unknown"
        print("YANDEX DISK HTTP ERROR:", status, repr(error))
        return json_response(502, {"success": False, "error": "Не удалось сохранить фотографию"})
    except Exception as error:
        print("INTERNAL ERROR:", repr(error))
        return json_response(500, {"success": False, "error": "Внутренняя ошибка сервера"})

