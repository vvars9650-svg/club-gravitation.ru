# Лара — Visual Update 2, 31.10.2026

## RESULT

Реализован и локально проверен кандидат, ожидающий приёмки Владом и Ларой.
Слайд 1: уменьшено оригинальное фото, подняты имя, оранжевая линия и должность;
внизу добавлены оригинальный горизонтальный логотип и `tel:+79154234712`.
На desktop логотип слева, телефон справа; до 600 px — вертикальное размещение.
Площадь прямоугольной области фото: desktop 76% × 47% = 35,72%; mobile
64% × 35% = 22,4%. Фото не ретушировалось. Слайд 5: удалена строка «Давай узнаем
друг друга лучше», заголовок опущен с 12% до 18%; ссылки и навигация сохранены.

## SOURCE

- Точный файл: `prototypes/lara-card/assets/gravitation-logo-horizontal-main.svg`.
- Google Drive: https://drive.google.com/file/d/1NGWlSlelEkFHVYPTTAsH9JGOuZh_ZrRG/view
- Вариант: оригинальный SVG, прозрачный фон, светлые векторные буквы и золотая
  подпись «КЛУБ ЖИВЫХ ВСТРЕЧ». Файл содержит оригинальный растровый знак.
- 33006 байт; SHA-256:
  `0d9beab3b96f50004e1c9f89529c7dad8d5f0ce5ff148c96427a7692a55e7222`.
- Получен через подключённый проектный Google Drive, сохранён без изменения байтов.

## WHERE

- Worktree: `C:/Users/VLAD/Documents/ChatGPT/Сайт Гравитации/.worktrees/lara-visual-update2`.
- Ветка: `codex/lara-visual-update2-20261031`.
- Baseline: `9938a78655a5f7688233233384e78448f8c07e88`.
- GitHub: https://github.com/vvars9650-svg/club-gravitation.ru/tree/codex/lara-visual-update2-20261031
- Новый эталон не утверждён; `accepted-manifest.json` сохранён побайтово.
- SHA-256 автономного кандидата:
  `68e96f451baa76803ce4f1c3a16c23176e5400bf31554836ef8fdda54c1204d0` (1843595 байт).
- Изменены README, index.html, style.css, prepare-test-release.mjs, .gitattributes;
  добавлены SVG, candidate-manifest.json, verify-candidate.mjs, preview.mjs,
  screenshots/измерения в exports/visual-update2 и этот отчёт.

## VERIFIED

- Node.js 24.22.1: сборка preview и автономного HTML — PASS.
- Две последовательные сборки дают одинаковый SHA-256 — PASS.
- `node prototypes/lara-card/verify-candidate.mjs` — PASS: контрольные суммы,
  неизменность HTML слайдов 2–4, tel, все пять экранов через кнопки, точки,
  клавиатуру, моделируемые touch pointer-события и границы навигации.
- script.js, фото, шрифты, лицензии и QR не изменены относительно baseline.
- CSS слайдов 2–4 и общая навигация не изменены (проверка diff).
- `node --check prototypes/lara-card/script.js`, `git diff --check` — PASS.
- HTTP smoke `http://localhost:4176/`: 200, в ответе текущий кандидат.
- Независимый clone GitHub commit `c2f253f80e1464b911471c76512c39921f95acd8`:
  `verify-candidate.mjs` — PASS; дерево совпало с локальным
  `b0b31175afa1be2f99a022a3a4d689528f672eee`. Последующее исправление preview
  сохраняется отдельным commit; актуальный SHA сверять по remote ref.
- Обычный push потребовал интерактивную авторизацию; использован подключённый
  GitHub connector, без изменения доступа и без merge.
- npx отсутствует; локальный preview запущен через Node fallback, порт 4176.

## PREVIEW / LIMITATIONS

Сохранены 8 JPEG: слайды 1 и 5 при 1080×1080, 1440×900, 390×844, 360×800.
Папка: `prototypes/lara-card/exports/visual-update2/`.
`qa-geometry.json` содержит измерения всех пяти слайдов на 1080, 1440,
390, 360 и tablet smoke 768 px. Horizontal overflow и переполнения текста
не обнаружены; фото и логотип загружены. Визуально проверены читаемость,
кадрирование, отсутствие наложений изменённых слайдов. Слайды 2–4 сохранены.
В браузере проверены кнопки вперёд/назад, точки и клавиатура. Console warn/error:
пусто. Локальные зависимости дополнительно проверяются HTTP smoke.

Локальный preview исправлен: `localhost` разрешается в IPv4 и IPv6, исходный
fallback слушал только ::1 (family=4 давал ECONNREFUSED, family=6 — HTTP 200).
Теперь оба loopback listener дают HTTP 200 на прежнем порту 4176. После ручного
обновления CURRENT PAGE браузер показал визитку, visual QA выполнен.
Proxy, firewall, DNS, Google Drive и правила доступа не менялись.

Ограничения: API viewport поддерживает только ширину/высоту, DPR в сессии = 1;
DPR 2/3 не проверены. Touch проверен моделированием pointer-событий;
проверка жестов на физическом телефоне не выполнялась. CI PASS не заявляется.
Статус кандидата не означает визуальную приёмку.

## NEXT

Влад и Лара оценивают скриншоты слайдов 1 и 5 и подтверждают композицию.
При необходимости отдельно проверить HiDPI и физический touch.
Любая TEST/PROD-публикация требует отдельного поручения.

## GUARDRAILS

TEST/PROD, сервер, DNS, SSH-права, основной сайт и действующий QR не изменялись.
Публикация не выполнялась и отдельно не разрешена. Основной грязный worktree и
предыдущий worktree визитки не редактировались. Commit/push разрешены только в
отдельную ветку; merge не выполняется. Правила ветки docs/codex-persistence-20261029
и gravitation-handoff прочитаны без объединения веток.
