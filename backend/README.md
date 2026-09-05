# GRAVITATION V3 backend

Рабочий backend проекта «ГРАВИТАЦИЯ» для Yandex Cloud.

## Назначение

Целевая цепочка:

`club-gravitation.ru -> API Gateway -> Cloud Function -> YDB Serverless -> Yandex Disk`

## Источник истины

GitHub является источником истины по backend-коду.

Текущая версия Cloud Function в Yandex Cloud должна быть скопирована в `backend/src/index.py` без функциональных изменений и зафиксирована отдельным baseline-коммитом до начала рефакторинга.

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
- Сначала фиксируется точный baseline текущей функции, затем выполняются изменения.
- Production frontend V2 не переключается на Yandex API до завершения backend QA.
