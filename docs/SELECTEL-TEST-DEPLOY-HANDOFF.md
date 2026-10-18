# SELECTEL TEST DEPLOY READY

18.10.2026. Установка выполнена после отдельного явного разрешения Влада, в открытом им существующем root-сеансе Selectel. Ключи, SSH-политика, пользователи и владельцы существующих каталогов не менялись. Последующие deploy/rollback работают через обычный `ssh selectel-gravitation` под gravdeploy без пароля.

## Установлено

- `/usr/local/sbin/gravitation-test-release`: root:root 0755, SHA-256 `4686bf1b4f9d863d602c040cafb13e7f0378985ea11e3c2bf5907f9eeb8f3d79`.
- `/var/lib/gravitation-test-deploy`: root:root 0700, baseline manifest, allowlist, журнал переключений и release manifests.
- `/etc/sudoers.d/gravitation-test-public`: root:root 0440. Только `(root) NOSETENV: NOPASSWD` на `status`, `deploy ID SHA256`, `rollback` фиксированного script. Нет shell, Nginx, initialize или произвольного command/path.
- `/srv/gravitation-test/current`: root-owned symlink; Nginx TEST root изменён только на него. Сам TEST releases остаётся root-owned, gravdeploy не получает прямую запись.
- Backup установки: `/var/backups/gravitation-test-deploy/20261018T190115Z`. Содержит исходный/итоговый TEST Nginx config, sudoers candidate, hashes sources и read-only снимок PROD/Admin links.

При первоначальной установке `nginx -t`, candidate/global `visudo` и reload прошли. Изменение TEST Nginx побайтово соответствует единственной утверждённой root-директиве. TEST Admin include не изменён.

## Проверенные команды

```sh
ssh selectel-gravitation 'sudo -n /usr/local/sbin/gravitation-test-release status'
ssh selectel-gravitation 'sudo -n /usr/local/sbin/gravitation-test-release rollback'
```

Deploy вызывается как `sudo -n /usr/local/sbin/gravitation-test-release deploy ID SHA256` с JSON delta через бинарный stdin. [Runbook](SELECTEL-TEST-DEPLOY.md) содержит packager и пример передачи без преобразования байтов PowerShell.

## Live acceptance

1. Из нового SSH-процесса status подтвердил исходный TEST.
2. Deploy `infra-smoke-20261018-a` с нулевым delta; current сменился, полный manifest совпал с baseline. Rollback вернул исходный TEST.
3. Новые SSH-процессы повторили deploy `infra-smoke-20261018-b` и rollback. Подтверждены повторное использование и сохранность previous.
4. После каждого switch и rollback: `/`, `/about/`, `/apply/`, `/admin-test/` TEST и `/` PROD отвечают HTTPS 200. `/about/` имеет исходную checksum, редакция 18.10 не публиковалась. PUBLIC_BLOCKED и пустой PROD endpoint сохранены.
5. Установленный script отклонил protected public-config, неверную SHA-256 и stale base. Проверки sudo permissions без исполнения команд отвергли root shell, Nginx и initialize.
6. Полные manifests и targets TEST/PROD/TEST Admin до/после совпали; Admin snippet и HTTP response hashes также совпали.

Итоговый current: `event01-20261016-7605aba`. Previous: `infra-smoke-20261018-b`. Оба smoke release сохранены; содержимое каждого идентично прежнему TEST, все 64 файла.

Контрольные суммы полных inventories (JSON mapping относительный путь → SHA-256, sort_keys=True):

| Контур | SHA-256 inventory до и после |
| --- | --- |
| TEST | `8fdde9282ef5bde276dcc9cc484bdb2e753e02ebd1c0c2db3d3988e23f9fbc50` |
| PROD | `5a9f2ad34c63378429a69a7329f2833b15e3245753a7aabb7a558147432dcbb9` |
| TEST Admin | `5d5eda050c386e63d9bfbf5ce99b27fd263aae6310cbded2e1b966d3610bc525` |

PROD target: `20261016-event01-7605aba-prod`. TEST Admin target: `final-gates-test-admin-20261014`. Production deploy/rollback, Admin deployment, backend, данные, API и управляющая таблица не затрагивались.

## Код и дальнейшая работа

Source branch: `codex/selectel-test-deploy`, исходная база `7605aba94e968543ca9f0a7f6b6e4af3875ba0c5`. Этот документ фиксируется в одном commit с scripts/runbook/AGENTS/Skill; точный commit берётся из Git, чтобы не создавать самоссылку.

12 Linux unit-тестов PASS, Python syntax PASS, sudoers parse PASS, git diff check PASS. Режим root для unit fixtures эмулировался; настоящие root permissions/activation и отказы отдельно проверены после установки. Полный frontend build не повторялся: публичные исходники и содержимое TEST в инфраструктурной задаче не менялись.

Изменения Git ограничены TEST scripts, tests, документацией, ссылками AGENTS/release Skill и точечными LF-атрибутами. ABOUT worktree и чужие dirty backend-правки сохранены. Merge не выполняется. Инструкции SSH перенесены из `codex/selectel-ssh-home-20261016` без посторонних изменений этой ветки.

Механизм сохраняет PUBLIC_BLOCKED файлы; одобрение контента/live QA обязательно при каждой публикации. SHA-256 не является подписью или отдельным approval. Лимит 20 releases; очистка не делегирована. Не переустанавливать механизм и не повторять диагностику ключей в будущих сессиях. Для ABOUT нужна отдельная контентная задача/продолжение ранее разрешённого TEST deploy; эта инфраструктурная задача ABOUT не публикует.
