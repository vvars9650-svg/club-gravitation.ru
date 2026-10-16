# Selectel: SSH/CLI с домашнего ПК

Последняя проверка: **16.10.2026**. SSH/CLI под `gravdeploy` работает; проверено
повторное подключение из нового процесса Windows OpenSSH. Полная готовность TEST
deployment без браузерной консоли **не подтверждена**: для изменения TEST нужны
серверные полномочия, которых у проверенного профиля сейчас нет.

## Постоянная среда и профиль

Разработка и публикация «Гравитации» по умолчанию выполняются только с домашнего
ПК. Новая локальная сессия использует существующий профиль, без поиска ключей.
Не переносить эту настройку автоматически на другой компьютер.

| Параметр | Подтверждённое значение |
| --- | --- |
| SSH client | Windows OpenSSH 9.5p2 |
| Alias | `selectel-gravitation` |
| User | `gravdeploy` |
| Config | `%USERPROFILE%\.ssh\config` |
| IdentityFile | `~/.ssh/gravitation-github-deploy` |
| Fingerprint ключа | `SHA256:CbvXchJsG+hEkH/w2xeViFITipBxZhUUFgzUusjEP10` |
| HostName | Адрес Selectel VDS сохранён в локальном профиле; в Git не публикуется |
| Проверенный host key | ED25519 `SHA256:7i1H5J9PMMi8vHKUuURtjo1uSBjTTpkHqe5VB37Exr4` |

Локальные параметры профиля: `IdentitiesOnly yes`, `IdentityAgent none`,
`BatchMode yes`, `PasswordAuthentication no`, `KbdInteractiveAuthentication no`,
`StrictHostKeyChecking yes`, `UpdateHostKeys no`, `ConnectTimeout 15`.
Используется существующий `%USERPROFILE%\.ssh\known_hosts`; его записи не менялись.
Перед добавлением блока создана локальная копия `config.backup-selectel-*`.
Исходные байты config и действующие VPN-профили сохранены.

Служба Windows `ssh-agent` при проверке: Stopped / Disabled. Успешное соединение
выполнено с `IdentityAgent none` и `BatchMode yes`, поэтому текущий профиль не
требует агента или интерактивной разблокировки ключа. Passphrase и ключ не менялись.
Вход после перезагрузки ПК отдельно не проверялся.

## Read-only проверка новой сессии

В новом терминальном процессе:

```powershell
ssh -G selectel-gravitation
ssh selectel-gravitation 'id; readlink /srv/gravitation/current; ls -ld /srv/gravitation-test/releases /srv/gravitation-admin/releases'
```

Ожидается успешная publickey-аутентификация под `gravdeploy`, exit code 0 и
чтение каталогов. Команда не разрешает deployment. Браузерная консоль для этих
проверок не требуется. Не принимать новый host key автоматически.

## Причина прежнего отказа

Предыдущие попытки использовали `gravitation-prod-selectel-home` и
`gravitation-prod-selectel-home-v2`. Для v2 диагностика повторно подтвердила:
сервер доступен, host key совпадает с `known_hosts`, публичный ключ
`SHA256:ggUguHkB5ehECUp4Ol48iOY1s9ctl/LrS8+DwgR5XQY` явно предъявлен, но
отвергнут сервером до подписи. Следовательно, этот отказ не вызван ssh-agent или
невозможностью разблокировать закрытый ключ. Точная серверная причина отклонения
v2 (например, отсутствие его авторизации) отдельно не исследовалась.

Правильный deploy-ключ подтверждён двумя независимыми проверками: успешной
publickey-аутентификацией и совпадением fingerprint с доступным
`/home/gravdeploy/.ssh/authorized_keys`. В старом config отсутствовал Selectel Host;
без явного `-i` OpenSSH выбирал стандартные имена ключей вместо deploy-ключа.
Исправление: добавлен отдельный постоянный alias с проверенным IdentityFile.

## TEST / PROD и deployment

Это снимок состояния на дату проверки, а не разрешение на публикацию.

- PROD: `/srv/gravitation/current` указывает на
  `/srv/gravitation/releases/20261015-3964d4a-prod`;
  source из утверждённого handoff — `3964d4a38bc89f68646bb8f3b212ed5822b1cb54`.
  `gravdeploy` имеет запись в `/srv/gravitation/releases` и `shared`.
- TEST public: Nginx `/etc/nginx/sites-available/test.club-gravitation.ru` использует
  прямой `root /srv/gravitation-test/releases/event01-20261016-7605aba`.
  `/srv/gravitation-test/current` и `shared` отсутствуют. Каталоги принадлежат root;
  `gravdeploy` может читать release, но не записывать в TEST base/releases.
- TEST Admin: `/srv/gravitation-admin/current` указывает на
  `/srv/gravitation-admin/releases/final-gates-test-admin-20261014`.
  Каталог принадлежит root, запись для `gravdeploy` недоступна.
- `sudo -n -l` сообщает `a password is required`. Доступная без пароля процедура
  публикации TEST для этого профиля не установлена. Не менять права, SSH,
  `authorized_keys`, пользователей или sudoers без отдельного разрешения.

Release/deploy skill: [gravitation-release](../.agents/skills/gravitation-release/SKILL.md).
PROD frontend runbook: [SELECTEL-DEPLOYMENT](SELECTEL-DEPLOYMENT.md) и
[selectel-release.sh](../scripts/selectel-release.sh). Скрипт жёстко использует
`BASE=/srv/gravitation`; запускать его для TEST нельзя. Workflow
[selectel-deploy.yml](../.github/workflows/selectel-deploy.yml) относится к PROD,
не запускается этой SSH-задачей. Перед будущей публикацией сверять текущие gates
и [ACTIVATION-2.3-HANDOFF](ACTIVATION-2.3-HANDOFF.md), включая независимый backend rollback.

TEST Admin: [SELECTEL-ADMIN-TEST](SELECTEL-ADMIN-TEST.md),
[FINAL-RELEASE-GATES](FINAL-RELEASE-GATES.md) и
[activate-test-admin.sh](../scripts/activate-test-admin.sh). Активация требует
разрешённого root-сеанса; скрипт сохраняет предыдущий symlink/snippet и при ошибке
возвращает их. Rollback после завершённого deployment — отдельная разрешённая
операция по сохранённым backup, не повторная активация того же release ID.

TEST public EVENT 01: действует отдельный root-owned release и прямой Nginx root.
Найден backup-каталог `/srv/gravitation-test/backups/event01-20261016-7605aba`
с режимом 700; его содержимое `gravdeploy` прочитать не может. Проверенная CLI
процедура deploy/rollback EVENT 01 под этим пользователем отсутствует. Для
публикации/возврата нужен отдельно разрешённый привилегированный доступ,
проверка backup и `nginx -t` перед reload. Не использовать PROD rollback.

## Типовые ошибки

- `Permission denied (publickey)`: проверить `ssh -G`, User, единственный
  IdentityFile и его fingerprint через `ssh-keygen -lf`. В ограниченном
  `ssh -vvv` различать `Offering public key`, `Server accepts key` и ошибку подписи.
  Не перебирать все ключи/пользователей и не читать закрытый ключ.
- `Load key ...` или ошибка подписи после `Server accepts key`: проверить доступ
  к файлу, целостность пары и необходимость интерактивной разблокировки.
  Не убирать passphrase ради автоматизации.
- `Host key verification failed` / changed host key: остановиться и независимо
  подтвердить серверный fingerprint. Не удалять known_hosts и не заменять его
  результатом неподтверждённого ssh-keyscan.
- Timeout: проверить маршрут/VPN и доступность TCP/22; это не доказательство
  неверного ключа. В этой диагностике один timeout сменился успешным соединением.
- Отказ записи в TEST при успешном SSH: подтверждённое ограничение серверных прав;
  изменение прав требует отдельного решения владельца.

## Передача следующему Codex

Использовать `ssh selectel-gravitation`, сначала read-only проверка. Не создавать
ключи заново. TEST и PROD в этой задаче не изменялись; workflow и Secrets также.
SSH-восстановление завершено, но полный статус `SELECTEL HOME SSH/CLI READY` для
обычного TEST deployment без консоли пока не присваивается. Следующее решение
владельца: отдельно разрешить подготовку ограниченного серверного механизма
TEST deploy/rollback либо предоставить уже разрешённый привилегированный CLI-доступ.
Управляющую таблицу обновляет управляющий чат; эта задача её не изменяет.
