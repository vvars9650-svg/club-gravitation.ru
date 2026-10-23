# ABOUT COLLAGE — HANDOFF для TEST, 23.10.2026

## Result

**CODE READY / TEST DEPLOY BLOCKED.** Локальный visual QA пройден с ограничением Google Fonts. На Selectel ничего не опубликовано; финальная приёмка Влада на TEST ещё не выполнена.

- Убраны встроенные в PNG номера `1/8…8/8` небольшим пропорциональным CSS-кадрированием. PNG не изменены и не перегенерированы.
- Нижний коллаж ABOUT: восемь одинаковых карточек 9:10, четыре колонки desktop / две до 760 px, одинаковые промежутки и внешние поля 4 px. Порядок фотографий сохранён.
- По дополнительному поручению Влада шапки показывают «КЛУБ ЖИВЫХ ВСТРЕЧ» без города; в подвале — только «Краснодар» существующим мелким шрифтом. Город внутри мероприятия сохранён. Юридические тексты и FORM не редактировались.

## Where

- Repo: `vvars9650-svg/club-gravitation.ru`.
- Cloud worktree: `/workspace/club-gravitation.ru`.
- Branch: `codex/about-collage-test-20261023`.
- Code commit: `fe41bfac28ec8af4ad60155376f6fbb3d4a6e27d`.
- Baseline: `4ca9034aaff5d7548910bb6c6ca5edd824194009`, удалённая `codex/legal-sbp-test-20261019`. Проверены GitHub branches API и успешный `git ls-remote`/`fetch` всех веток. Baseline включает `6aff849bc85e0ee37f71dc49b5105ab251a08079`; следующий commit добавляет только документацию. ABOUT наследует принятые `06a75f6` и `af7efa5`. `main` остаётся на `6cf41a7` и не использован как база.
- Изменены: `about/index.html`, `assets/css/story.css` (только новые scoped-правила коллажа), `assets/js/site.js`, `index.html`, `events/index.html`, `first-contact/index.html`, `founders/index.html`. Дополнительно этот HANDOFF и QA evidence.
- [Скриншоты до/после и результаты](qa/about-collage-20261023/README.md).
- Push/точный итоговый HEAD проверить через `git ls-remote origin refs/heads/codex/about-collage-test-20261023`; итог также указан в сообщении исполнителя. PR/merge/deploy не выполнялись.

## Verified

- `node scripts/build-public.js` — PASS; `PUBLIC_BLOCKED`, PROD endpoint пустой, legal FORM/PPD/CONSENT 2.3 сохранены.
- `node tests/public-artifact-safety.test.js` — PASS, 64 файла.
- `node tests/public-release-safety.test.js` — PASS.
- `node tests/frontend-submit.test.js` — PASS.
- `node tests/legal-activation.test.js` — PASS.
- `node --check assets/js/site.js` — PASS.
- `git -c core.whitespace=cr-at-eol diff --check` — PASS, исходные CRLF сохранены.
- Chromium/Playwright: 1440×900 DPR1 и DPR2; 1920×1080 DPR1; 768×1024 DPR2; 390×844 DPR3; 360×800 DPR3. Равенство размеров всех восьми карточек, симметрия полей, отсутствие горизонтального overflow, равенство масштабов изображения по X/Y — PASS. Все выбранные изображения загрузились и декодировались.
- Соседние main-блоки ABOUT имеют точно ту же DOM-разметку, что baseline (без учёта диагностического `loading`). Содержательная нумерация глав и принципов сохранена.
- Branding/footer smoke — PASS на `/`, `/about/`, `/events/`, `/first-contact/`, `/founders/`, `/apply/`, `/privacy/`, `/consent-pd/`, `/offer/`, `/terms/`. У страниц без брендовой шапки проверен подвал.
- Ошибок JavaScript нет. Google Fonts недоступен через Cloud proxy (`ERR_TUNNEL_CONNECTION_FAILED`), поэтому console содержит ошибку загрузки шрифта и screenshots используют fallback. В desktop логах также есть отменённые запросы невыбранного mobile picture source; итоговые изображения декодированы. Полный clean-network/Manrope QA нужен на TEST.
- `git diff --exit-code 4ca9034 -- assets/images apply privacy consent-pd offer terms backend api .github` — PASS: защищённые исходники и все изображения неизменны. Новые CSS-правила ограничены `.page-about .about-collage`.

## Current blocker

В Cloud отсутствуют SSH config/профиль Selectel, настроенные credentials и TCP/VPN grants. Read-only HTTPS к TEST и PROD отвергнут proxy: `CONNECT tunnel failed, response 403`. Новые ключи, профили, права и обходы не создавались.

Фактические active TEST/PROD release ID, manifests и rollback target **не проверены**. Последние ID из задания — `legal-sbp-20261019-6aff849-test` и `20261020-combined-4html-6aff849-prod` — только исторические ориентиры, не подтверждённое текущее состояние.

Дополнительный blocker полного branding deploy: `assets/js/site.js` защищён текущей TEST allowlist. Без отдельного решения о разрешённой публикации этого пути новая шапка на всех страницах не может быть доставлена штатным manager. Не расширять policy/sudoers автоматически и не маскировать замену JS под HTML/CSS.

## Next task

1. В среде с уже настроенным `selectel-gravitation` прочитать [SSH runbook](SELECTEL-SSH-CLI.md) и [TEST procedure](SELECTEL-TEST-DEPLOY.md). Взять свежий `status`, фактические manifest/current/previous; проверить активные TEST/PROD и сохранность Admin read-only. Зафиксировать actual current как rollback target будущего TEST deploy.
2. Сопоставить фактические файлы TEST с baseline, не перезаписывать более новые серверные изменения. Для отдельной приёмки **только коллажа** штатно разрешены `about/index.html` и `assets/css/story.css`; старый TEST JS продолжит добавлять город в шапку, это не будет полной приёмкой branding.
3. Для полной публикации всех семи файлов сначала получить отдельное решение по защищённому `assets/js/site.js`. Запрет allowlist не обходить; установку TEST manager не повторять.
4. Использовать существующий delta packager; его исходник отсутствует в этой контентной ветке, pinned source — `15a388f9dd8f6b544489ad619bde8762290d8e9d:scripts/package-test-release.py`. Не merge инфраструктурную ветку целиком. Пакет строить с actual TEST ID и явным разрешённым списком, не из полного public-dist. Сохранить текущий TEST config/JS, кроме отдельно разрешённого пути, и все protected manifests.
5. После штатного deploy — hashes, `PUBLIC_BLOCKED`, пустой PROD endpoint, FORM-2.3, HTTPS/console/visual smoke на 1440/1920/768/390/360, отсутствие номеров и симметрия. При существенном сбое — только предусмотренный TEST rollback. Передать Владу URL `/about/` и новый фактический release ID.
6. Только после успешной публикации и live QA поставить `ABOUT COLLAGE / TEST READY FOR VLAD VISUAL ACCEPTANCE`. Затем остановиться, без PROD.

## Guardrails

PROD, main/v5, backend/API/YDB, Admin и legal/form source не менялись. Исходный Cloud checkout был чистым; домашние незакоммиченные ABOUT/прочие worktree недоступны, не восстанавливались и не перезаписывались. Cloud build — локальная проверка, не источник для замены действующего PROD artifact. Не переносить TEST config в PROD. Управляющий Google Drive обновляет технический управляющий чат после приёмки HANDOFF.
