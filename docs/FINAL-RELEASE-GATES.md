# Final release gates — 14.10.2026

Исходный принятый HEAD: eaf7519. Ветка codex/production-rc-20261014, Draft PR №6. PROD не изменён; merge, migration и публикация legal не выполняются.

## Юридический комплект

Файлы 2.3 приведены к согласованным ссылкам 2.3; состав короткой заявки отделён от добровольных интервью/исторических данных; обязательный контакт отделён от добровольной внешней ссылки. TEST/payload/служебные пояснения вынесены из юридического текста в [README комплекта](../legal/drafts/README.md). Frozen 2.2 сохранены. Требуется утверждение трёх текстов и даты Владом. После утверждения отдельный activation commit с frozen 2.3, canonical hash, точными версиями и открытием gate.

## TEST Admin

Во встроенном браузере через существующий аккаунт Влада выполнен реальный OIDC login с PKCE; callback очищен, authenticated workspace и карточка №000018 открылись. Контакт, статус, duplicate warning и evidence FORM-2.3 отображаются. Logout не выполнялся.

Операторский photo gate закрыт после разрешённого обновления TEST через открытый Владом существующий root-сеанс консоли Selectel. Активный frontend release — `final-gates-test-admin-20261014`; прежний `20260918-admin-crmv2` сохранён для rollback. SSH-ключи и права доступа не изменялись.

TEST artifact и scripts/activate-test-admin.sh размещены в /home/gravdeploy/test-admin-final-gates.tar.gz и /home/gravdeploy/activate-test-admin.sh. SHA-256 архива: `20f706cd22a7dca13e269da4940f8e9b9825b98a1f5de5defbd8fb8e5020fb60`; скрипта: `16fa8247b78bbf6dfe4d3c8ecbc7ad9f8d577a62bdfe8b15bf9cea2b2574aa88`. Оба checksum проверены перед исполнением. Выполнение завершилось `TEST_ADMIN_ACTIVE=final-gates-test-admin-20261014`; nginx -t PASS, неизменность PROD server block проверена скриптом. Для фото CSP разрешает только `https://storage.yandexcloud.net/gravitation-v5-test-photos-b1g4bdjb/`. Предыдущий TEST symlink и snippet сохранены в закрытом /srv/gravitation-admin/backups/final-gates-test-admin-20261014/.

Выполненная команда activation (через launcher, предварительно проверяющий SHA-256):

```bash
bash /home/gravdeploy/activate-test-admin.sh /home/gravdeploy/test-admin-final-gates.tar.gz 20f706cd22a7dca13e269da4940f8e9b9825b98a1f5de5defbd8fb8e5020fb60 final-gates-test-admin-20261014
```

После activation выполнен реальный OIDC-вход через сохранённую сессию Влада и повторно открыта №000018. Секция «Фотография» присутствует; изображение complete=true, naturalWidth=1, naturalHeight=1, декодировано из точного TEST bucket. Это ранее загруженный синтетический PNG 1×1, поэтому на экране почти незаметен. Signed URL X-Amz-Expires=180; referrerPolicy=no-referrer. Console warn/error отсутствуют, CSP загрузку разрешает. Заявка, фото, статусы и evidence не изменялись. TEST backend/OIDC/Gateway и PROD deployment остаются прежними.

## PROD backend

[Происхождение и rollback](PROD-BACKEND-PROVENANCE.md): найдены deployment history активного v5-prod-admin.zip и архивный Git snapshot b306cf4. В RC восстановлено разделение TEST/PROD с отсутствием TEST fallback в PROD, packaged frozen consent и environment в YDB/handler. Создан отдельный production builder с file hashes/manifest и entry-point запретом запуска в TEST. FORM-2.3 на сервере PROD закрыт до legal activation. PROD candidate не развёрнут. Независимый rollback возвращает tag на сохранённую active version d4ej2creip5g0iloi3vh; он не зависит от frontend symlink. Первоначальный ZIP/checksum итоговой версии не сохранился, побайтовое равенство пересборки не заявляется.

## РКН

[Сверка RKN-03](RKN-03-FORM-2.3.md) выполнена по доступному Google Doc. Цели и обычный характер фотографии сохранены; обязательность контакта и состав новой формы требуют уточнения описания. Чтобы сделать окончательный вывод об актуализации уведомления, нужны сформированный порталом PDF №100432874 от 23.09 и актуальная запись реестра №23-26-186952. Ключ уведомления не нужен.

## Проверки

После восстановления runtime isolation выполнены 182 backend-теста (новые PROD gate/package и legal checks плюс затронутая регрессия). TEST Admin artifact safety и bash syntax PASS. Public visual/browser/TEST submission E2E прежнего принятого этапа не повторялись. Cloud TEST остаётся на ранее принятой версии d4ev92fcfmgoj0sfr64f; изменённый универсальный runtime в cloud не выпускался.

Готовность к разрешению production: NO-GO до утверждения legal, activation commit, сверки RKN и приёмки восстановленного PROD candidate. Живой operator photo QA — PASS; блокер привилегированного TEST доступа разрешён использованием существующего root-сеанса. Код и пакеты подготовлены для оставшихся действий.
