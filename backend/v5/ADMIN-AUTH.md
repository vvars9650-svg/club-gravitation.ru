# Admin API authorization (TEST)

## Trust boundary

The Yandex API Gateway JWT authorizer is the only component that validates the
OIDC token signature and standard claims. It checks the TEST issuer, audience,
token lifetime, and required `sub` claim, then passes the verified result in
`requestContext.authorizer.jwt`.

`backend/v5/authorizer.py` is the backend authorization boundary. It accepts an
actor only from `authorizer.jwt.claims.sub` and permissions only from the
gateway-derived `authorizer.jwt.scopes` list. Headers, cookies, query
parameters, and request bodies cannot establish identity or permissions. A
direct Cloud Function invocation therefore fails closed.

## Roles and endpoint policy

The roles are represented as OIDC scopes:

| Scope | Permission |
| --- | --- |
| `admin:read` | List applications and read participant cards. |
| `admin:write` | PATCH the allowlisted operational fields. This is a separate mutation permission; it does not expand the PATCH allowlist. |

The gateway requires `admin:read` on `GET /admin/applications` and
`GET /admin/participants/{id}`, and `admin:write` on
`PATCH /admin/participants/{id}`. The backend repeats this method-level check.
The external Identity Hub administrator must assign these scopes to TEST
operators; no user list, role mapping, or credential is stored in this repo.

## Configuration and verification

`deployment/admin-api.test.yaml` is an additive gateway fragment. Merge its
`components` and `/admin/*` paths into the existing TEST gateway specification;
keep the public application and photo paths unchanged. Before any reviewed
TEST change, set only the non-secret variables `admin_function_id` and, if
needed, `admin_origin`/`admin_audience` for the TEST environment. The checked-in
`admin_origin` default is deliberately invalid; replace it with the exact HTTPS
Selectel origin (scheme + host + optional port, without `/admin-test/`) only in
the reviewed TEST gateway deployment. There is no client secret, access token,
or PROD value in this repository. This step does not deploy or update Yandex
Cloud.

The standalone frontend is built with `scripts/build-admin-selectel.js` and is
intended for `/admin-test/`. Its redirect URI must be registered exactly in the
TEST Single-Page Application client. The public site artifact continues to serve
a script-free placeholder at `/admin/` and never receives this Admin config.

Expected checks:

- no token or invalid token: rejected by Gateway with `401`;
- valid TEST token without the required scope: rejected with `403`;
- valid `admin:read`: list/card only;
- valid `admin:write`: PATCH only, with backend field allowlist and hashed audit actor;
- direct function invocation or spoofed client identity: backend `401`;
- public application, photo, legal, and TEST data flows: unchanged.

The current Admin contract does not return photo bytes or a presigned download
URL. It exposes the application `photo_object_id` only as stored form data, and
the UI deliberately does not render it. Private photo viewing requires a
separate authenticated backend endpoint and is outside this deployment step.
