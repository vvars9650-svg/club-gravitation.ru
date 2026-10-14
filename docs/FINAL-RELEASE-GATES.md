# Final release gates — 14.10.2026

Исходный принятый HEAD: eaf7519. Ветка codex/production-rc-20261014, Draft PR №6. PROD не изменён; merge, migration и публикация legal не выполняются.

## Юридический комплект

Файлы 2.3 приведены к согласованным ссылкам 2.3; состав короткой заявки отделён от добровольных интервью/исторических данных; обязательный контакт отделён от добровольной внешней ссылки. TEST/payload/служебные пояснения вынесены из юридического текста в [README комплекта](../legal/drafts/README.md). Frozen 2.2 сохранены. Требуется утверждение трёх текстов и даты Владом. После утверждения отдельный activation commit с frozen 2.3, canonical hash, точными версиями и открытием gate.

## TEST Admin

Во встроенном браузере через существующий аккаунт Влада выполнен реальный OIDC login с PKCE; callback очищен, authenticated workspace и карточка №000018 открылись. Контакт, статус, duplicate warning и evidence FORM-2.3 отображаются. Logout не выполнялся.

Live TEST frontend остаётся release `20260918-admin-crmv2`; в нём отсутствует новая photo UI. Существующий gravdeploy SSH доступен, но TEST release/symlink и Nginx snippet принадлежат root; sudo требует пароль. Оба проверенных существующих root-ключа сервером отклонены. Второй ключ проверен только после явного разрешения Влада. Автоматическая проверка первоначально остановила альтернативный root-key probe; разрешение получено, но аутентификация не прошла.

Подготовлены и проверены TEST artifact и scripts/activate-test-admin.sh. Они размещены в /home/gravdeploy/test-admin-final-gates.tar.gz и /home/gravdeploy/activate-test-admin.sh. SHA-256 архива: `20f706cd22a7dca13e269da4940f8e9b9825b98a1f5de5defbd8fb8e5020fb60`. Скрипт меняет только TEST Admin release и TEST snippet, сохраняет предыдущие значения в закрытом backup-каталоге, проверяет Nginx и неизменность PROD server block. Для фото добавляется только точный TEST bucket CSP path. Скрипт не исполнялся; просмотр фото в живом UI пока НЕ ПРОВЕРЕН.

Команда для уже авторизованного root-сеанса (не для gravdeploy и не через неподтверждённый sudo):

```bash
bash /home/gravdeploy/activate-test-admin.sh /home/gravdeploy/test-admin-final-gates.tar.gz 20f706cd22a7dca13e269da4940f8e9b9825b98a1f5de5defbd8fb8e5020fb60 final-gates-test-admin-20261014
```

После выполнения — reload TEST Admin, повторное открытие №000018, проверка изображения/Network/CSP. Существующий private TEST backend, OIDC, API Gateway и данные не меняются.

## PROD backend

[Происхождение и rollback](PROD-BACKEND-PROVENANCE.md): найдены deployment history активного v5-prod-admin.zip и архивный Git snapshot b306cf4. В RC восстановлено разделение TEST/PROD с отсутствием TEST fallback в PROD, packaged frozen consent и environment в YDB/handler. Создан отдельный production builder с file hashes/manifest и entry-point запретом запуска в TEST. FORM-2.3 на сервере PROD закрыт до legal activation. PROD candidate не развёрнут. Независимый rollback возвращает tag на сохранённую active version d4ej2creip5g0iloi3vh; он не зависит от frontend symlink. Первоначальный ZIP/checksum итоговой версии не сохранился, побайтовое равенство пересборки не заявляется.

## РКН

[Сверка RKN-03](RKN-03-FORM-2.3.md) выполнена по доступному Google Doc. Цели и обычный характер фотографии сохранены; обязательность контакта и состав новой формы требуют уточнения описания. Чтобы сделать окончательный вывод об актуализации уведомления, нужны сформированный порталом PDF №100432874 от 23.09 и актуальная запись реестра №23-26-186952. Ключ уведомления не нужен.

## Проверки

После восстановления runtime isolation выполнены 182 backend-теста (новые PROD gate/package и legal checks плюс затронутая регрессия). TEST Admin artifact safety и bash syntax PASS. Public visual/browser/TEST submission E2E прежнего принятого этапа не повторялись. Cloud TEST остаётся на ранее принятой версии d4ev92fcfmgoj0sfr64f; изменённый универсальный runtime в cloud не выпускался.

Готовность к разрешению production: NO-GO до утверждения legal, activation commit, живой operator photo QA, сверки RKN и приёмки восстановленного PROD candidate. Код и пакеты подготовлены для этих действий.
