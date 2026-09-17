"""Authorization boundary for the TEST Admin API.

The cryptographic JWT validation is performed by the Yandex API Gateway JWT
authorizer.  This module validates the *trusted result* of that authorizer
before an admin handler can access the repository.  It deliberately never
uses request headers, cookies, query parameters, or request bodies as an
identity or access source.
"""

from dataclasses import dataclass


class AdminAuthorizationError(Exception):
    """Controlled authentication/authorization failure for an admin route."""

    def __init__(self, code, status):
        self.code = code
        self.status = status
        super().__init__(code)


@dataclass(frozen=True)
class AdminPrincipal:
    """Identity established by the TEST Gateway JWT authorizer."""

    subject: str


def _authorizer_context(event):
    try:
        context = event["requestContext"]["authorizer"]["jwt"]
    except (KeyError, TypeError):
        return None
    return context if isinstance(context, dict) else None


def _claims(context):
    claims = context.get("claims")
    return claims if isinstance(claims, dict) else None


def authorize_admin(event):
    """Return the single full-access TEST operator established by Gateway.

    The Gateway validates signature, issuer, audience, lifetime and required
    ``sub``.  This boundary accepts identity only from that trusted authorizer
    context; scopes, headers, cookies, query parameters and bodies never grant
    access.
    """
    context = _authorizer_context(event)
    claims = _claims(context) if context else None
    if claims is None:
        raise AdminAuthorizationError("admin_authentication_required", 401)

    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject.strip():
        raise AdminAuthorizationError("admin_authentication_required", 401)

    return AdminPrincipal(subject=subject.strip())
