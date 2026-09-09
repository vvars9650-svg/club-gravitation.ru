"""Closed, TEST-only Admin MVP contract.

Authentication is intentionally outside this module.  The public Cloud Function
handler fails closed for every /admin route until a gateway/auth integration
supplies an authenticated actor to ``admin_handler``.
"""

import hashlib
import json
import re
import uuid

from .repository import RepositoryUnavailable


ENVIRONMENT = "TEST"
STATUSES = (
    "Новая заявка", "На рассмотрении", "Нужен контакт", "Интервью назначено",
    "Интервью пройдено", "Одобрен", "Активный участник", "Пауза", "Не подходит",
)
OPERATIONAL_FIELDS = (
    "lifecycle_status", "owner", "priority", "next_action", "next_contact_at",
    "decision", "internal_comment",
)
LIST_SORTS = ("submitted_at", "full_name", "age", "city", "lifecycle_status", "priority", "next_contact_at")


class AdminError(Exception):
    def __init__(self, code, status=422):
        self.code, self.status = code, status


def _headers(event):
    return {str(key).lower(): value for key, value in event.get("headers", {}).items()}


def _actor_token(identity):
    """Keep audit identity stable without placing an email/login in the audit row."""
    return "auth-" + hashlib.sha256(str(identity).encode("utf-8")).hexdigest()[:16]


def list_arguments(params):
    params = params or {}
    sort = params.get("sort", "submitted_at")
    order = params.get("order", "desc")
    if sort not in LIST_SORTS:
        raise AdminError("invalid_sort")
    if order not in ("asc", "desc"):
        raise AdminError("invalid_order")
    return ({name: str(params.get(name, "")).strip() for name in ("q", "lifecycle_status", "owner", "priority", "decision")}, sort, order)


def validate_patch(data):
    if not isinstance(data, dict):
        raise AdminError("invalid_json", 400)
    unknown = set(data).difference(OPERATIONAL_FIELDS)
    if unknown:
        raise AdminError("immutable_or_unknown_field")
    if not data:
        raise AdminError("empty_patch")
    if "lifecycle_status" in data and data["lifecycle_status"] not in STATUSES:
        raise AdminError("invalid_lifecycle_status")
    changes = {}
    for name, value in data.items():
        if name == "next_contact_at":
            if value not in (None, "") and not re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:\d{2})?)?", str(value)):
                raise AdminError("invalid_next_contact_at")
            changes[name] = value or None
        else:
            value = str(value).strip()
            if len(value) > 2000:
                raise AdminError("operational_value_too_long")
            changes[name] = value
    return changes


def admin_response(status, body, request_id):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json", "Cache-Control": "no-store"},
        "body": json.dumps({**body, "request_id": request_id}, ensure_ascii=False, default=str),
    }


def admin_handler(event, context=None, repo=None, actor_identity=None):
    """Dispatch a request after external auth has established ``actor_identity``."""
    request_id = getattr(context, "request_id", None) or str(uuid.uuid4())
    path = event.get("path", "")
    method = event.get("httpMethod")
    if not actor_identity:
        return admin_response(404, {"error": {"code": "admin_not_published"}}, request_id)
    try:
        if repo is None:
            raise RepositoryUnavailable("admin_repository_required")
        if path.endswith("/admin/applications") and method == "GET":
            filters, sort, order = list_arguments(event.get("queryStringParameters"))
            return admin_response(200, {"environment": ENVIRONMENT, "applications": repo.list_admin_applications(filters, sort, order)}, request_id)
        match = re.fullmatch(r".*/admin/participants/([^/]+)", path)
        if not match:
            raise AdminError("not_found", 404)
        participant_id = match.group(1)
        if method == "GET":
            card = repo.get_admin_participant(participant_id)
            if not card:
                raise AdminError("participant_not_found", 404)
            return admin_response(200, card, request_id)
        if method == "PATCH":
            if not str(_headers(event).get("content-type", "")).startswith("application/json"):
                raise AdminError("unsupported_media_type", 415)
            changes = validate_patch(json.loads(event.get("body", "")))
            participant = repo.update_admin_participant(participant_id, changes, _actor_token(actor_identity), request_id)
            if not participant:
                raise AdminError("participant_not_found", 404)
            return admin_response(200, {"environment": ENVIRONMENT, "participant": participant, "changed_fields": sorted(changes)}, request_id)
        raise AdminError("method_not_allowed", 405)
    except RepositoryUnavailable as error:
        return admin_response(503, {"error": {"code": str(error)}}, request_id)
    except (ValueError, AdminError) as error:
        code = error.code if isinstance(error, AdminError) else "invalid_json"
        status = error.status if isinstance(error, AdminError) else 400
        return admin_response(status, {"error": {"code": code}}, request_id)
