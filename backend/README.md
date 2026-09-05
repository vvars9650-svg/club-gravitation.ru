# GRAVITATION V3 backend

Рабочий backend проекта «ГРАВИТАЦИЯ» для Yandex Cloud.

## Целевая цепочка

`club-gravitation.ru -> API Gateway -> Cloud Function -> YDB Serverless -> Yandex Disk`

GitHub является источником истины по backend-коду.

## Файлы

- `backend/src/index.py` — точный baseline Cloud Function, скопированный из Yandex Cloud до начала V3-рефакторинга.
- `backend/src/index_v3.py` — текущий release candidate V3 backend.
- `backend/tests/test_index_v3.py` — unit tests.
- `backend/API_CONTRACT.md` — API-контракт `POST /applications`.
- `backend/BASELINE.md` — зафиксированное исходное состояние Yandex Cloud backend.
- `backend/migrations/000_preflight.sql` — проверка данных перед индексами.
- `backend/migrations/001_indexes.sql` — необходимые YDB indexes для production V3.
- `backend/DEPLOY_YANDEX.md` — пошаговый controlled deploy и rollback.

## Что уже реализовано в `index_v3.py`

- canonical JSON API contract;
- backward-compatible aliases для текущих V2 field names;
- server-side validation;
- phone/email/Telegram normalization;
- participant deduplication по phone/email/Telegram;
- protection from ambiguous contact matches (`participant_conflict`);
- preservation of existing CRM lifecycle fields on repeat application;
- required `Idempotency-Key`;
- deterministic Application/Consent/File/Audit IDs;
- idempotent replay without duplicate records;
- detection of same idempotency key with changed payload;
- photo fingerprint in `raw_payload`;
- separate photo path per Application;
- Yandex Disk access-token refresh through Lockbox OAuth credentials;
- honeypot rejection;
- structured technical logging with `request_id`;
- HTTP error codes and machine-readable error codes;
- lazy YDB client initialization for testability;
- backend unit tests in GitHub Actions.

## YDB deployment prerequisite

V3 uses explicit secondary indexes for deterministic and efficient participant resolution.

Before deployment:

1. run `backend/migrations/000_preflight.sql`;
2. confirm there are no duplicate non-empty phone values;
3. apply `backend/migrations/001_indexes.sql`;
4. confirm indexes exist.

The phone index is synchronous and unique to prevent two participant records from being created with the same phone during concurrent submissions.

## Current Cloud Function

Existing resource, do not recreate:

- Function: `gravitation-v3-api`
- Runtime: Python 3.14
- Entrypoint: `index.handler`
- Service account: `gravitation-v3-api`
- Environment: `YDB_DATABASE`, `YDB_ENDPOINT`
- Secrets are supplied through Yandex Lockbox.

The current deployed Yandex function still uses the baseline implementation until controlled V3 deployment is performed.

## Production rules

- `main` remains stable V2 until V3 backend and browser E2E are verified.
- Development happens in branch `v3`.
- Tokens, OAuth credentials, service-account keys and participant personal data are never committed.
- Backend code is changed in GitHub first, checked by CI, and only then copied into a new Cloud Function version.
- API Gateway and existing Yandex resources are edited in place when required, never recreated casually.
- Production frontend is switched from Google Apps Script only after Yandex backend tests pass.

## Current stopping point

GitHub-side backend work is prepared and CI is green. The next operation is a controlled YDB migration followed by a new Cloud Function version and API Gateway CORS update. These operations require access to the user's existing Yandex Cloud console and are described in `backend/DEPLOY_YANDEX.md`.
