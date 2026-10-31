# Визитка Лары — кандидат Visual Update 2

Текущие исходники — кандидат от 31.10.2026, ещё не прошедший visual QA и приёмку.
Изменены слайды 1 и 5; TEST и PROD не публиковались. Исторический
`accepted-manifest.json` сохранён без изменений и относится к исходному commit
`9938a78655a5f7688233233384e78448f8c07e88`, а не к новому кандидату.

Проверка и воспроизводимая сборка кандидата из корня репозитория:

    node prototypes/lara-card/verify-candidate.mjs

Скрипт сверяет `candidate-manifest.json`, исходники, слайды 2–4, ссылку телефона,
управление (touch проверяется моделированием pointer-событий), две идентичные
автономные сборки. Результат: `prototypes/lara-card/public-dist/`, автономный HTML:
`public-dist/candidate/card/lara/index.html` внутри папки визитки.

Preview только прототипа на каноническом порту:

    npx --yes serve@14 prototypes/lara-card/public-dist --listen 4176 --no-clipboard

Если npx отсутствует, доступен fallback без зависимостей:

    node prototypes/lara-card/preview.mjs

Адрес: http://localhost:4176/. При сетевом ограничении sandbox сервер нужно
запускать с разрешённым локальным сетевым доступом. Host/port не менять.

Использован точный оригинал `assets/gravitation-logo-horizontal-main.svg`
(33006 байт), без редактирования. Источник Google Drive:
https://drive.google.com/file/d/1NGWlSlelEkFHVYPTTAsH9JGOuZh_ZrRG/view
SHA-256: `0d9beab3b96f50004e1c9f89529c7dad8d5f0ce5ff148c96427a7692a55e7222`.
Логотип с прозрачным фоном и светлой надписью для шоколадного фона.

Фото занимает 35,72% карточки на desktop, 22,4% на мобильных экранах.
На mobile логотип и телефон располагаются друг под другом. Визуальная читаемость,
кадрирование, наложения и размеры 1080/390/360 ещё требуют проверки в браузере.
Действующий QR и эталон принятой версии не изменялись. См. итоговый отчёт:
`../../docs/LARA-VISUAL-UPDATE2-20261031.md`.

## Историческая принятая версия (исходный commit)

Пять слайдов утверждены Владом и Ларой (подтверждение в задаче 29.10.2026).
Дизайн сохранён без изменений. TEST: https://test.club-gravitation.ru/card/lara/
Release: lara-typography-20261029-v3-test; предыдущий: lara-palette-20261029-v2-test.
PROD-публикация не поручалась.

## Сборка на другом компьютере

Нужны Git и Node.js 22+ (проверено на Node.js 24.22.1). Сборка использует только
стандартную библиотеку Node; npm install, Codex, Python, Drive и SSH не нужны.
Из корня репозитория:

    node prototypes/lara-card/verify-build.mjs

Скрипт проверяет SHA-256 исходников, собирает локальное превью в
prototypes/lara-card/public-dist/ и автономную страницу в
public-dist/verified-release/card/lara/index.html внутри папки визитки.
SHA-256 страницы обязан совпасть с accepted-manifest.json:
7c2bf4f3d37b1608e50a6207fd54f7635475a94937f44ff99bc70909f29cd325 (1798924 байта).
Страница содержит фото, шрифт, CSS и JS; для отображения не нужны внешние ресурсы.
Ссылки на клуб и Instagram требуют интернет.

Для превью можно обслужить prototypes/lara-card/public-dist статическим сервером
на порту 4176. Корневой scripts/build-public.js собирает основной сайт и не включает
этот изолированный прототип.

Дополнительная проверка текущего TEST (только чтение) с существующим
SSH-профилем selectel-gravitation и доступом HTTPS:

    node prototypes/lara-card/verify-build.mjs --live

Проверяются HTTPS, TEST manager status, SHA-256 серверного файла и PUBLIC_BLOCKED.
Скрипт не вызывает deploy/rollback и ничего не пишет на сервер.
Если TEST позднее обновлён, нужно сверить новую принятую версию.

prepare-test-release.mjs только формирует локальный пакет, без публикации.
Его исторические defaults не являются актуальным разрешением на deploy.
Воспроизведение принятого пакета:

    node prototypes/lara-card/prepare-test-release.mjs --base lara-palette-20261029-v2-test --release lara-typography-20261029-v3-test --output public-dist/verified-release

## Цветовая легенда

| Слайд | Цвет | HEX |
| --- | --- | --- |
| 1 | Шоколад | #3D2118 |
| 2 | Коралл | #FFB3A5 |
| 3 | Горчица | #D6B65D |
| 4 | Синий | #397FE5 |
| 5 | Шоколад | #3D2118 |

Акцент: #FF8754. Светлый текст: #FFF3E6. Тёмный текст на синем: #160B07.
Внешние поля: #000000. Палитра отражает принятый CSS, изменений дизайна нет.

## Исходники и зависимости

- index.html, style.css, script.js — пять слайдов и навигация.
- assets/lara-approved.jpg — утверждённое публичное фото без изменения байтов.
- assets/cormorant-garamond.ttf, assets/inter.ttf и OFL-*.txt — локальные шрифты с лицензиями. Inter сохранён для исходного CSS; автономная страница использует только Cormorant.
- .gitattributes сохраняет точные байты принятых HTML/CSS/JS и медиа независимо от core.autocrlf.
- accepted-manifest.json — контрольные суммы исходников и принятого артефакта.
- exports/lara-card-qr-TEST.* — PNG/SVG QR на TEST-ссылку и результат декодирования.

Логотип не используется. Исторические варианты, временные пакеты и серверные
установщики не входят в этот набор. Секретов, ключей и конфигураций Admin здесь нет.

ТЗ: https://docs.google.com/document/d/1EUuh7JprhDQ-Wn63z11_Q0AmWL1c9igM/edit
Медиа: https://drive.google.com/drive/folders/18K7kBGpklkbdAk412A808Ne-R3PmC8Sy
Фото Drive ID: 18cJa9yX_tyRDfmlys1qm08fddy9mcYMd.
Шрифты: официальный https://github.com/google/fonts (ofl/cormorantgaramond, ofl/inter),
лицензии OFL рядом с файлами.

## Необязательное создание QR

Готовые PNG и SVG используются без установки Python. Для пересоздания нужны
Python 3.11+ и отдельное окружение:

    python -m venv .test-deps/lara-qr
    # Активируйте окружение стандартным для вашей ОС способом.
    python -m pip install -r prototypes/lara-card/requirements-qr.txt
    python prototypes/lara-card/create-qr.py

Генератор проверяет декодирование на 820/240/180 px. QR ведёт на TEST, не на PROD.
Библиотеки Python не участвуют в сборке страницы.

Проверки сохранения: ../../docs/LARA-PERSISTENCE-20261029.md
