# GRAVITATION V3 backend

Рабочий backend проекта «ГРАВИТАЦИЯ» для Yandex Cloud.

## Назначение

Целевая цепочка:

`club-gravitation.ru -> API Gateway -> Cloud Function -> YDB Serverless -> Yandex Disk`

## Источник истины

GitHub является источником истины по backend-коду.

## Файлы

- `backend/src/index.py` — точный baseline текущей Cloud Function из Yandex Cloud, сохранённый без функциональных изменений.
- `backend/src/index_v3.py` — текущая рабочая версия V3 backend. Сейчас в ней реализован первый этап: participant deduplication и безопасное хранение нового фото для повторной заявки.
- `backend/API_CONTRACT.md` — рабочий API-контракт V3.
- `backend/BASELINE.md` — зафиксированное состояние исходной Yandex Cloud Function.

До завершения тестирования `index_v3.py` не считается production-версией и не разворачивается автоматически.

## Текущая Cloud Function

- Function: `gravitation-v3-api`
- Runtime: Python 3.14
- Entrypoint: `index.handler`
- Service account: `gravitation-v3-api`
- Environment: `YDB_DATABASE`, `YDB_ENDPOINT`
- Secrets are supplied through Yandex Lockbox and must never be committed to GitHub.

## Правила

- Не хранить токены, OAuth credentials, service-account keys и персональные данные в репозитории.
- Не менять `main` до завершения и проверки V3.
- Рабочая ветка V3: `v3`.
- Baseline сохраняется в Git-истории и не переписывается задним числом.
- Production frontend V2 не переключается на Yandex API до завершения backend QA.
- Новая backend-логика сначала проходит CI и тестирование, затем переносится в production Cloud Function.
