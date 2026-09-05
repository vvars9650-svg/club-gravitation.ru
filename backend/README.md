# GRAVITATION V3 backend

Рабочий backend проекта «ГРАВИТАЦИЯ» для Yandex Cloud.

## Целевая цепочка

`club-gravitation.ru -> API Gateway -> Cloud Function -> YDB Serverless -> Yandex Disk`

GitHub является источником истины по backend-коду.

## Файлы

- `backend/src/index.py` — точный baseline Cloud Function до V3-рефакторинга;
- `backend/src/index_v3.py` — общий V3 core/helper layer;
- `backend/src/index_v3_release.py` — актуальный release candidate и entrypoint module;
- `backend/tests/` — unit tests;
- `backend/API_CONTRACT.md` — API-контракт `POST /applications`;
- `backend/BASELINE.md` — исходное состояние Yandex Cloud backend;
- `backend/migrations/000_preflight.sql` — проверка исходных данных;
- `backend/migrations/001_indexes.sql` — создание `participant_phone_keys`;
- `backend/migrations/002_backfill_phone_registry.sql` — backfill телефонов;
- `backend/migrations/003_verify_phone_registry.sql` — контроль backfill;
- `backend/DEPLOY_YANDEX.md` — controlled deploy и rollback.

## Что реализовано

- canonical JSON API contract;
- backward-compatible aliases для текущих V2 field names;
- server-side validation;
- phone/email/Telegram normalization;
- обязательный `Idempotency-Key`;
- deterministic Application/Consent/File/Audit IDs;
- idempotent replay without duplicate records;
- конфликт при повторном idempotency key с другим payload;
- phone-authoritative participant resolution;
- database-level phone uniqueness через `participant_phone_keys(phone PRIMARY KEY)`;
- защита от конфликтов email/Telegram;
- сохранение lifecycle-полей Participant при повторной заявке;
- application-scoped photo path на основе application ID + request fingerprint;
- Yandex Disk access-token refresh через Lockbox OAuth credentials;
- honeypot rejection;
- structured logging с `request_id`;
- machine-readable HTTP error codes;
- unit tests и GitHub Actions CI.

## YDB migration status

Миграция реестра телефона завершена и проверена вручную в YDB:

1. preflight показал 0 дублей непустого телефона;
2. `participant_phone_keys` создана;
3. существующие телефоны перенесены;
4. обе verification-проверки вернули пустой результат.

Участники без телефона в registry не входят. Новая web-заявка без телефона backend не принимает.

## Почему используется `participant_phone_keys`

YDB фактически отклонил попытку добавить UNIQUE secondary index к существующей `participants`: `Adding a unique index to an existing table is disabled`.

Поэтому production V3 использует отдельную таблицу:

`participant_phone_keys(phone PRIMARY KEY -> participant_id)`

Primary Key не позволяет двум параллельным first-submit операциям закрепить один телефон за разными участниками.

## Release artifact

Каждый успешный `V3 Backend CI` в ветке `v3` собирает готовый ZIP для Yandex Cloud и публикует его как GitHub Actions artifact:

`gravitation-v3-backend-<commit-sha>`

ZIP содержит:

- `index_v3.py`;
- `index_v3_release.py`;
- `requirements.txt`.

Entrypoint для Cloud Function: `index_v3_release.handler`.

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

GitHub-side release candidate и YDB migration готовы. Следующее действие выполняется в Yandex Cloud: создать новую версию существующей `gravitation-v3-api` из последнего успешного ZIP artifact с entrypoint `index_v3_release.handler`, сохранив текущие env vars, Lockbox bindings и service account.
