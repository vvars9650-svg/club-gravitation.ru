# Release candidate FORM-2.3 — 14.10.2026

Среда подготовки: LOCAL / TEST. PROD не изменён. Merge в v5/main не выполняется.

Baseline исходников: `410c39392f5be49d56a87dadd7103bde1d2768e3` (сохранённый origin/v5). Принятый preview: `1257123a9ee5b8e5d8da7427747a86236b50115a`. Указанный в HANDOFF dirty worktree на этом компьютере отсутствует; визуал восстановлен из source preview, настоящий transport — из Git baseline. Исходная рабочая копия v5 `d400052` с тремя изменёнными файлами Admin оставлена отдельно. Их копии сохранены в каталоге артефактов чата. Других активных Codex-задач с этим checkout в доступном списке не обнаружено; сторонние редакторы этим не исключаются.

Изменения: утверждённые главная/about/founders/EVENT01/privacy и CSS; четыре новых изображения коллажей/основателей; одностраничная apply с точным текстом фото, city autocomplete и free contact; защищённый transport initiate/PUT/complete и submit; versioned backend validation, service и YDB evidence; подпись контакта Admin; контрактные, transport, YDB и browser тесты; проекты юридических документов. Четыре WebP hero в preview являются производными тех же hash-verified chunks: сборка воспроизводит их, повторное хранение в Git не требуется. events и остальные frozen/legal страницы совпадают с baseline и сохранены.

Миграция базы для сокращённой формы не нужна: сохраняются столбцы, JSON-снимки, прежние поля и версия 2.2. Старый backend-контракт продолжает работать. При новых заявках старые поля пусты. application_id, participant_id, номера, duplicate protection, защищённая фотография и операторский workflow сохраняются.

`node scripts/build-public.js` по умолчанию строит PUBLIC_BLOCKED. `V5_PUBLIC_MODE=PROD_ENABLED` в кандидате намеренно останавливает сборку до записи артефакта. Существующий Selectel workflow задаёт PROD_ENABLED, поэтому его deploy-step также остановится. Кандидат нельзя случайно опубликовать как работающий новый intake. После юридического утверждения потребуется отдельный малый gate commit с точными версиями/хэшами и проверкой фактического PROD runtime.

Фактический PROD metadata прочитан без изменения: Gateway `d5dsivdtqjog5vgvn111` → Function `d4e8kk0f5bqulombl18j`, active version `d4ej2creip5g0iloi3vh`. Имена runtime-параметров: `V5_ENVIRONMENT`, `V5_PROD_CONSENT_TEXT_HASH`, `V5_PROD_PHOTO_BUCKET`, `V5_PROD_YDB_DATABASE`, `V5_PROD_YDB_ENDPOINT`. Значения секретов/подключения не выводились. API metadata не возвращает исходный пакет или его checksum. Найдены локальные PROD ZIP от 19.09, но их равенство текущей active version не подтверждено; поэтому они не приняты автоматически за источник истины. До PROD требуется связать точный deployed source с Git и применить изменения короткой формы к этому runtime с сохранением PROD isolation.

TEST ZIP кандидата: SHA-256 `a4e24d3967418d28a8e9d9077586bbe0b4fd21014da0638ac23bf353fc07e8ed`. Активная TEST version `d4ev92fcfmgoj0sfr64f` построена из этого ZIP.

## Контролируемый deployment после приёмки

1. Утвердить юридический комплект и сверить RKN-03/реестр; подготовить публикацию версий, links и canonical hash. Сохранить старые frozen/evidence.
2. Получить точный текущий PROD backend source/version и его runtime-конфигурацию. Git baseline Python ориентирован на TEST (`ENVIRONMENT=TEST`, TEST-marked hash); этот ZIP не является PROD-пакетом. Не подменять работающий PROD TEST-артефактом. Проверить адаптацию короткой формы в фактической PROD-сборке и её regression отдельно.
3. Зафиксировать релизный SHA, green CI, frontend SHA-256 и backend ZIP SHA-256; сохранить предыдущую cloud version, API Gateway spec, environment/secrets references, IAM/service account, private bucket CORS, номер схемы/ledger. Не выводить секреты.
4. До открытия UI выпустить совместимый backend, принимающий старую и новую форму, с exact legal evidence. База для этого изменения не мигрируется. Если потребуется другая миграция, оформить отдельный проверенный additive план.
5. После отдельного разрешения Влада и gate commit собрать production frontend и запустить существующий Selectel workflow на точном SHA. Atomic `/srv/gravitation/current` переключает только frontend. Проверить /, /about/, /events/, /first-contact/, /founders/, /apply/ и юридические страницы, HTTPS, изображения, консоль, фото CORS, заявку/evidence и защищённый Admin по утверждённой процедуре. Проверка реальных данных не разрешена этой задачей.
6. При сбое закрыть новый intake и выполнить согласованный rollback. Merge стабильных веток отдельным решением.

## Rollback

- Frontend: существующая операция rollback на сохранённый release ID / `shared/previous-release`; проверить symlink, HTTPS и старую форму. Точное значение live release ID перед deploy прочитать на сервере; исторический ID из Sheet не считать гарантией актуальности.
- Backend: вернуть предыдущую Cloud Function version/tag и прежний Gateway binding, не пересоздавать конфигурацию/секреты. Frontend symlink этого не делает. Сначала закрыть новый UI, затем backend rollback, иначе FORM-2.3 будет обращаться к старому валидатору.
- Данные: не откатывать базу и не удалять новые заявки/consent/photo. Версия 2.3 сохранена в evidence; старое приложение должно читать существующие DTO/JSON. Счётчики не сбрасывать. Миграций сокращённой формы нет.
- TEST: предыдущая версия `d4ebquobceqdbjfgj7bc` функции `d4es728msdiuui3d1hcg`. Синтетические E2E-записи сохранять до отдельного решения о cleanup; не удалять автоматически.

Юридические решения и непроверенные источники: [LEGAL-GATE-FORM-2.3](LEGAL-GATE-FORM-2.3.md).
