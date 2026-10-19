# LEGAL SBP 1.3 + 1.1: TEST policy and release

19.10.2026. Влад явно разрешил добавление только `terms/index.html` и `offer/index.html` в установленную TEST allowlist. Применено в существующем root-сеансе; обычный `gravdeploy` не получил новых sudo-команд или иных прав. SSH, ключи, пользователи, sudoers, Nginx, backend, PROD и TEST Admin не менялись.

## Постоянный порядок следующих публикаций

Использовать существующий `ssh selectel-gravitation` и `/usr/local/sbin/gravitation-test-release status/deploy/rollback`. Повторные изменения этих двух HTML выполняются обычным TEST delta deploy, без root-консоли. Перед каждым deploy брать фактический current; не считать записанный ниже release постоянным baseline.

Frozen legal TXT, FORM-2.3, PPD/CONSENT-PD, `/apply/`, все JS/config и Admin остаются защищены. Новые пути и прочее расширение policy требуют отдельного разрешения владельца. Не обходить allowlist, не переустанавливать manager, не менять sudoers и не восстанавливать исправный SSH из-за policy rejection. Не использовать PROD deployment script для TEST.

## Применённое изменение

- Установленный manager не менялся: SHA-256 `4686bf1b4f9d863d602c040cafb13e7f0378985ea11e3c2bf5907f9eeb8f3d79`.
- Изменён только список `allowed` в `/var/lib/gravitation-test-deploy/policy.json`: добавлены ровно два пути. `baseline`, manifests и файлы release при этом не менялись.
- Backup прежней policy: `/var/lib/gravitation-test-deploy/legal-sbp-20261019-policy.before.json`.
- Проверенный owner-script: SHA-256 `c3b7403b285d2b3671717605ee55060ea30b9fb204077183181ec1e87caa8f5f`. Root-owned копия: `/root/legal-sbp-6aff849-c3b7403b.py`.
- Использовалась штатная блокировка manager; проверены current/previous, сохранён backup, затем проверена policy и неизменность manifests. Linux self-tests: PASS. Script и артефакты приёмки сохранены в локальной evidence-папке; повторно применять изменение не требуется.

## Опубликованный TEST

- Content commit: `6aff849bc85e0ee37f71dc49b5105ab251a08079`.
- Release: `legal-sbp-20261019-6aff849-test`.
- Previous / непосредственный rollback: `event01-founders-20261019-876058e-test`.
- Изменены только `terms/index.html` и `offer/index.html`. Остальные 62 файла совпали с прежним TEST.
- PUBLIC_BLOCKED и пустой PROD endpoint сохранены. PROD/Admin targets и полные manifests совпали с baseline.
- Предыдущие frozen редакции TERMS-1.2 и OFFER-1.0 сохранены. Новые тексты встроены в HTML; в публичной шапке нет служебной версии/статуса/даты подготовки.
- Google Docs прочитаны без изменения; разрешены только удаление служебных строк и HTML-форматирование. Полный текст сверяется с source snapshots/revision IDs в evidence.

TEST rollback выполняется обычным manager. Если когда-либо понадобится отменить также расширение policy, сначала вернуть release с прежними юридическими HTML и проверить его, затем отдельно согласовать восстановление policy владельцем. Восстановление старой policy при новом активном legal release нарушит проверку защищённых файлов.

## Evidence и приёмка

Локально в основной копии: `.release-evidence-legal-sbp-20261019/` — source JSON/text, source mapping, точное сравнение HTML/DOM, package и SHA-256, before/deployed manifests, policy self-tests и console proof, local/live responsive QA и screenshots, HANDOFF.

Техническая готовность TEST не является визуальной или юридической приёмкой. Для PROD нужны подтверждения Влада и Лары, юридическая проверка направления 06 и отдельное разрешение Влада. PROD deploy и merge в этой задаче не выполняются.
