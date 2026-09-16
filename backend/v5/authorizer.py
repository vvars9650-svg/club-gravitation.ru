"""Authorization boundary for the TEST Admin API.

The cryptographic JWT validation is performed by the Yandex API Gateway JWT
authorizer.  This module validates the *trusted result* of that authorizer
before an admin handler can access the repository.  It deliberately never
uses request headers, cookies, query parameters, or request bodies as an
identity or role source.
"""

from dataclasses import dataclass


READ_SCOPE = "admin:read"
WRITE_SCOPE = "admin:write"
ADMIN_SCOPES = (READ_SCOPE, WRITE_SCOPE)


class AdminAuthorizationError(Exception):
    """Controlled authentication/authorization failure for an admin route."""

    def __init__(self, code, status):
        self.code = code
        self.status = status
        super().__init__(code)


@dataclass(frozen=True)
class AdminPrincipal:
    """Validated identity and gateway-derived permissions for one request."""

    subject: str
    scopes: frozenset

    def can(self, required_scope):
        return required_scope in self.scopes


def _authorizer_context(event):
    try:
        context = event["requestContext"]["authorizer"]["jwt"]
    except (KeyError, TypeError):
        return None
    return context if isinstance(context, dict) else None


def _scope_set(value):
    if isinstance(value, str):
        return frozenset(item for item in value.split() if item)
    if isinstance(value, (list, tuple, set, frozenset)):
        return frozenset(item.strip() for item in value if isinstance(item, str) and item.strip())
    return frozenset()


def _claims(context):
    claims = context.get("claims")
    return claims if isinstance(claims, dict) else None


def authorize_admin(event, required_scope):
    """Return a principal only when gateway authentication and role pass.

    Yandex API Gateway supplies permissions as ``authorizer.jwt.scopes``.
    Token ``scope`` is intentionally not used as a fallback: requiring the
    gateway-derived list prevents a direct/injected function event from
    gaining admin access merely by copying a claim-shaped field.
    """

    if required_scope not in ADMIN_SCOPES:
        raise ValueError("unsupported_admin_scope")

    context = _authorizer_context(event)
    claims = _claims(context) if context else None
    if claims is None:
        raise AdminAuthorizationError("admin_authentication_required", 401)

    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject.strip():
        raise AdminAuthorizationError("admin_authentication_required", 401)

    scopes = _scope_set(context.get("scopes"))
    principal = AdminPrincipal(subject=subject.strip(), scopes=scopes)
    if not principal.can(required_scope):
        raise AdminAuthorizationError("admin_access_denied", 403)
    return principal


def required_scope_for_request(method):
    """Map the immutable/read and operational/mutate Admin API surface."""

    return WRITE_SCOPE if str(method or "").upper() == "PATCH" else READ_SCOPE
