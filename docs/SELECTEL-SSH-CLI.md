# Selectel: SSH/CLI с домашнего ПК

**Актуально 18.10.2026: SELECTEL TEST DEPLOY READY.** Профиль SSH работает. Публичный TEST deploy/rollback установлен и проверен, в том числе из новых SSH-процессов. Не повторять настройку доступа или диагностику ключей при обычной публикации.

## Постоянный профиль

Разработка и публикация по умолчанию выполняются с домашнего ПК. Использовать существующий alias:

```powershell
ssh selectel-gravitation
```

- User: `gravdeploy`.
- Config: `%USERPROFILE%\.ssh\config`.
- IdentityFile: `~/.ssh/gravitation-github-deploy`.
- Fingerprint ключа: `SHA256:CbvXchJsG+hEkH/w2xeViFITipBxZhUUFgzUusjEP10`.
- Проверенный host key ED25519: `SHA256:7i1H5J9PMMi8vHKUuURtjo1uSBjTTpkHqe5VB37Exr4`.
- HostName сохранён в локальном профиле; не публиковать его в Git.

Настроены `IdentitiesOnly yes`, `IdentityAgent none`, `BatchMode yes`, `PasswordAuthentication no`, `KbdInteractiveAuthentication no`, `StrictHostKeyChecking yes`, `UpdateHostKeys no`, `ConnectTimeout 15`. Используется существующий known_hosts. SSH-agent для этого профиля не требуется. Закрытый ключ и passphrase не читать/не менять и в чат не передавать.

## Публичный TEST: готовая процедура

[Runbook deploy/rollback](SELECTEL-TEST-DEPLOY.md) и [проверенный HANDOFF](SELECTEL-TEST-DEPLOY-HANDOFF.md).

```powershell
ssh selectel-gravitation 'sudo -n /usr/local/sbin/gravitation-test-release status'
```

Для разрешённого контентного deploy сформировать локальный delta package с явным списком файлов и передать его бинарно через stdin команде `deploy ID SHA256`. Не отправлять целиком production public-dist и не заменять TEST public-config. Точные команды — в runbook.

Отдельный rollback переключает на предыдущий проверенный TEST release:

```powershell
ssh selectel-gravitation 'sudo -n /usr/local/sbin/gravitation-test-release rollback'
```

Установлены root-owned command, state и ограниченное sudoers-правило. gravdeploy разрешены только status/deploy/rollback, без общего sudo, root shell, Nginx или initialize. Существующие владельцы TEST releases не менялись; прямой записи в release у gravdeploy нет.

Nginx TEST использует `/srv/gravitation-test/current`; после приёмки current — `event01-20261016-7605aba`, previous — `infra-smoke-20261018-b`. Перед каждой публикацией брать актуальный status, а не считать эти ID постоянными. PUBLIC_BLOCKED, apply, все JS, Admin и legal защищены manifest/allowlist.

## Разделение контуров

- TEST public: отдельный manager; PROD script использовать для TEST запрещено.
- PROD: `/srv/gravitation/current`, при проверке `20261016-event01-7605aba-prod`. Эта настройка не даёт разрешения на PROD deployment.
- TEST Admin: `/srv/gravitation-admin/current`, `final-gates-test-admin-20261014`. Public TEST sudo-правило не даёт права его менять.
- Backend/API/данные процедура не обслуживает. Управляющую таблицу обновляет управляющий чат.

Scripts `selectel-release.sh` и `.github/workflows/selectel-deploy.yml` относятся к PROD и не запускаются для TEST. Релизные разрешения TEST, PROD и Admin всегда отдельные.

## Если есть конкретный сбой

- `status` не проходит: сохранить ошибку, сверить runbook/фактические права. Не расширять sudoers и не переустанавливать механизм без отдельного решения.
- `Permission denied (publickey)`: сначала сверить alias/User/IdentityFile с этим runbook, не перебирать ключи. Углублять диагностику только при фактическом отказе SSH.
- Host key changed: остановиться и независимо подтвердить fingerprint, не принимать новый ключ автоматически и не удалять known_hosts.
- Timeout: проверить конкретный маршрут/VPN, не считать его доказательством неверного ключа.
- Лимит release, место на диске, неоднозначный журнал или повреждённый manifest: остановиться; очистка/восстановление прав не делегированы.

## Источник и установка

SSH-runbook и ссылки перенесены из `codex/selectel-ssh-home-20261016` без посторонних изменений этой ветки. Разрешение Влада на постоянный TEST manager получено отдельно. Установка выполнена через уже открытый им root-сеанс Selectel; SSH/ключи/пользователи не менялись. Backup: `/var/backups/gravitation-test-deploy/20261018T190115Z`.

SSH-сервер не разрешил PTY. Один ввод sudo-пароля был отклонён, после чего установка продолжена через существующую root-консоль владельца. Эти ограничения не обходились и не ослаблялись. После установки штатным status/deploy/rollback пароль и интерактивная консоль не нужны. Подробные результаты — в HANDOFF.
