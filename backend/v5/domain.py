import hashlib
import json
import re
from datetime import datetime, timezone

FORM_VERSION = "FORM-2.2"
CONSENT_VERSION = "CONSENT-PD-2.2"
POLICY_VERSION = "PPD-2.2"

FORM_FIELDS = (
    "full_name age gender city visit_krasnodar phone email preferred_contact "
    "profile_or_messenger_url public_profile_url occupation life_outside_work "
    "what_interested what_participant_brings what_friends_value desired_connections "
    "desired_connections_other values_in_people barriers_to_meeting acquaintance_methods "
    "acquaintance_methods_other return_reason source photo_object_id"
).split()
MULTI_FIELDS = {"desired_connections", "acquaintance_methods"}
REMOVED_FORM_FIELDS = {
    "telegram", "interests", "event_expectations", "social_comfort", "initiative",
    "acquaintance_scenario", "successful_evening", "unacceptable_behavior",
    "convenient_days", "comfortable_price",
}
GENDERS = {"Мужчина", "Женщина"}
VISIT_OPTIONS = {"Да, регулярно", "Да, время от времени", "Пока не уверен(а)"}
CONTACT_OPTIONS = {
    "", "по телефону", "по email",
    "через профиль или мессенджер по указанной ссылке",
}
DESIRED_CONNECTION_OPTIONS = {
    "Романтические отношения", "Новые друзья", "Близкие по духу люди",
    "Партнёрство / бизнес", "Творческие и совместные проекты",
    "Новый круг общения и впечатления", "Интересные люди без заданной цели",
    "Весело провести время", "Другое",
}
ACQUAINTANCE_METHOD_OPTIONS = {
    "Через общее дело или занятие", "Через живой разговор",
    "Через игру или активность", "Когда знакомят друзья",
    "Когда первый шаг делает другой человек", "Зависит от человека и ситуации",
    "Другое",
}
SOURCE_OPTIONS = {
    "Сайт / поиск", "От знакомого / рекомендация", "Мессенджер",
    "Социальные сети", "Сайт знакомств", "Другое",
}


class DomainError(Exception):
    def __init__(self, code, status=422):
        self.code, self.status = code, status


def fingerprint(data):
    safe = {key: data.get(key) for key in FORM_FIELDS}
    return hashlib.sha256(
        json.dumps(safe, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def phone(value):
    raw = str(value or "").strip()
    if (
        not raw
        or re.search(r"[^\d+\s()-]", raw)
        or ("+" in raw and not re.match(r"^\+\d", raw))
        or (raw.startswith("+") and not raw.startswith("+7"))
        or raw.count("+") > 1
    ):
        raise DomainError("invalid_phone")
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 11:
        if digits[0] not in "78":
            raise DomainError("invalid_phone")
        digits = digits[1:]
    if not re.fullmatch(r"\d{10}", digits):
        raise DomainError("invalid_phone")
    return "+7" + digits


def _required_text(data, fields):
    for key in fields:
        if not str(data.get(key, "")).strip():
            raise DomainError("missing_" + key)


def _url(data, field):
    value = str(data.get(field, "")).strip()
    if value and not re.fullmatch(r"https?://[^\s]+", value, re.IGNORECASE):
        raise DomainError("invalid_" + field)


def _multi(data, field, allowed):
    value = data.get(field)
    if not isinstance(value, list) or not value:
        raise DomainError("invalid_" + field)
    if any(not isinstance(item, str) or item not in allowed for item in value):
        raise DomainError("invalid_" + field)
    if len(value) != len(set(value)):
        raise DomainError("invalid_" + field)
    return value


def validate(data):
    if not isinstance(data, dict):
        raise DomainError("invalid_json", 400)
    if data.get("policy_acknowledged") is not True:
        raise DomainError("policy_acknowledgement_required")
    if data.get("personal_data_consent") is not True:
        raise DomainError("consent_required")
    if (
        data.get("consent_version") != CONSENT_VERSION
        or data.get("policy_version") != POLICY_VERSION
        or data.get("form_version") != FORM_VERSION
    ):
        raise DomainError("invalid_legal_version")
    if REMOVED_FORM_FIELDS.intersection(data):
        raise DomainError("legacy_form_fields_not_allowed")

    _required_text(
        data,
        ("full_name", "gender", "city", "email", "occupation", "life_outside_work", "source"),
    )
    try:
        age = int(data.get("age"))
    except (TypeError, ValueError):
        raise DomainError("invalid_age")
    if not 25 <= age <= 52:
        raise DomainError("invalid_age")
    if data["gender"] not in GENDERS:
        raise DomainError("invalid_gender")
    visit = str(data.get("visit_krasnodar", "")).strip()
    if data["city"] != "Краснодар" and visit not in VISIT_OPTIONS:
        raise DomainError("missing_visit_krasnodar" if not visit else "invalid_visit_krasnodar")
    if data["city"] == "Краснодар" and visit:
        raise DomainError("invalid_visit_krasnodar")
    if data.get("preferred_contact", "") not in CONTACT_OPTIONS:
        raise DomainError("invalid_preferred_contact")
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", str(data["email"]).strip()):
        raise DomainError("invalid_email")
    _url(data, "profile_or_messenger_url")
    _url(data, "public_profile_url")

    desired = _multi(data, "desired_connections", DESIRED_CONNECTION_OPTIONS)
    methods = _multi(data, "acquaintance_methods", ACQUAINTANCE_METHOD_OPTIONS)
    if "Другое" in desired and not str(data.get("desired_connections_other", "")).strip():
        raise DomainError("missing_desired_connections_other")
    if "Другое" not in desired and str(data.get("desired_connections_other", "")).strip():
        raise DomainError("unexpected_desired_connections_other")
    if "Другое" in methods and not str(data.get("acquaintance_methods_other", "")).strip():
        raise DomainError("missing_acquaintance_methods_other")
    if "Другое" not in methods and str(data.get("acquaintance_methods_other", "")).strip():
        raise DomainError("unexpected_acquaintance_methods_other")
    if data["source"] not in SOURCE_OPTIONS:
        raise DomainError("invalid_source")

    # Imported here to keep the photo module's DomainError dependency acyclic.
    from .photo_contract import validate_photo_object_id
    photo_object_id = validate_photo_object_id(data.get("photo_object_id"))

    out = {
        key: data.get(key, [] if key in MULTI_FIELDS else "")
        for key in FORM_FIELDS
    }
    out["age"] = age
    out["phone"] = phone(data.get("phone"))
    out["photo_object_id"] = photo_object_id
    return out


def ids(key):
    digest = hashlib.sha256(key.encode()).hexdigest()[:20]
    return "APP-" + digest, "CONS-" + digest


def now():
    return datetime.now(timezone.utc).isoformat()
