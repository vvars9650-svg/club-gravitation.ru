# Yandex Cloud backend baseline

Зафиксировано: 2026-09-05

Источник: активная Cloud Function `gravitation-v3-api` в Yandex Cloud.

## Runtime

- Python 3.14
- Entrypoint: `index.handler`
- Memory: 128 MB
- Timeout: 10 s
- Service account: `gravitation-v3-api`

## Environment

- `YDB_DATABASE`
- `YDB_ENDPOINT`

## Lockbox bindings

- `YANDEX_DISK_ACCESS_TOKEN`
- `YANDEX_DISK_REFRESH_TOKEN`
- `YANDEX_OAUTH_CLIENT_ID`
- `YANDEX_OAUTH_CLIENT_SECRET`

## API Gateway

- Gateway: `gravitation-v3-api`
- Route: `POST /applications`
- Origin: `https://club-gravitation.ru`
- Integration: Cloud Function `gravitation-v3-api`

## YDB tables used by the current function

- `participants`
- `applications`
- `consents`
- `files`
- `audit_log`

The repository copy in `backend/src/index.py` is the preserved baseline before production hardening and frontend migration.
