# Сохранение исходников визитки Лары — 29.10.2026

## Result

Восстановлен необходимый набор оригинальных исходников принятой пятислайдовой
визитки; реконструкция и изменения дизайна не выполнялись. Приёмка Владом и Ларой
подтверждена текущей задачей. Собранный автономный HTML совпадает побайтово с TEST.
Исходники постоянно сохранены в отдельной GitHub-ветке. Независимое повторное
получение ветки и сборка из удалённого commit успешно выполнены.

## Where

- Репозиторий: https://github.com/vvars9650-svg/club-gravitation.ru
- Ветка сохранения: `codex/lara-card-persistence-20261029`.
- Исходный baseline: `08fc6d6dcaa61c1df15d5b76973bce22bdc20bad`.
- Исходники: `prototypes/lara-card/`.
- Проверенный исходный remote commit: `f402d98a2674d440404d92943b4e3418c141fd7e`.
- Его дерево: `a5191bb6783d194e5017cd71c3477fede6542c3b`, совпадает с локально проверенным commit.
- Этот отчёт уточняется последующим документационным commit; текущий HEAD сверять через remote ref.
- TEST: https://test.club-gravitation.ru/card/lara/
- Current: `lara-typography-20261029-v3-test`.
- Previous: `lara-palette-20261029-v2-test`.
- Артефакт: `card/lara/index.html`, 1798924 байта.
- SHA-256: `7c2bf4f3d37b1608e50a6207fd54f7635475a94937f44ff99bc70909f29cd325`.
- Пакет: `9065a8e77c06598a0133daeea567aae52699c71ef8ef8b9d564f50e5757c315a`.

Политика прочитана через Google Drive:
https://docs.google.com/document/d/1wzqOeA2GYO6H9369LF-DLqsuCtnJuM92ENzW1u0XrnM/edit

Обновлённые AGENTS и skills прочитаны из `docs/codex-persistence-20261029`.
Их ветка не объединяется с веткой визитки. Разрешение commit/push явно дано
текущей задачей; main/v5, TEST и PROD остаются вне изменений.

## Verified

- Фактически найдена изолированная рабочая копия `.worktrees/lara-card-20261028`;
  исходники до начала задачи были untracked на `codex/lara-card-first-screen-20261028`.
- Сборка Node.js 24.22.1 без npm-пакетов: PASS.
- Повторная упаковка из HTML/CSS/JS/фото/шрифта дала исходные SHA-256 HTML и пакета.
- HTTPS 200, точная контрольная сумма загруженного HTML: PASS.
- Существующий SSH alias `selectel-gravitation`: TEST manager status и чтение
  server-файла подтверждают release, размер и SHA-256: PASS.
- TEST config остаётся `PUBLIC_BLOCKED`, `prod_api_url` пустой: PASS.
- Исходные файлы дизайна и медиа закреплены точными SHA-256 в accepted-manifest.json.
- Отдельные gitattributes исключают изменение байтов при checkout на другой ОС.
- Закреплённые Python-зависимости QR установлены в отдельную локальную папку;
  генератор повторно запущен: декодирование 820/240/180 px PASS.
- Набор из 20 сохраняемых файлов проверен по содержимому и шаблонам секретов;
  ключи/токены не обнаружены. Точные имена файлов видны в GitHub commit.
- В набор входят только публичные фото/имя Лары, утверждённый контент, шрифты OFL,
  код, инструкции и публичные QR. Приватные данные участников не включены.

Повторная проверка сборки после checkout:

    node prototypes/lara-card/verify-build.mjs

Дополнительная независимая сверка TEST только на чтение:

    node prototypes/lara-card/verify-build.mjs --live

### Удалённый readback и воспроизводимость

- Независимый git ls-remote подтвердил ветку и remote SHA.
- Новый sparse clone скачан с GitHub в отдельную папку, без копирования исходников.
- Все 20 файлов из сохранённого набора присутствуют в удалённом дереве.
- `verify-build.mjs --live` из нового clone: source checks, build, HTTPS, SSH,
  PUBLIC_BLOCKED — PASS. HTML и JSON-пакет имеют исходные SHA-256.
- git diff --check и git status нового clone: PASS, tracked-изменений нет.
- TEST current/previous остались прежними; deploy/rollback не вызывались.
- CI не заявляется: эта задача проверена независимой сборкой и readback.

### Сохранённые файлы

- `docs/LARA-PERSISTENCE-20261029.md`
- `prototypes/lara-card/.gitattributes`
- `prototypes/lara-card/README.md`
- `prototypes/lara-card/accepted-manifest.json`
- `prototypes/lara-card/assets/OFL-CormorantGaramond.txt`
- `prototypes/lara-card/assets/OFL-Inter.txt`
- `prototypes/lara-card/assets/cormorant-garamond.ttf`
- `prototypes/lara-card/assets/inter.ttf`
- `prototypes/lara-card/assets/lara-approved.jpg`
- `prototypes/lara-card/build.mjs`
- `prototypes/lara-card/create-qr.py`
- `prototypes/lara-card/exports/lara-card-qr-TEST-verification.json`
- `prototypes/lara-card/exports/lara-card-qr-TEST.png`
- `prototypes/lara-card/exports/lara-card-qr-TEST.svg`
- `prototypes/lara-card/index.html`
- `prototypes/lara-card/prepare-test-release.mjs`
- `prototypes/lara-card/requirements-qr.txt`
- `prototypes/lara-card/script.js`
- `prototypes/lara-card/style.css`
- `prototypes/lara-card/verify-build.mjs`

## Current blocker

Нет. Источники находятся в GitHub и воспроизводимы без исходного компьютера.
Обычный HTTPS git push на этом ПК требовал интерактивную авторизацию; тот же
проверенный набор байтов сохранён через уже подключённый GitHub. Настройки
доступа не менялись. Локальный commit `83cedcedbb3e3c907f368024f82f888bc400d92e`
и исходный remote commit отличаются метаданными автора; дерево файлов совпадает.

## Next task

После подтверждённого remote readback эта задача хранения закрыта. Любая новая
версия дизайна или PROD-публикация — отдельная задача. QR пока ведёт на TEST.

## Guardrails

- В этой задаче нет deploy/rollback, изменений серверов, merge, ключей или DNS.
- Сохранены только минимально необходимые исходники и воспроизводимые инструменты.
  Исторические альтернативы, логи, серверные установщики и временные deploy-пакеты
  остались локально; они не требуются для сборки принятой визитки.
- Основная рабочая копия содержит 14 ранее изменённых tracked файлов и четыре
  посторонних untracked документа. Они не включены и не изменены.
- Существующий worktree не удаляется. Локальные исторические материалы сохраняются.
