# Аудит УЧ ч7 и технической памяти — 19.10.2026

Датированный архив доказанных фактов и пробелов. Владелец: технический управляющий чат сайта; приёмка: Влад. Текущие статусы после этой даты читать в [управляющем Sheet](https://docs.google.com/spreadsheets/d/1DnTkvn0GdufxDy6g_6skKs0yJGxUVpjndyrbqwgDFCs/edit). Это не новый MASTER и не разрешение на серверные действия.

## Объём и границы доказательства

- Прочитаны четыре вкладки Sheet: ТЕКУЩЕЕ СОСТОЯНИЕ (1–13), ИСТОЧНИКИ (1–30), ИЗМЕНЕНИЯ (1–157, включая пустые исторические строки), ПЕРЕДАТЬ ДАЛЬШЕ (1–37); MASTER 00/06/07/08 и рабочая карточка EVENT 01.
- `read_thread` для [УЧ ч7](chatgpt-conversation://6acd2e1e-d858-83eb-8dfc-cb555b350de6) вернул пять обменов, nextCursor=null/hasMore=false. Ответы ассистента представлены content-reference placeholders; более ранняя история и вложения не получены. Аудит полного текста чата НЕ подтверждён. Сохранены подтверждённые источниками решения, без восстановления отсутствующего содержания по догадке.
- GitHub проверен через connector и отдельный clone: ветки, PR №6, исходный CTA commit, AGENTS, три repo-skills, release/SSH/TEST runbook и workflow triggers. Локальный CTA PROD HANDOFF прочитан отдельно. Сервер/SSH/cloud/API и повторный live/browser QA в этом аудите не запускались.
- Локальная рабочая копия проекта в ChatGPT (`club-gravitation.ru`) имеет другую базу: `feature/v5-form-2.2-wave1`, HEAD `ef38c127e11de511283a48f5cd93a1f425935314`, ahead 1, tracked diff пустой. Для аудита создан отдельный clone `audit-repo-20261019`, исходная база `af7efa5b0aa726c67f4b21c264466d2af7e9cf8f`.

## Ответственные источники

| Содержание | Единственное ответственное место / владелец |
|---|---|
| Устойчивые правила управления | [MASTER 00](https://docs.google.com/document/d/1guqaNuEoZcLePMglgEsDdgFhYQIJ02mf_SlQltNun5A/edit), управление клуба |
| Продукт сайта | [MASTER 07](https://docs.google.com/document/d/1l8unN8oYEHKykToPQsLRS5ual24Aq9O80gxiiQdrLkQ/edit), Влад+Лара |
| Анкета/CRM и персональные данные | [MASTER 06](https://docs.google.com/document/d/1JTInAWlfFsR1KSwUXfC6D-qc5QpJG8nBWJ1E-ITzvM8/edit), [MASTER 08](https://docs.google.com/document/d/1XfNr5YEuxub9cZoSq5tgVDksfof32LwoPwHo5Vacy2Q/edit), профильные управляющие направления |
| Состав формы и frozen legal 2.3 | [Модель анкеты](https://docs.google.com/document/d/154u5BpbgbHTLhdkJ2UcMUJbNARB14F_hGWULIKSS4PE/edit), [frozen Git source](https://github.com/vvars9650-svg/club-gravitation.ru/tree/3964d4a38bc89f68646bb8f3b212ed5822b1cb54/legal/frozen); не копировать тексты в память |
| Оперативный статус, изменения, передачи | Sheet, вкладки ТЕКУЩЕЕ СОСТОЯНИЕ / ИЗМЕНЕНИЯ / ПЕРЕДАТЬ ДАЛЬШЕ; управляющие чаты обновляют свои затронутые записи |
| Параметры EVENT 01 и оплата | [Рабочая карточка EVENT 01](https://docs.google.com/document/d/1KkLc-T2e-AS0akcAPTyLx4_NrZli_Su-WXU2W20sJ6E/edit); Влад+Лара / EVENT / 09 / 06 |
| Код и повторяемые процедуры | GitHub `vvars9650-svg/club-gravitation.ru`; Влад отвечает за техническое исполнение. AGENTS и `.agents/skills/gravitation-{release,handoff,visual-qa}` уже существуют |
| Этот аудит и основа перехода | GitHub, ветка `docs/control-chat-audit-20261019`; этот архив и `docs/CONTROL-CHAT-HANDOFF-DRAFT-20261019.md` |
| Указатель Drive на GitHub и ограничения | [Аудит и карта продолжения](https://docs.google.com/document/d/1IvZOqYk9INY440i9ghUgdTbBqzWGrZK4DdiLBXC82KY/edit), ID `1IvZOqYk9INY440i9ghUgdTbBqzWGrZK4DdiLBXC82KY`, папка «9. Сайт / 0. Документация сайта» ID `1dCJScuv2im6EIQ_h2T7qn9Dt8QXKsX0O`; технический управляющий чат |

Drive хранит указатель и приёмку, GitHub — версионируемый архив и инструкции. Полные копии MASTER/runbook не создаются. Для следующего задания читать актуальную запись Sheet, затем только профильный источник.

## Последний принятый релизный срез

Ниже серверные факты приняты по HANDOFF исполнителя и записям Sheet; заново на сервере не проверены. Git source и PR проверены независимо.

| Контур / этап | Зафиксированное состояние |
|---|---|
| FORM/legal 2.3, 15.10 | Source `3964d4a38bc89f68646bb8f3b212ed5822b1cb54`; legal live 11:51:26 МСК, intake 11:53:04 МСК. Старые 2.2/evidence сохранены. Последующие frontend deltas этого не меняли |
| EVENT 01 | `20261016-event01-7605aba-prod`, source `7605aba94e968543ca9f0a7f6b6e4af3875ba0c5`, затем включён в следующие релизы |
| ABOUT+FOUNDERS | `20261019-about-founders-06a75f6-prod`, source `06a75f6937839a4e8a7ec64d38ac332dc58f3d41`, теперь rollback target CTA V2 |
| Текущий PROD по HANDOFF | `20261019-cta-funnel-v2-af7efa5-prod`; [source af7efa5](https://github.com/vvars9650-svg/club-gravitation.ru/commit/af7efa5b0aa726c67f4b21c264466d2af7e9cf8f), ветка `codex/cta-funnel-prod-20261019` pushed |
| Публичный TEST | `cta-funnel-20261019-06a75f6-v2`; предыдущий V1 `cta-funnel-20261019-06a75f6-v1`; `PUBLIC_BLOCKED`, PROD endpoint пустой |
| TEST Admin | `final-gates-test-admin-20261014`, отдельный контур, без изменений CTA-релизом |
| PROD Admin | [операторский вход /admin-prod/](https://club-gravitation.ru/admin-prod/), OIDC; не путать с `/admin/` или TEST |

CTA: главная → ABOUT → EVENT 01 → `/apply/`; FOUNDERS → EVENT 01; обе кнопки EVENT 01 → одна анкета. Шапка сохраняет прямую «Подать заявку». Влад сообщил о личной проверке TEST и делегировании Ларой приёмки этого класса изменений; это конкретное согласование четырёх HTML, не общее изменение совместных полномочий основателей.

PROD CTA artifact: 64 файла, заменены четыре HTML, остальные 60 идентичны предыдущему PROD, добавлений/удалений нет. По исполнителю build + шесть наборов тестов PASS, 64 HTTPS hash checks, 11 HTTP(S) маршрутов и 24 viewport-проверки PASS. Проверки CTA без отправки заявок/фото. CI на release SHA не запускался; локальный PASS не означает CI PASS. `public-config.source_head` намеренно остался от прежней сборки, поскольку JS/config вне scope; provenance подтверждается source и release evidence.

## Технические решения и маршрутизация процедур

- Selectel обслуживает публичный frontend; PROD data path остаётся отдельным Yandex Cloud backend (Function/Gateway/YDB/private photo storage). Обсуждение переноса backend на Selectel не является выполненной миграцией. Не считать frontend release подтверждением изменения backend.
- TEST public, PROD public и Admin используют разные deployment-механизмы. TEST manager и SSH описаны только в [commit 15a388f](https://github.com/vvars9650-svg/club-gravitation.ru/tree/15a388f9dd8f6b544489ad619bde8762290d8e9d/docs): `SELECTEL-TEST-DEPLOY.md`, `SELECTEL-SSH-CLI.md`, `SELECTEL-TEST-DEPLOY-HANDOFF.md`. Не переустанавливать доступ из-за отсутствия этих файлов в текущей ветке.
- TEST manager допускает ограниченные status/deploy/rollback и delta утверждённых public файлов; apply/JS/config/legal/Admin защищены. Реальные пределы и команды читать в runbook, не копировать в новое задание всю процедуру. IDs в runbook относятся к 18.10, не к текущему TEST.
- PROD CTA использовал установленный `/home/gravdeploy/production-release-3964d4a.sh`, immutable release, проверку полного manifest и atomic current switch; rollback `20261019-about-founders-06a75f6-prod` проверен исполнителем, не выполнялся. Рабочий `/srv/gravitation/current` отделён от `/srv/gravitation-test/current` и `/srv/gravitation-admin/current`.
- Узкий frontend release строится от фактического активного артефакта целевой среды плюс только approved delta; целиком TEST в PROD не переносится. Исходники с нескольких dirty worktree объединять только по явно согласованному составу.
- Не запускать одновременно тесты, пересобирающие общий `public-dist`: в CTA это вызвало ложные сбои, последовательный повтор дал PASS. Остальные независимые проверки можно выполнять параллельно.
- Canonical build/preview и visual matrix уже определены в AGENTS/visual skill; сохраняются. Не создавать ещё одну QA-инструкцию. `.home-scroll` удаляется существующим `site.js`; восстановление не входило в CTA scope.
- Отдельная документационная ветка не запускает PROD workflow: `selectel-deploy.yml` только workflow_dispatch; Pages push ограничен `main`. CI может проверять документы, но не означает deploy. В этой задаче никаких workflow dispatch/merge/deploy.

## Локальное и GitHub: не потерять при переносе

Проверены read-only статусы домашнего репозитория `C:/Users/glada/OneDrive/Документы/GITHUB/club-gravitation.ru`:

| Копия | HEAD / состояние |
|---|---|
| Основная v5 | `d400052569231c082e8cf095da4385598c34244a`; dirty `backend/v5/deployment/admin-api.live-minimal.patch.yaml`, `backend/v5/deployment/admin-api.test.yaml`, `backend/v5/tests/test_admin_authorization_config.py`; не переносить в документационный commit |
| `.about-20261018` | `7605aba…`; dirty `about/index.html`, `assets/css/story.css` |
| `.founders-lara-20261018` | `15a388f…`; dirty `founders/index.html`, `assets/images/founders/founders-Lara.jpg` |
| `.cta-funnel-20261019` | `06a75f6…`; dirty `index.html`, `about/index.html`, `founders/index.html`, `first-contact/index.html` |
| `.cta-funnel-prod-20261019` | `af7efa5…`; tracked status чистый, source pushed |
| `.admin-cleanup` | `7fd58b073a15f7cb5172bec13fbccc1cdf9cea8c`, tracked status чистый; remote branch отсутствует в полученном списке, по Sheet push не было; browser smoke OPEN |

GitHub `v5` при аудите: `410c39392f5be49d56a87dadd7103bde1d2768e3`; `main`: `6cf41a7c7bee7365203091ab3e1760e5b8dd7b99`. [PR №6](https://github.com/vvars9650-svg/club-gravitation.ru/pull/6) открыт, Draft, head `codex/production-rc-20261014`, base `v5`, не merged. Эти refs не равны опубликованному CTA source. Интеграция source `06a75f6`, `af7efa5`, infra `15a388f` и PR6 остаётся отдельной задачей.

Полный CTA evidence находится только локально в `.release-evidence-cta-prod-20261019`: `HANDOFF.md`, `source.patch`, manifests, verification и browser evidence. Архив не утверждает, что эти файлы или server script перенесены на GitHub/Drive. Сначала проверить состав на секреты/ПД, если понадобится отдельный перенос доказательств. Фотографический master Лары — Drive ID `1NQSstbpvChzWjHBDRBk8V1QZ3y1pZxEv`; исходник не менять.

## Открытые вопросы и несоответствия

1. Полный текст УЧ ч7 недоступен инструменту. Для исчерпывающего аудита потребуется экспорт отсутствующей истории; текущая сохранённая база пригодна для проверки Владом, но не доказывает полноту чата.
2. Git integration и локальный Admin cleanup не завершены. Не merge/rebase/чистить worktree в рамках аудита. Локальные evidence и Admin commit не гарантированно доступны на другом компьютере.
3. MASTER и старые release runbook содержат исторические «PROD закрыт», TEST-only и старые active IDs. Более новые актуализации и Sheet имеют приоритет. MASTER не переписывались: новых продуктовых/управленческих решений аудит не принимает. В repo AGENTS уточнено сохранение уже работающего `PROD_ENABLED` при закрытом TEST.
4. Запись ИСТОЧНИКИ о коде сайта от 16.10 отстаёт от текущего CTA; обновляется точечно вместе с указателем аудита. Старые передачи остаются историей, не новым запретом публикации.
5. RKN-03 подано, сверка реестра не подтверждена; не считать снятие release gate доказательством сверки. Проверка юридического статуса не выполнялась в этом техническом аудите.
6. EVENT 01: дата страницы 15.11.2026 18:00–22:00 не доказывает бронь площадки. Последнее совместное решение 19.10 — СБП по телефону + ручной чек НПД; QR не универсален, Robokassa в резерве. Проверка платежа/лимитов/юрусловий открыта в профильных направлениях. Не менять здесь оферту и платёжную интеграцию.
7. `.home-scroll`, прежний favicon 404 и вопрос кеша CSS — известные отдельные замечания по источникам, не повторно воспроизведены и не исправлялись. Эффект приглашений через ABOUT остаётся маркетинговой гипотезой.

## Сохранение и проверка

Минимальный change set: этот архив, основа HANDOFF, две точечные правки существующих skills и уточнение AGENTS. Source сайта, backend, инфраструктура и workflows не меняются. Проверка: diff/whitespace, перечень файлов, наличие внутренних ссылок и skill frontmatter; после push — remote SHA и повторное чтение GitHub. Drive: повторное чтение нового указателя, его папки и изменённых строк Sheet. Точные итоговые SHA и результаты — в возвращаемом HANDOFF задачи и указателе Drive.

Переход в новый управляющий чат НЕ выполнен. Следующий шаг — проверка Владом этого пакета; затем отдельная финализация перехода по [основе HANDOFF](../CONTROL-CHAT-HANDOFF-DRAFT-20261019.md).
