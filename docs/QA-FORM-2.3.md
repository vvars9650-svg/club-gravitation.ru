# Проверки кандидата FORM-2.3 — 14.10.2026

LOCAL / TEST, только синтетические данные. PROD не изменялся.

| Проверка | Результат |
|---|---|
| Public production-format build с PUBLIC_BLOCKED | PASS, 60 файлов |
| 8 JS-наборов: frontend, API, contract, Admin, public/artifact/deploy safety | PASS |
| Python unit/integration/regression, 175 тестов | PASS |
| Backend ZIP allowlist/import/health | PASS |
| Git diff --check | PASS |
| 10 страниц × 5 viewport/DPR | PASS, overflow/видимые изображения/page errors/network HTTP errors |
| Локальный браузер → настоящий handler/codec → synthetic repository/storage | PASS |
| Опубликованный GitHub Pages preview: заполнение, фото, submit, фактические network writes | PASS, 0 записей |
| Cloud TEST: настоящий private photo initiate → PUT → complete → submit | PASS |
| Cloud TEST: повторная подача | PASS, исходная заявка №000018 |
| TEST YDB: consent FORM-2.3, TEST hash, duplicate warning | PASS |
| TEST private photo GET, URL TTL 180 секунд | PASS |
| TEST Admin repository/card и операционный PATCH synthetic-заявки | PASS |
| Анонимный GET фактического TEST `/admin/participants/{id}?include_photo=true` | PASS, отклонён |
| Живой TEST Admin: операторский OIDC login и экран фотографии | PASS после разрешённого TEST activation; №000018, private PNG декодирован, TTL 180 секунд, console/CSP clean |
| PROD_ENABLED build | Намеренно BLOCKED до legal/release gate |

Браузерная матрица: 1440×900 DPR1, 1440×900 DPR2, 390×844 DPR3, 360×800 DPR3, 768×1024 DPR2. Страницы: /, /about/, /events/, /first-contact/, /founders/, /privacy/, /consent-pd/, /offer/, /terms/, /apply/. Скриншоты и JSON отчёты находятся в локальном `test-results` и не включаются в публичный artifact.

Активная TEST Cloud Function version: `d4ev92fcfmgoj0sfr64f`, функция `d4es728msdiuui3d1hcg`, tag `short-form-rc` и default latest. Предыдущая baseline version для TEST rollback: `d4ebquobceqdbjfgj7bc`. Gateway и schema не менялись. Ledger TEST прочитан: 001–008 присутствуют. E2E заявка: `APP-4e006298e63d34b163d6`, участник `PT-4e006298e63d34b163d6`, №000018. Промежуточные synthetic попытки/фото сохранены; автоматического удаления не было.

Cloud QA обнаружил и устранил ошибки YQL: constant predicate в JOIN, неявные aliases canonical application/participant и String bytes; также исправлена обработка всех streamed chunks UNION. FakeRepository раньше не выявлял эти различия. Регрессия включает bytes/chunk duplicate case и сохранение FORM-2.3 в YDB application/consent.

`cloud-release-browser.js` получает frontend-код из локального RC, но исполняет настоящий private TEST flow под TEST frontend origin: это подтверждает контракт и TEST bucket CORS. Сам TEST frontend hosting не перезаписывался. `cloud-admin-verification.py` проверяет backend/Admin repository и SDK-доступ к private фото; он не заменяет OIDC operator UI acceptance.

Для воспроизводимости локальных тестов использованы зависимости из backend/v5/requirements.txt в игнорируемом `.test-deps`; временные файлы — `.test-tmp`. Браузер — bundled Playwright + Edge. Внешние cloud/browser scripts не запускаются автоматически в CI и используют только явно заданный TEST-контур.
