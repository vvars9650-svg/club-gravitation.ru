# V5 TEST backend

Runtime: `python314`. Entry point: `index.handler`. Runtime dependencies are
listed and pinned in `requirements.txt`.

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
  image_codec.py
  object_storage.py
  photo_contract.py
  photo_upload_service.py
  service.py
  repository.py
  ydb_repository.py
  factory.py
  authorizer.py
  admin.py
  handler.py
```

The builder uses an allowlist: tests, schema, `__pycache__`, `.pyc`, secrets and credentials are not packaged. Do not flatten `backend/v5`; `index.py` imports `handler` from the deployed `v5` package.

Required runtime variables are `YDB_ENDPOINT`, `YDB_DATABASE`,
`V5_TEST_CONSENT_TEXT_HASH` (the hash must start with `TEST-`), and
`V5_TEST_PHOTO_BUCKET`. The Cloud Function invocation token supplies Object
Storage and PresignService authentication; no static keys are used. Runtime has
no memory-storage fallback; `FakeRepository` is test injection only. Before
deployment, manually review/apply schema, configure the TEST variables, deploy
the ZIP, and configure the gateway. No migration or deployment is performed by
the builder.

The runtime repository is created lazily on the first POST and reused for the lifetime of a warm Cloud Function instance. `GET /health` neither creates the repository nor opens a YDB connection. A failed initialization is not cached. There is no synthetic shutdown hook; `YdbRepository.close()` exists for explicit local and unit-test lifecycle management and closes the query session pool before the driver.

## Protected Admin API (TEST-ready)

`backend/v5/admin.py` provides the TEST-only Admin contract for the application
list, application card, and application-scoped operational PATCH. `authorizer.py` is the
backend authorization boundary for a Yandex API Gateway JWT authorizer:
unauthenticated `/admin/*` requests fail closed.
There is no header, token, or development bypass in this code. Status is read-only;
the only mutable fields are `owner`, `priority`, `next_action`, `next_contact_at`,
`decision`, and `internal_comment`. A non-empty decision atomically becomes the
Application status. Each PATCH emits a minimal `audit_log` action
containing a hashed actor token and changed field names, never a participant
payload. Authorization and gateway configuration are
documented in `ADMIN-AUTH.md` and `deployment/admin-api.test.yaml`; they are
TEST-only artifacts and are not deployed by this repository.

## Admin CRM V2 migration 008 (prepared, not applied)

`schema/008_admin_crm_v2.sql` is additive TEST-only DDL. It adds Application-owned
`owner`, `priority`, `next_action`, `next_contact_at`, and `internal_comment`, plus
the duplicate warning summary. Existing `application_status` and `decision` from
migration 005 become the CRM V2 status/decision fields. It creates:

- `application_phone_keys`, whose `(environment, normalized_phone)` primary key
  maps the normalized pilot phone to the one original Application and protects
  concurrent POST requests at the database transaction boundary;
- `application_submission_keys`, which maps a rejected duplicate submission's
  deterministic idempotency identifier to the original Application without
  retaining a second form or consuming an application number.

The runtime handles a duplicate inside the same serializable transaction: it
keeps the original Application and Participant unchanged, increments the original
warning count, records `duplicate_submission|basis=normalized_phone` in
`audit_log`, records a minimal technical success event, schedules the unused new
photo for deletion, and returns the original number. Secondary identifiers are
not automatic merge keys.

The SQL file deliberately contains no data-changing backfill. The executable
TEST-only data-plane procedure is now implemented in
[`migration_008_runner.py`](migration_008_runner.py); see
[`MIGRATION-008-RUNBOOK.md`](MIGRATION-008-RUNBOOK.md) for exact phased commands,
recovery, verification and STOP conditions. `migration_008.py` remains an offline
test helper, not production readiness evidence. Before deploying
the new TEST function, use only synthetic TEST data and perform this reviewed
reconciliation:

1. Export an ID-only inventory grouped by the already-normalized `applications.phone`.
   Include application ID, participant ID, number, and submitted time; do not put
   contact values in logs or tickets.
2. For each phone with one row, insert that row into `application_phone_keys`.
   Initialize missing operational values on that Application to empty values,
   status `Новая заявка`, next action `Рассмотреть`, and duplicate count `0`.
3. For each duplicate group, select the earliest `submitted_at`; break an exact
   timestamp tie with the lowest positive `application_number`, then
   `application_id`. This is the preserved original. Do not merge profile, email,
   photo, or answers from later rows into it.
4. Insert only the preserved original into `application_phone_keys`. For every
   later synthetic row, add one audit duplicate event linked to the original and
   recompute its duplicate summary from stable reconciliation evidence plus
   existing runtime hard-duplicate events. The Admin list joins through this key table,
   so those later rows cease to be canonical visible CRM records while remaining
   preserved in storage. Keep a reviewed ID mapping until acceptance is complete.
5. Later synthetic Application/consent/photo rows must not be deleted by an
   automated migration. Their final quarantine/deletion is a separate, explicitly
   approved TEST cleanup after the ID mapping and counts are verified.
6. For every canonical Application whose number is NULL or zero, allocate a
   number in deterministic canonical Application-ID order. Start above both
   the current `application_counters` value and every already-positive
   Application number; preserve all existing positive numbers. Later retained
   duplicate Applications are never assigned a number. Verify that each
   normalized phone has exactly one phone-key row, each key points to an
   existing Application/Participant pair, all visible applications have
   positive unique numbers, and the counter is at least every allocated number.
Register migration 008 only after DDL and this verification succeed.

Recovery contract: preflight the additive objects before applying DDL; treat
the schema phase and reconciliation phase separately.  The reconciliation
job is resumable and repeat-safe (deterministic canonical selection plus
UPSERTs and stable event identities).  Set the final ledger entry only after
verification reports `ready_for_deployment`; deployment is blocked while that
state is false.  A failed backfill is resumed, never by blindly rerunning the
DDL file.

The Python suite is intentionally consolidated for CRM V2: the former
participant-oriented Admin tests were replaced by application-scoped CRM
tests, while duplicate, workflow, and authorization coverage was retained.
This accounts for the baseline 121 methods versus the current 120; it is an
intentional rename/consolidation, not a skipped test.

Because current TEST data may contain synthetic duplicate Application rows, the
new function must not be deployed between the DDL and the reviewed key backfill.
Application startup, builders and tests do not apply or register migrations.
Only the explicitly invoked operator runner with `--allow-write --writers-paused`
can apply missing DDL, backfill or register 008; phases never chain automatically.

## STEP 7B OIDC/JWT client foundation (not deployed)

The Admin SPA has an in-memory OIDC Authorization Code + PKCE client in
`assets/js/admin-auth.js`. It accepts only the TEST `auth` section of
`window.__V5_ADMIN_CONFIG__` injected by the protected host. Required
configuration is `environment: "TEST"`,
`issuer`, `openid_configuration_url`, `client_id`, `redirect_uri`, and the exact
supported scopes `openid email profile` (`groups` is not requested). Direct endpoint values may
also be injected as `authorization_endpoint` and `token_endpoint`. No client
secret, token, or production configuration belongs in the repository.

The OIDC ID token is held in memory as the Gateway bearer token; the OAuth
access token is not stored or sent to the Admin API. The transient PKCE
verifier/state is held in `sessionStorage` solely across the authorization
redirect; no `localStorage` is used. The Admin API client sends
`Authorization: Bearer <id_token>`, never cookie credentials. On 401 it signs
out locally and does not retry PATCH; on 403 it shows access denied.

For `/admin/*`, `handler.py` delegates to `authorizer.py`, which reads only
`requestContext.authorizer.jwt.claims.sub`. Missing context or `sub` fails
closed. Scopes do not grant access in this single-operator TEST stage; Identity
Hub application membership plus Gateway issuer/audience/subject validation is
the access boundary. Client headers, cookies, query parameters, and body fields
are ignored as identity or access sources. The raw `sub` is hashed by the
existing Admin layer before audit storage.

## STEP 8A lifecycle foundation (internal only)

`backend/v5/schema/002_v5_test_lifecycle.sql` is a non-breaking TEST migration. It adds nullable lifecycle fields to `participants`: `processing_blocked`, `processing_blocked_at`, `processing_block_reason`, and `processing_block_request_id`. It is deliberately not applied by CI, the builder, or runtime startup.

After reviewed TEST schema application, `YdbRepository.block_processing()` uses a serializable read/write transaction to set the block and add the minimal `processing_blocked` audit action. A repeated block is idempotent. Intake reads the same block within its transaction and returns `processing_blocked` without writing a participant, application, consent or creation audit event.

`find_participant`, `find_participant_by_phone`, and `find_application` are internal repository helpers only; there are no lifecycle HTTP routes. `destruction_plan()` is dry-run only: it returns IDs/counts (not contact values) and explicit classification for each record category: `contains_personal_data`, `contains_direct_contact_data`, `contains_linkable_identifiers`, and `retention_decision_required`. Consents, technical logs and audit logs are personal data through linkable identifiers even though they contain no direct contacts; technical-log classification applies to records linked by application/request identifiers. It never executes DELETE. Lifecycle audit action names are `processing_blocked`, `destruction_requested`, and `destruction_planned`; no client input or free-text PII is copied into these actions.

## Wave 1 Phase B participant foundation (not migrated or deployed)

The normalized Russian phone produced by `domain.phone()` is the only intake
identity-resolution key. Resolution and optional Participant creation occur inside
the same serializable YDB transaction as the immutable Application insert. A phone
key found without its Participant fails with `phone_key_inconsistent`; it is never
silently reassigned. A repeat Application links to the existing Participant without
updating any canonical profile or operational field.

Participant status, Application lifecycle and Application decision use separate
domain vocabularies in `participant_model.py`. Migration 005 adds separate nullable
columns without changing the legacy fields. Existing Participant rows require an
explicit reviewed bootstrap classification; runtime intake does not infer or
backfill their canonical status.

Migration 004 creates `schema_migrations(environment, migration_id, applied_at)`.
Stable IDs are declared in `migration_ledger.py`. For a future controlled TEST
bootstrap: first verify migrations 001 and 002 against the actual schema; apply
pending 003; apply 004; register verified/applied IDs 001–004; then apply 005 and
register it. Registration happens only after every statement in that migration
succeeds. Do not treat column presence alone as ledger evidence. None of these
steps is performed by application startup, CI, or this repository change.

## Wave 2 Phase B photo submission (code only; not deployed)

FORM 2.2 requires one protected photo reference. Migration 006 only prepares
additive `photo_object_id`, `current_photo_object_id`, `photo_required_blocked`, and
`photo_objects` metadata. It stores no binary, original filename, public URL, or
presigned URL.

FakeRepository models ownership with a SHA-256 hash of the upload/idempotency
context, an immutable Application reference, and a separate Participant current
reference. This is a domain test double, not proof of cloud isolation. For
submission, the runtime YDB adapter reads idempotency, phone/Participant state,
candidate Participant collision state, and the exact owned `READY` photo inside
one serializable read/write transaction. That transaction creates the Participant
when needed, inserts the immutable Application and consent evidence, transitions
the photo directly from `READY` to `ATTACHED`, and initializes a missing current
Participant photo in one commit. A repeat Application never replaces an existing
current Participant photo, and an idempotent replay does not require the already
attached photo to become `READY` again.

Phase B must use JPEG/PNG/WebP detected from decoded content, a 10 MiB input limit,
and local decode plus fresh re-encode so GPS, device model, timestamps, and other
unnecessary EXIF are absent from the persistent object. No face detection,
recognition, matching, scoring, biometric processing, or external image service is
permitted. Admin access should use the authenticated backend proxy. Real PROD photo
collection remains disabled by `PROD_PHOTO_RKN_GATE_PENDING`.

The Pillow codec rejects animated/multi-frame images and applies a decompression
safety ceiling of 40 megapixels and 12,000 pixels on either edge. It fully
decodes, applies EXIF orientation, copies pixels into a fresh image, and encodes
JPEG, PNG, or WebP without source metadata. Invalid or oversized objects are
deleted when possible and never become `READY`.
