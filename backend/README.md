# GRAVITATION V3 backend

Рабочий backend проекта «ГРАВИТАЦИЯ» для Yandex Cloud.

## Целевая цепочка

`club-gravitation.ru -> API Gateway -> Cloud Function -> YDB Serverless -> Yandex Disk`

GitHub является источником истины по backend-коду.

## Файлы

- `backend/src/index.py` — точный baseline Cloud Function, скопированный из Yandex Cloud до V3-рефакторинга.
- `backend/src/index_v3.py` — предыдущий V3 prototype/release candidate, сохранён для истории разработки.
- `backend/src/index_v3_release.py` — актуальный release candidate после обнаружения ограничения YDB на добавление UNIQUE secondary index к существующей таблице.
- `backend/tests/` — unit tests.
- `backend/API_CONTRACT.md` — API-контракт `POST /applications`.
- `backend/BASELINE.md` — исходное состояние Yandex Cloud backend.
- `backend/migrations/000_preflight.sql` — проверка данных перед миграцией.
- `backend/migrations/001_indexes.sql` — создание таблицы `participant_phone_keys`.
- `backend/migrations/002_backfill_phone_registry.sql` — backfill существующих телефонов.
- `backend/migrations/003_verify_phone_registry.sql` — проверка результата backfill.
- `backend/DEPLOY_YANDEX.md` — controlled deploy и rollback.

## Что реализовано в актуальном release candidate

- canonical JSON API contract;
- backward-compatible aliases для текущих V2 field names;
- server-side validation;
- phone/email/Telegram normalization;
- обязательный `Idempotency-Key`;
- deterministic Application/Consent/File/Audit IDs;
- idempotent replay without duplicate records;
- detection of same idempotency key with changed payload;
- phone-authoritative participant resolution;
- database-level phone uniqueness through `participant_phone_keys(phone PRIMARY KEY)`;
- protection from ambiguous email/Telegram matches;
- preservation of existing CRM lifecycle fields on repeat application;
- application-scoped immutable photo path based on application ID + request fingerprint;
- Yandex Disk access-token refresh through Lockbox OAuth credentials;
- honeypot rejection;
- structured technical logging with `request_id`;
- HTTP error codes and machine-readable error codes;
- lazy YDB client initialization for testability;
- unit tests and GitHub Actions CI.

## Почему используется `participant_phone_keys`

YDB вернул фактическое ограничение: `Adding a unique index to an existing table is disabled` при попытке добавить UNIQUE secondary index к существующей `participants`.

Поэтому production V3 не зависит от UNIQUE secondary index. Вместо этого создаётся отдельная таблица:

`participant_phone_keys(phone PRIMARY KEY -> participant_id)`

Телефон обязателен для анкеты. Primary Key физически не позволяет двум параллельным first-submit операциям закрепить один и тот же телефон за разными участниками.

## YDB deployment prerequisite

Перед развёртыванием release candidate:

1. `backend/migrations/000_preflight.sql` должен показать 0 дублей непустого телефона;
2. выполнить `backend/migrations/001_indexes.sql`;
3. выполнить `backend/migrations/002_backfill_phone_registry.sql`;
4. выполнить `backend/migrations/003_verify_phone_registry.sql`;
5. обе проверки в шаге 4 должны вернуть пустой результат.

Участники без телефона не включаются в registry. Новая web-заявка без телефона backend не принимает.

## Existing Yandex Cloud resources

Не пересоздавать:

- YDB: `gravitation-v3`;
- Cloud Function: `gravitation-v3-api`;
- API Gateway: `gravitation-v3-api`;
- function service account: `gravitation-v3-api`;
- gateway service account: `gravitation-v3-gateway`;
- Lockbox: `gravitation-v3-disk-oauth`.

## Production rules

- `main` остаётся стабильной V2 до прохождения V3 backend + browser E2E;
- разработка идёт в ветке `v3`;
- токены, OAuth credentials, service-account keys и ПДн не коммитятся;
- backend меняется сначала в GitHub, затем проходит CI, после чего создаётся новая версия существующей Cloud Function;
- production frontend не переключается с Google Apps Script до завершения Yandex backend QA.

## Current stopping point

GitHub-side release candidate подготовлен. Следующее действие выполняется в Yandex Cloud: создать `participant_phone_keys`, сделать backfill и verification, затем создать новую Cloud Function version с entrypoint `index_v3_release.handler`.
