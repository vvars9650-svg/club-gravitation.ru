# V5 TEST backend

Runtime: `python314`. Entry point: `index.handler`. Runtime dependency: `ydb==3.31.5`.

Build the deployment artifact from the repository root:

```text
python backend/v5/build_deployment.py --output backend/v5/dist/v5-deployment.zip
```

The ZIP layout is:

```text
index.py
requirements.txt
v5/
  __init__.py
  domain.py
  service.py
  repository.py
  ydb_repository.py
  factory.py
  admin.py
  handler.py
```

The builder uses an allowlist: tests, schema, `__pycache__`, `.pyc`, secrets and credentials are not packaged. Do not flatten `backend/v5`; `index.py` imports `handler` from the deployed `v5` package.

Required runtime variables are `YDB_ENDPOINT`, `YDB_DATABASE`, and `V5_TEST_CONSENT_TEXT_HASH` (the hash must start with `TEST-`). The Cloud Function service account supplies credentials. Runtime has no memory-storage fallback; `FakeRepository` is test injection only. Before deployment, manually review/apply schema, configure the TEST variables, deploy the ZIP, and configure the gateway. No migration or deployment is performed by the builder.

The runtime repository is created lazily on the first POST and reused for the lifetime of a warm Cloud Function instance. `GET /health` neither creates the repository nor opens a YDB connection. A failed initialization is not cached. There is no synthetic shutdown hook; `YdbRepository.close()` exists for explicit local and unit-test lifecycle management and closes the query session pool before the driver.

## Admin MVP (not published)

`backend/v5/admin.py` provides the TEST-only Admin contract for a future protected
route: list applications, participant card, and operational PATCH. The current
Cloud Function handler always returns `admin_not_published` for `/admin/*`.
STEP 7B must choose and deploy an external identity/gateway scheme that verifies
the operator and supplies an authenticated actor identity; there is no header,
token, or development bypass in this code. The only mutable fields are
`lifecycle_status`, `owner`, `priority`, `next_action`, `next_contact_at`,
`decision`, and `internal_comment`. Each PATCH emits a minimal `audit_log` action
containing a hashed actor token and changed field names, never a participant
payload. The existing schema is unchanged.

## STEP 7B OIDC/JWT foundation (not deployed)

The Admin SPA has an in-memory OIDC Authorization Code + PKCE client in
`assets/js/admin-auth.js`. It accepts only a TEST `window.__V5_ADMIN_AUTH_CONFIG__`
injected by the protected host. Required configuration is `environment: "TEST"`,
`issuer` or `openid_configuration_url`, `client_id`, `redirect_uri`, and scopes
(`openid email profile`; `groups` is not requested). Direct endpoint values may
also be injected as `authorization_endpoint` and `token_endpoint`. No client
secret, token, or production configuration belongs in the repository.

The access token is memory-only. The transient PKCE verifier/state is held in
`sessionStorage` solely across the authorization redirect; no `localStorage` is
used. The Admin API client sends `Authorization: Bearer <token>`, never cookie
credentials. On 401 it signs out locally and does not retry PATCH; on 403 it
shows access denied.

For `/admin/*`, `handler.py` reads only
`requestContext.authorizer.jwt.claims.sub` supplied by a future API Gateway JWT
authorizer. Missing context or `sub` fails closed. Client headers, cookies,
query parameters and body fields are ignored as actor sources. The raw `sub` is
hashed by the existing Admin layer before audit storage.

## STEP 8A lifecycle foundation (internal only)

`backend/v5/schema/002_v5_test_lifecycle.sql` is a non-breaking TEST migration. It adds nullable lifecycle fields to `participants`: `processing_blocked`, `processing_blocked_at`, `processing_block_reason`, and `processing_block_request_id`. It is deliberately not applied by CI, the builder, or runtime startup.

After reviewed TEST schema application, `YdbRepository.block_processing()` uses a serializable read/write transaction to set the block and add the minimal `processing_blocked` audit action. A repeated block is idempotent. Intake reads the same block within its transaction and returns `processing_blocked` without writing a participant, application, consent or creation audit event.

`find_participant`, `find_participant_by_phone`, and `find_application` are internal repository helpers only; there are no lifecycle HTTP routes. `destruction_plan()` is dry-run only: it returns IDs/counts (not contact values) and explicit classification for each record category: `contains_personal_data`, `contains_direct_contact_data`, `contains_linkable_identifiers`, and `retention_decision_required`. Consents, technical logs and audit logs are personal data through linkable identifiers even though they contain no direct contacts; technical-log classification applies to records linked by application/request identifiers. It never executes DELETE. Lifecycle audit action names are `processing_blocked`, `destruction_requested`, and `destruction_planned`; no client input or free-text PII is copied into these actions.
