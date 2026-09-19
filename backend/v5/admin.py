"""Closed, TEST-only Admin MVP contract.

Authentication is intentionally outside this module.  The public Cloud Function
handler fails closed for every /admin route until a gateway/auth integration
supplies an authenticated actor to ``admin_handler``.
"""

import hashlib
import json
import re
import uuid
from datetime import datetime

from .repository import RepositoryUnavailable
from .participant_model import (
    APPLICATION_DECISIONS,
    APPLICATION_NEXT_ACTIONS,
    APPLICATION_OWNERS,
    APPLICATION_PRIORITIES,
    APPLICATION_STATUSES,
)


ENVIRONMENT = "TEST"
STATUSES = APPLICATION_STATUSES
DECISIONS = APPLICATION_DECISIONS
OWNERS = APPLICATION_OWNERS
PRIORITIES = APPLICATION_PRIORITIES
NEXT_ACTIONS = APPLICATION_NEXT_ACTIONS
WORKFLOW_ACTIONS = {
    "Новая заявка": ("Рассмотреть",),
    "На рассмотрении": ("Назначить интервью", "Связаться"),
    "Нужен контакт": ("Связаться",),
    "Интервью назначено": ("Провести интервью",),
    "Интервью пройдено": ("Обсудить",),
    "Одобрен": ("Пригласить",),
    "Ожидаем ответ": ("Дождаться ответа", "Добавить в участники"),
    "Пауза": ("Связаться позже",),
    "Активный участник": (),
    "Не подходит": (),
}
NEXT_CONTACT_REQUIRED_STATUSES = {"Интервью назначено", "Пауза"}
OPERATIONAL_FIELDS = (
    "owner", "priority", "next_action", "next_contact_at", "decision",
    "internal_comment",
)
LIST_SORTS = ("submitted_at", "application_number", "full_name", "age", "city", "status", "priority", "next_contact_at")


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
    return ({name: str(params.get(name, "")).strip() for name in ("q", "status", "owner", "priority", "decision")}, sort, order)


def validate_patch(data):
    if not isinstance(data, dict):
        raise AdminError("invalid_json", 400)
    unknown = set(data).difference(OPERATIONAL_FIELDS)
    if unknown:
        raise AdminError("immutable_or_unknown_field")
    if not data:
        raise AdminError("empty_patch")
    changes = {}
    for name, value in data.items():
        if name == "next_contact_at":
            if value not in (None, ""):
                candidate = str(value)
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:\d{2})?", candidate):
                    raise AdminError("invalid_next_contact_at")
                try:
                    datetime.fromisoformat(candidate.replace("Z", "+00:00"))
                except ValueError as error:
                    raise AdminError("invalid_next_contact_at") from error
            changes[name] = value or None
        elif name == "owner":
            value = str(value).strip()
            if value and value not in OWNERS:
                raise AdminError("invalid_owner")
            changes[name] = value
        elif name == "priority":
            value = str(value).strip()
            if value and value not in PRIORITIES:
                raise AdminError("invalid_priority")
            changes[name] = value
        elif name == "next_action":
            value = str(value).strip()
            if value and value not in NEXT_ACTIONS:
                raise AdminError("invalid_next_action")
            changes[name] = value
        elif name == "decision":
            value = str(value).strip()
            if value and value not in DECISIONS:
                raise AdminError("invalid_decision")
            changes[name] = value
        else:
            value = str(value).strip()
            if len(value) > 2000:
                raise AdminError("operational_value_too_long")
            changes[name] = value
    return changes


def validate_workflow(status, next_action, next_contact_at, strict=False):
    """Validate the CRM V2 status/action pair after a repository merges a PATCH."""
    allowed = WORKFLOW_ACTIONS.get(status)
    if allowed is None:
        raise AdminError("invalid_status")
    if next_action and next_action not in allowed:
        raise AdminError("invalid_next_action_for_status")
    if not strict:
        return
    if allowed and not next_action:
        raise AdminError("next_action_required")
    if not allowed and next_action:
        raise AdminError("next_action_not_allowed")
    if status in NEXT_CONTACT_REQUIRED_STATUSES and not next_contact_at:
        raise AdminError("next_contact_required")


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
            return admin_response(200, {"environment": getattr(repo, "environment", ENVIRONMENT), "applications": repo.list_admin_applications(filters, sort, order)}, request_id)
        match = re.fullmatch(r".*/admin/(applications|participants)/([^/]+)", path)
        if not match:
            raise AdminError("not_found", 404)
        path_params = event.get("pathParams") or {}
        application_id = path_params.get("id") if isinstance(path_params, dict) else None
        if not application_id:
            application_id = match.group(2)
        legacy_participant_path = match.group(1) == "participants"
        if method == "GET":
            card = repo.get_admin_application(application_id)
            if not card and legacy_participant_path:
                card = repo.get_admin_participant(application_id)
            if not card:
                raise AdminError("application_not_found", 404)
            return admin_response(200, card, request_id)
        if method == "PATCH":
            if not str(_headers(event).get("content-type", "")).startswith("application/json"):
                raise AdminError("unsupported_media_type", 415)
            changes = validate_patch(json.loads(event.get("body", "")))
            if legacy_participant_path and not repo.get_admin_application(application_id):
                legacy_card = repo.get_admin_participant(application_id)
                if legacy_card:
                    application_id = legacy_card["application"]["application_id"]
            application = repo.update_admin_application(application_id, changes, _actor_token(actor_identity), request_id)
            if not application:
                raise AdminError("application_not_found", 404)
            return admin_response(200, {"environment": getattr(repo, "environment", ENVIRONMENT), "application": application, "changed_fields": sorted(changes)}, request_id)
        raise AdminError("method_not_allowed", 405)
    except RepositoryUnavailable as error:
        return admin_response(503, {"error": {"code": str(error)}}, request_id)
    except (ValueError, AdminError) as error:
        code = error.code if isinstance(error, AdminError) else "invalid_json"
        status = error.status if isinstance(error, AdminError) else 400
        return admin_response(status, {"error": {"code": code}}, request_id)
