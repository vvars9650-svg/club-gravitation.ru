import base64
import hashlib
import json
import os
import re
import secrets
import uuid
from datetime import datetime, timezone
from urllib.parse import parse_qs

import requests
import ydb
import ydb.iam


# =========================================================
# CONFIG
# =========================================================

PD_CONSENT_VERSION = os.getenv("PD_CONSENT_VERSION", "pd-test-v1")
RULES_VERSION = os.getenv("RULES_VERSION", "rules-test-v1")
CONTACT_CONSENT_VERSION = os.getenv("CONTACT_CONSENT_VERSION", "contact-test-v1")

MAX_REQUEST_BYTES = int(os.getenv("MAX_REQUEST_BYTES", "2300000"))
MAX_PHOTO_BYTES = int(os.getenv("MAX_PHOTO_BYTES", "1500000"))
DISK_PHOTO_DIR = os.getenv(
    "YANDEX_DISK_PHOTO_DIR",
    "/ГРАВИТАЦИЯ/Участники/Фото",
)

PHONE_RE = re.compile(r"^\+7\d{10}$")
EMAIL_RE = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+"
    r"@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$"
)
IDEMPOTENCY_KEY_RE = re.compile(r"^[A-Za-z0-9._:-]{16,128}$")

FIELD_LIMITS = {
    "full_name": 150,
    "gender": 50,
    "city": 150,
    "visit_krasnodar": 100,
    "phone": 12,
    "telegram": 150,
    "vk": 300,
    "instagram": 300,
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

ALIASES = {
    "name": "full_name",
    "city_visit": "visit_krasnodar",
    "life_beyond_work": "life_outside_work",
    "interest_reason": "what_interested",
    "expectations": "event_expectations",
    "connection_goal": "desired_connections",
    "values_people": "values_in_people",
    "meeting_barriers": "barriers_to_meeting",
    "introduction_scenario": "acquaintance_scenario",
    "personal_data_consent": "pd_consent",
    "rules_consent": "rules_accepted",
    "submitted_at_client": "client_timestamp",
}


# =========================================================
# LAZY YDB CLIENT
# =========================================================

_driver = None
_pool = None


def get_pool():
    global _driver, _pool
    if _pool is None:
        endpoint = os.getenv("YDB_ENDPOINT")
        database = os.getenv("YDB_DATABASE")
        if not endpoint or not database:
            raise RuntimeError("YDB_ENDPOINT and YDB_DATABASE must be configured")

        _driver = ydb.Driver(
            endpoint=endpoint,
            database=database,
            credentials=ydb.iam.MetadataUrlCredentials(),
        )
        _driver.wait(fail_fast=True, timeout=5)
        _pool = ydb.QuerySessionPool(_driver)
    return _pool


# =========================================================
# ERRORS
# =========================================================

class ParticipantConflictError(RuntimeError):
    """Submitted contacts match more than one participant."""


class IdempotencyConflictError(RuntimeError):
    """An idempotency key was already used with another payload."""


class SpamDetectedError(RuntimeError):
    """Honeypot was filled."""


# =========================================================
# HELPERS
# =========================================================

def log_event(request_id, event, level="INFO", **fields):
    record = {
        "level": level,
        "event": event,
        "request_id": request_id,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    record.update(fields)
    print(json.dumps(record, ensure_ascii=False, separators=(",", ":")))


def json_response(status_code, data, request_id=""):
    headers = {
        "Content-Type": "application/json; charset=utf-8",
    }
    if request_id:
        headers["X-Request-Id"] = request_id
        data = dict(data)
        data.setdefault("request_id", request_id)

    return {
        "statusCode": status_code,
        "headers": headers,
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


def normalize_phone(value):
    raw = clean_string(value)
    digits = re.sub(r"\D", "", raw)

    if len(digits) == 11 and digits[0] in ("7", "8"):
        digits = digits[1:]
    if len(digits) == 10:
        return "+7" + digits
    return raw


def normalize_email(value):
    return clean_string(value).lower()


def normalize_telegram(value):
    value = clean_string(value)
    if not value:
        return ""

    lower = value.lower()
    for prefix in ("https://t.me/", "http://t.me/", "t.me/"):
        if lower.startswith(prefix):
            value = value[len(prefix):]
            break

    value = value.strip().lstrip("@").strip()
    return f"@{value.lower()}" if value else ""


def normalize_payload(data):
    normalized = dict(data)

    for old_name, canonical_name in ALIASES.items():
        if canonical_name not in normalized and old_name in normalized:
            normalized[canonical_name] = normalized[old_name]

    normalized["phone"] = normalize_phone(normalized.get("phone"))
    normalized["email"] = normalize_email(normalized.get("email"))
    normalized["telegram"] = normalize_telegram(normalized.get("telegram"))

    return normalized


def header_value(event, name):
    headers = event.get("headers") or {}
    target = name.lower()
    for key, value in headers.items():
        if str(key).lower() == target:
            return clean_string(value)
    return ""


def request_id_from_context(context):
    for attr in ("request_id", "requestId"):
        value = getattr(context, attr, None)
        if value:
            return str(value)
    return "REQ-" + uuid.uuid4().hex[:20].upper()


def validate_idempotency_key(value):
    key = clean_string(value)
    if not key:
        raise ValueError("Не указан Idempotency-Key")
    if not IDEMPOTENCY_KEY_RE.fullmatch(key):
        raise ValueError(
            "Idempotency-Key должен содержать 16–128 символов: "
            "латинские буквы, цифры, '.', '_', ':', '-'"
        )
    return key


def stable_id(prefix, idempotency_key, purpose, length=20):
    digest = hashlib.sha256(
        f"{purpose}:{idempotency_key}".encode("utf-8")
    ).hexdigest().upper()
    return f"{prefix}-{digest[:length]}"


def create_participant_id():
    now = datetime.now(timezone.utc)
    suffix = secrets.token_hex(4).upper()
    return f"GR-{now:%y%m%d-%H%M%S}-{suffix}"


def parse_event_body(event):
    body = event.get("body")
    if body is None or body == "":
        raise ValueError("Пустое тело запроса")

    if isinstance(body, dict):
        return body

    if not isinstance(body, str):
        raise ValueError("Некорректный формат тела запроса")

    if event.get("isBase64Encoded"):
        try:
            body_bytes = base64.b64decode(body, validate=True)
            body = body_bytes.decode("utf-8")
        except Exception as exc:
            raise ValueError("Некорректное base64-тело запроса") from exc

    if len(body.encode("utf-8")) > MAX_REQUEST_BYTES:
        raise OverflowError("Размер заявки превышает допустимый")

    content_type = header_value(event, "content-type").split(";", 1)[0].strip().lower()

    if content_type in ("", "application/json", "text/json"):
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError as exc:
            raise ValueError("Некорректный JSON") from exc
        if not isinstance(parsed, dict):
            raise ValueError("JSON должен содержать объект")
        return parsed

    if content_type == "application/x-www-form-urlencoded":
        parsed_qs = parse_qs(body, keep_blank_values=True)
        return {key: values[-1] if values else "" for key, values in parsed_qs.items()}

    raise TypeError("Поддерживается только application/json")


# =========================================================
# PHOTO + IDEMPOTENCY FINGERPRINT
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


def build_payload_snapshot(data, photo_bytes):
    snapshot = dict(data)
    snapshot.pop("photo_data", None)
    snapshot.pop("idempotency_key", None)
    snapshot.pop("website", None)
    snapshot["photo_attached"] = True
    snapshot["photo_sha256"] = hashlib.sha256(photo_bytes).hexdigest()

    canonical = json.dumps(
        snapshot,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    snapshot["idempotency_fingerprint"] = fingerprint
    return snapshot, fingerprint


def extract_stored_fingerprint(raw_payload):
    if raw_payload is None:
        return ""

    if isinstance(raw_payload, dict):
        data = raw_payload
    else:
        try:
            data = json.loads(str(raw_payload))
        except (TypeError, ValueError, json.JSONDecodeError):
            return ""

    return clean_string(data.get("idempotency_fingerprint"))


# =========================================================
# YDB LOOKUPS
# =========================================================

def _rows(result_sets):
    if not result_sets:
        return []
    return result_sets[0].rows or []


def _first_value(row, key, default=""):
    try:
        value = row[key]
    except (KeyError, TypeError):
        return default
    return value if value is not None else default


def find_participant_by_index(index_name, column_name, value):
    if not value:
        return []

    allowed = {
        ("idx_participants_phone", "phone"),
        ("idx_participants_email", "email"),
        ("idx_participants_telegram", "telegram"),
    }
    if (index_name, column_name) not in allowed:
        raise RuntimeError("Unsupported participant index")

    query = f"""
    DECLARE $value AS Utf8;

    SELECT participant_id
    FROM participants VIEW {index_name}
    WHERE {column_name} = $value
    LIMIT 3;
    """

    result_sets = get_pool().execute_with_retries(query, {"$value": value})
    return [
        clean_string(_first_value(row, "participant_id"))
        for row in _rows(result_sets)
        if clean_string(_first_value(row, "participant_id"))
    ]


def find_existing_participant(phone, email="", telegram=""):
    participant_ids = set()

    participant_ids.update(
        find_participant_by_index("idx_participants_phone", "phone", phone)
    )
    if email:
        participant_ids.update(
            find_participant_by_index("idx_participants_email", "email", email)
        )
    if telegram:
        participant_ids.update(
            find_participant_by_index("idx_participants_telegram", "telegram", telegram)
        )

    if len(participant_ids) > 1:
        raise ParticipantConflictError(
            "Контактные данные совпадают с несколькими участниками"
        )

    return next(iter(participant_ids)) if participant_ids else None


def find_existing_application(application_id):
    query = """
    DECLARE $application_id AS Utf8;

    SELECT participant_id, raw_payload
    FROM applications
    WHERE application_id = $application_id;

    SELECT file_id
    FROM files VIEW idx_files_application
    WHERE application_id = $application_id
    LIMIT 1;
    """

    result_sets = get_pool().execute_with_retries(
        query,
        {"$application_id": application_id},
    )

    if not result_sets or not result_sets[0].rows:
        return None

    row = result_sets[0].rows[0]
    file_id = ""
    if len(result_sets) > 1 and result_sets[1].rows:
        file_id = clean_string(_first_value(result_sets[1].rows[0], "file_id"))

    return {
        "participant_id": clean_string(_first_value(row, "participant_id")),
        "raw_payload": _first_value(row, "raw_payload", None),
        "file_id": file_id,
    }


# =========================================================
# YANDEX DISK OAUTH + FILES
# =========================================================

_disk_access_token = None


def current_disk_access_token():
    global _disk_access_token
    if _disk_access_token:
        return _disk_access_token

    token = os.getenv("YANDEX_DISK_ACCESS_TOKEN")
    if not token:
        raise RuntimeError("YANDEX_DISK_ACCESS_TOKEN is not configured")

    _disk_access_token = token
    return token


def refresh_disk_access_token():
    global _disk_access_token

    refresh_token = os.getenv("YANDEX_DISK_REFRESH_TOKEN")
    client_id = os.getenv("YANDEX_OAUTH_CLIENT_ID")
    client_secret = os.getenv("YANDEX_OAUTH_CLIENT_SECRET")

    if not refresh_token or not client_id or not client_secret:
        raise RuntimeError("Yandex OAuth refresh credentials are not configured")

    response = requests.post(
        "https://oauth.yandex.ru/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=15,
    )
    response.raise_for_status()

    token = clean_string(response.json().get("access_token"))
    if not token:
        raise RuntimeError("Yandex OAuth did not return access_token")

    _disk_access_token = token
    return token


def disk_api_request(method, url, **kwargs):
    headers = dict(kwargs.pop("headers", {}) or {})
    headers["Authorization"] = f"OAuth {current_disk_access_token()}"

    response = requests.request(method, url, headers=headers, **kwargs)

    if response.status_code == 401:
        headers["Authorization"] = f"OAuth {refresh_disk_access_token()}"
        response = requests.request(method, url, headers=headers, **kwargs)

    response.raise_for_status()
    return response


def upload_photo_to_disk(photo_bytes, participant_id, application_id, extension):
    disk_path = f"{DISK_PHOTO_DIR}/{participant_id}-{application_id}{extension}"

    link_response = disk_api_request(
        "GET",
        "https://cloud-api.yandex.net/v1/disk/resources/upload",
        params={
            "path": disk_path,
            "overwrite": "true",
        },
        timeout=15,
    )

    upload_url = clean_string(link_response.json().get("href"))
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


def delete_disk_file(disk_path, request_id=""):
    if not disk_path:
        return

    try:
        disk_api_request(
            "DELETE",
            "https://cloud-api.yandex.net/v1/disk/resources",
            params={
                "path": disk_path,
                "permanently": "true",
            },
            timeout=15,
        )
    except Exception as error:
        log_event(
            request_id,
            "disk_cleanup_failed",
            level="ERROR",
            error_type=type(error).__name__,
        )


# =========================================================
# VALIDATION
# =========================================================

def validate_application(data):
    full_name = validate_string("full_name", data.get("full_name"))
    gender = validate_string("gender", data.get("gender"))
    city = validate_string("city", data.get("city"))
    visit_krasnodar = validate_string(
        "visit_krasnodar",
        data.get("visit_krasnodar"),
    )
    phone = validate_string("phone", normalize_phone(data.get("phone")))
    telegram = validate_string("telegram", normalize_telegram(data.get("telegram")))
    vk = validate_string("vk", data.get("vk"))
    instagram = validate_string("instagram", data.get("instagram"))
    email = validate_string("email", normalize_email(data.get("email")))
    preferred_contact = validate_string(
        "preferred_contact",
        data.get("preferred_contact"),
    )

    if not full_name or len(full_name) < 2:
        raise ValueError("Не указаны имя и фамилия")
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

    validated = {
        "full_name": full_name,
        "age": age,
        "gender": gender,
        "city": city,
        "visit_krasnodar": visit_krasnodar,
        "phone": phone,
        "telegram": telegram,
        "vk": vk,
        "instagram": instagram,
        "email": email,
        "preferred_contact": preferred_contact,
        "pd_consent": pd_consent,
        "rules_accepted": rules_accepted,
        "contact_consent": contact_consent,
    }

    for name in (
        "occupation",
        "life_outside_work",
        "interests",
        "relationship_context",
        "desired_connections",
        "values_in_people",
        "barriers_to_meeting",
        "source",
        "what_interested",
        "event_expectations",
        "successful_evening",
        "return_reason",
        "social_comfort",
        "initiative",
        "acquaintance_scenario",
        "unacceptable_behavior",
        "convenient_days",
        "comfortable_price",
        "application_channel",
        "page_url",
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_content",
        "utm_term",
        "referrer",
        "user_agent",
    ):
        value = data.get(name)
        if name == "application_channel" and not clean_string(value):
            value = "website"
        validated[name] = validate_string(name, value)

    return validated


# =========================================================
# SAVE APPLICATION
# =========================================================

def save_application(data, idempotency_key, request_id):
    if clean_string(data.get("website")):
        raise SpamDetectedError()

    normalized = normalize_payload(data)
    validated = validate_application(normalized)
    photo_bytes, mime_type, extension = decode_photo(normalized)

    snapshot_source = dict(normalized)
    snapshot_source.update(validated)
    payload_snapshot, request_fingerprint = build_payload_snapshot(
        snapshot_source,
        photo_bytes,
    )
    raw_payload_json = json.dumps(
        payload_snapshot,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    application_id = stable_id("APP", idempotency_key, "application", 20)
    pd_consent_id = stable_id("CONS", idempotency_key, "consent-pd", 20)
    rules_consent_id = stable_id("CONS", idempotency_key, "consent-rules", 20)
    contact_consent_id = stable_id("CONS", idempotency_key, "consent-contact", 20)
    audit_id = stable_id("AUD", idempotency_key, "audit-application", 20)
    file_id = stable_id("FILE", idempotency_key, "profile-photo", 20)

    existing_application = find_existing_application(application_id)
    if existing_application:
        stored_fingerprint = extract_stored_fingerprint(
            existing_application.get("raw_payload")
        )
        if not stored_fingerprint or stored_fingerprint != request_fingerprint:
            raise IdempotencyConflictError(
                "Idempotency-Key уже использован для другой заявки"
            )

        return {
            "participant_id": existing_application["participant_id"],
            "application_id": application_id,
            "file_id": existing_application.get("file_id") or file_id,
            "participant_reused": True,
            "idempotent_replay": True,
        }

    participant_id = find_existing_participant(
        phone=validated["phone"],
        email=validated["email"],
        telegram=validated["telegram"],
    )
    participant_reused = participant_id is not None
    if not participant_id:
        participant_id = create_participant_id()

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

    disk_path = ""
    try:
        disk_path = upload_photo_to_disk(
            photo_bytes,
            participant_id,
            application_id,
            extension,
        )

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
        UPSERT INTO applications (
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

        query = declarations + participant_write + dependent_writes

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
            "$pd_consent_version": PD_CONSENT_VERSION,
            "$rules_version": RULES_VERSION,
            "$contact_consent_version": CONTACT_CONSENT_VERSION,
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

        get_pool().execute_with_retries(query, params)

    except Exception:
        delete_disk_file(disk_path, request_id=request_id)
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
    request_id = request_id_from_context(context)

    try:
        method = clean_string(event.get("httpMethod")).upper()
        if method != "POST":
            return json_response(
                405,
                {
                    "success": False,
                    "error": "Method not allowed",
                    "code": "method_not_allowed",
                },
                request_id,
            )

        data = parse_event_body(event)
        idempotency_key = validate_idempotency_key(
            header_value(event, "idempotency-key")
            or data.get("idempotency_key")
        )

        result = save_application(
            data,
            idempotency_key=idempotency_key,
            request_id=request_id,
        )

        status_code = 200 if result["idempotent_replay"] else 201
        log_event(
            request_id,
            "application_accepted",
            application_id=result["application_id"],
            participant_id=result["participant_id"],
            participant_reused=result["participant_reused"],
            idempotent_replay=result["idempotent_replay"],
        )

        return json_response(
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
        return json_response(
            413,
            {
                "success": False,
                "error": str(error),
                "code": "payload_too_large",
            },
            request_id,
        )
    except TypeError as error:
        return json_response(
            415,
            {
                "success": False,
                "error": str(error),
                "code": "unsupported_media_type",
            },
            request_id,
        )
    except SpamDetectedError:
        log_event(request_id, "honeypot_rejected", level="WARNING")
        return json_response(
            201,
            {
                "success": True,
                "message": "Заявка принята",
            },
            request_id,
        )
    except IdempotencyConflictError as error:
        log_event(request_id, "idempotency_conflict", level="WARNING")
        return json_response(
            409,
            {
                "success": False,
                "error": str(error),
                "code": "idempotency_conflict",
            },
            request_id,
        )
    except ParticipantConflictError:
        log_event(request_id, "participant_conflict", level="WARNING")
        return json_response(
            409,
            {
                "success": False,
                "error": "Контактные данные требуют ручной проверки",
                "code": "participant_conflict",
            },
            request_id,
        )
    except ValueError as error:
        return json_response(
            400,
            {
                "success": False,
                "error": str(error),
                "code": "validation_error",
            },
            request_id,
        )
    except requests.HTTPError as error:
        response = error.response
        status = response.status_code if response is not None else "unknown"
        log_event(
            request_id,
            "yandex_disk_http_error",
            level="ERROR",
            upstream_status=status,
        )
        return json_response(
            502,
            {
                "success": False,
                "error": "Не удалось сохранить фотографию",
                "code": "file_storage_error",
            },
            request_id,
        )
    except Exception as error:
        log_event(
            request_id,
            "internal_error",
            level="ERROR",
            error_type=type(error).__name__,
        )
        return json_response(
            500,
            {
                "success": False,
                "error": "Внутренняя ошибка сервера",
                "code": "internal_error",
            },
            request_id,
        )
