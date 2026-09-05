# Deploy GRAVITATION V3 backend to Yandex Cloud

Controlled deployment sequence for the existing Yandex Cloud resources. Infrastructure is not recreated.

## Existing resources

- YDB: `gravitation-v3`
- Cloud Function: `gravitation-v3-api`
- API Gateway: `gravitation-v3-api`
- Function service account: `gravitation-v3-api`
- Gateway service account: `gravitation-v3-gateway`
- Lockbox: `gravitation-v3-disk-oauth`

## YDB migration status

Completed and verified:

1. `backend/migrations/000_preflight.sql` — zero duplicate non-empty phones;
2. `backend/migrations/001_indexes.sql` — `participant_phone_keys` created;
3. `backend/migrations/002_backfill_phone_registry.sql` — existing non-empty phones backfilled;
4. `backend/migrations/003_verify_phone_registry.sql` — both verification queries returned empty results.

Do not attempt to add `GLOBAL UNIQUE` index to the existing `participants` table. YDB rejected this operation with `Adding a unique index to an existing table is disabled`. Phone uniqueness is enforced through `participant_phone_keys.phone PRIMARY KEY`.

## Release artifact

`V3 Backend CI` builds a deployment ZIP on every backend commit in branch `v3`.

The ZIP contains exactly:

- `index_v3.py` — shared V3 core;
- `index_v3_release.py` — active release handler;
- `requirements.txt` — Python dependencies.

The workflow artifact is named `gravitation-v3-backend-<commit-sha>` and is retained for 14 days.

Entrypoint: `index_v3_release.handler`.

## Cloud Function deployment

Keep current resource settings:

- runtime: Python 3.14;
- timeout: 10 seconds initially;
- memory: 128 MB initially;
- service account: `gravitation-v3-api`;
- environment variables: `YDB_DATABASE`, `YDB_ENDPOINT`;
- Lockbox bindings:
  - `YANDEX_DISK_ACCESS_TOKEN`;
  - `YANDEX_DISK_REFRESH_TOKEN`;
  - `YANDEX_OAUTH_CLIENT_ID`;
  - `YANDEX_OAUTH_CLIENT_SECRET`.

Controlled deploy:

1. Keep the currently active function version available for rollback.
2. Open the existing function `gravitation-v3-api` and create a **new version**.
3. Use the **ZIP archive** source option rather than copying large Python files by hand.
4. Upload the ZIP produced by the latest successful `V3 Backend CI` run.
5. Set entrypoint to `index_v3_release.handler`.
6. Preserve the existing service account, YDB environment variables and Lockbox bindings.
7. Do not make the function public.
8. Do not switch production frontend yet.

Optional environment variables, not required for the first controlled test:

- `PD_CONSENT_VERSION`;
- `RULES_VERSION`;
- `CONTACT_CONSENT_VERSION`;
- `YANDEX_DISK_PHOTO_DIR`.

## API Gateway change required before browser testing

Current Gateway CORS allows only `Content-Type`.

V3 frontend sends an `Idempotency-Key` header, so edit the existing `/applications` CORS block before browser E2E:

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

Do not recreate the API Gateway.

## First backend test

Test through the existing API Gateway, not by exposing Cloud Function publicly.

Request requirements:

- POST `/applications`;
- `Content-Type: application/json`;
- `Idempotency-Key: <unique value with at least 16 chars>`;
- synthetic test data only;
- valid small JPG/PNG/WEBP in `photo_data`.

Expected first request:

- HTTP 201;
- `success: true`;
- `participant_id`;
- `application_id`;
- `file_id`;
- `idempotent_replay: false`;
- `request_id`.

Verify:

1. one canonical `participants` row;
2. one `participant_phone_keys` row for the normalized phone;
3. one `applications` row;
4. three `consents` rows;
5. one `files` row;
6. one `audit_log` row;
7. photo exists on Yandex Disk at stored `file_path`.

## Idempotency test

Send the identical request with the identical `Idempotency-Key` again.

Expected:

- HTTP 200;
- same participant/application/file IDs;
- `idempotent_replay: true`;
- no additional Application/Consent/File/Audit rows.

Then send changed payload with the same key.

Expected:

- HTTP 409;
- `code: idempotency_conflict`;
- no new records and no overwrite of the accepted photo.

## Participant dedup test

Send a new application with a new idempotency key but the same normalized phone.

Expected:

- HTTP 201;
- same `participant_id`;
- new `application_id`;
- `participant_reused: true`;
- existing lifecycle fields remain intact.

## Concurrency guard

Two simultaneous first applications with the same phone race on the same `participant_phone_keys.phone` primary key. One transaction becomes the canonical owner. The losing request re-resolves the phone owner and retries its Application against that participant instead of creating a second Participant.

## Rollback

If a V3 test fails:

1. do not switch frontend;
2. restore routing to the previous known-good function version/tag if necessary;
3. keep `main` unchanged;
4. inspect logs by `request_id`;
5. fix GitHub `v3`, rerun CI, then create another function version.

The `participant_phone_keys` table may remain after rollback; baseline V2 backend does not use it.

## Production switch

Only after backend tests pass:

1. update V3 frontend client to JSON + CORS + `Idempotency-Key`;
2. test full browser path;
3. verify YDB and Yandex Disk;
4. only then merge/release V3 to production.
