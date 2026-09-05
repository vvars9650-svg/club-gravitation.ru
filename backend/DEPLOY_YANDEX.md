# Deploy GRAVITATION V3 backend to Yandex Cloud

This document describes the controlled deployment sequence for the existing Yandex Cloud resources. It does **not** recreate infrastructure.

## Existing resources

- YDB: `gravitation-v3`
- Cloud Function: `gravitation-v3-api`
- API Gateway: `gravitation-v3-api`
- Service account for function: `gravitation-v3-api`
- Service account for gateway: `gravitation-v3-gateway`
- Lockbox: `gravitation-v3-disk-oauth`

## Preconditions

1. GitHub branch is `v3`.
2. `V3 Backend CI` is green.
3. Current production frontend on `main` is not changed.
4. Run `backend/migrations/000_preflight.sql` in YDB.
5. Duplicate-phone query must return zero rows.
6. Apply `backend/migrations/001_indexes.sql`.
7. Confirm indexes exist before deploying the new function code.

## API Gateway change required before browser testing

Current Gateway CORS allows only `Content-Type`.

V3 frontend sends an `Idempotency-Key` request header, so add it to the existing `/applications` CORS block:

```yaml
x-yc-apigateway-cors:
  origin: https://club-gravitation.ru
  methods:
    - POST
  allowedHeaders:
    - Content-Type
    - Idempotency-Key
  exposeHeaders:
    - X-Request-Id
  maxAge: 3600
  optionsSuccessStatus: 204
```

Do not recreate the API Gateway. Edit the existing specification only.

## Cloud Function deployment

The current Yandex Cloud editor expects:

- runtime: Python 3.14
- entrypoint: `index.handler`
- requirements: `ydb`, `requests`

For the first controlled V3 deploy:

1. Keep a copy of the existing active function version available for rollback.
2. In the existing function `gravitation-v3-api`, create a **new version**, do not overwrite history.
3. Copy the contents of `backend/src/index_v3.py` into the Cloud Function file named `index.py`.
4. Copy `backend/requirements.txt` unchanged.
5. Keep service account `gravitation-v3-api`.
6. Keep environment variables:
   - `YDB_DATABASE`
   - `YDB_ENDPOINT`
7. Keep Lockbox bindings:
   - `YANDEX_DISK_ACCESS_TOKEN`
   - `YANDEX_DISK_REFRESH_TOKEN`
   - `YANDEX_OAUTH_CLIENT_ID`
   - `YANDEX_OAUTH_CLIENT_SECRET`
8. Optional configuration may be added later through environment variables:
   - `PD_CONSENT_VERSION`
   - `RULES_VERSION`
   - `CONTACT_CONSENT_VERSION`
   - `YANDEX_DISK_PHOTO_DIR`
9. Do not change production frontend yet.

## First backend test

Test through API Gateway, not by exposing the Cloud Function publicly.

Request requirements:

- method: POST
- route: `/applications`
- `Content-Type: application/json`
- `Idempotency-Key: <unique value with at least 16 chars>`
- synthetic test data only
- valid small JPG/PNG/WEBP in `photo_data`

Expected first request:

- HTTP 201
- `success: true`
- `participant_id`
- `application_id`
- `file_id`
- `idempotent_replay: false`
- `request_id`

Verify manually:

1. exactly one `participants` row;
2. exactly one `applications` row;
3. three `consents` rows;
4. one `files` row;
5. one `audit_log` row;
6. photo exists on Yandex Disk at the stored `file_path`.

## Idempotency test

Send the **identical request with the identical Idempotency-Key** again.

Expected:

- HTTP 200
- same `participant_id`
- same `application_id`
- same `file_id`
- `idempotent_replay: true`
- no additional Application/Consent/File/Audit records.

Then send a changed payload with the **same Idempotency-Key**.

Expected:

- HTTP 409
- `code: idempotency_conflict`
- no new records.

## Participant dedup test

Send a new application with a **new Idempotency-Key** but the same normalized phone.

Expected:

- HTTP 201
- same `participant_id`
- new `application_id`
- `participant_reused: true`
- existing lifecycle fields on `participants` remain intact.

## Rollback

If a V3 test fails:

1. do not switch frontend;
2. point API Gateway back to the previously known-good function version/tag if necessary;
3. keep `main` unchanged;
4. inspect logs by `request_id`;
5. fix code in GitHub `v3` first, then create another Cloud Function version.

## Production switch

Only after all backend tests pass:

1. update V3 frontend client to JSON + CORS + Idempotency-Key;
2. test the full browser path;
3. verify YDB and Yandex Disk;
4. only then merge/release V3 to production.
