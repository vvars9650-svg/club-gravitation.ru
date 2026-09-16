# Selectel VDS: безопасный deployment публичного сайта

Этот pipeline публикует только артефакт `public-dist`, который создаётся существующим
скриптом `scripts/build-public.js`. Артефакт сохраняет режим `PUBLIC_BLOCKED`: отправка
анкет и фотографий из публичного сайта не выполняется. Backend, API и серверная
конфигурация в этот deployment не входят.

Workflow `.github/workflows/selectel-deploy.yml` запускается только вручную через
`workflow_dispatch`. Автоматического запуска от `push` нет. Workflow не использует
`sudo`, не меняет Nginx, UFW, SSH, DNS или GitHub Pages.

## GitHub Environment и Secrets

Создайте защищённое GitHub Environment с точным именем `selectel-production`.
Рекомендуется включить required reviewers. В Environment добавьте четыре secrets:

| Secret | Значение |
|---|---|
| `SELECTEL_SSH_PRIVATE_KEY` | Закрытый SSH deploy key пользователя `gravdeploy`, включая строки BEGIN/END |
| `SELECTEL_SSH_HOST` | Адрес Selectel VDS; адрес не хранится в репозитории |
| `SELECTEL_SSH_USER` | `gravdeploy` |
| `SELECTEL_SSH_KNOWN_HOSTS` | Заранее проверенная строка `known_hosts` для сервера |

`SELECTEL_SSH_KNOWN_HOSTS` нельзя получать слепым `ssh-keyscan` внутри workflow:
это не подтверждает подлинность сервера. Администратор должен сверить fingerprint
host key по независимому доверенному каналу (например, через консоль Selectel или
при первоначальной ручной настройке), а затем сохранить полную OpenSSH-строку
`known_hosts` как secret. Workflow требует `StrictHostKeyChecking=yes` и завершится
ошибкой при несовпадении ключа.

## Ограничение default branch

GitHub обрабатывает `workflow_dispatch`, когда файл workflow присутствует в default
branch репозитория. Сейчас default branch — `main`. Подготовка этой feature-ветки не
меняет `main`. До отдельно одобренной интеграции workflow в default branch кнопка
ручного запуска может не появиться в GitHub Actions.

Существующий `.github/workflows/pages.yml` автоматически запускается при изменении
`main`. Поэтому интеграцию deployment-файлов в `main` следует планировать отдельно:
эта задача не выполняет merge и не отключает GitHub Pages.

## Первый deployment после одобренного merge

1. Убедитесь, что Environment и все четыре secrets созданы, а fingerprint host key
   проверен независимо.
2. В GitHub откройте **Actions → Deploy public site to Selectel → Run workflow**.
3. Выберите проверенный ref/commit и операцию `deploy`. Поле
   `rollback_release_id` оставьте пустым.
4. Подтвердите запуск через required reviewer Environment, если защита включена.
5. Дождитесь успешного завершения всех public release checks и release job.

Workflow создаёт уникальный release ID в формате:

```text
<UTC timestamp>-<full commit SHA>-<GitHub run ID>-<run attempt>
```

Архив передаётся во временный каталог, на сервере сверяется его SHA-256, проверяются
пути и типы записей архива, наличие обязательных public-файлов и маркер
`PUBLIC_BLOCKED`. Только после этого release перемещается в
`/srv/gravitation/releases/<release-id>`, а `/srv/gravitation/current` атомарно
переключается командой `mv -T`. До переключения текущий release записывается в
`/srv/gravitation/shared/previous-release`.

При ошибке до атомарного переключения `current` не меняется. Незавершённый staging и
загруженный архив удаляются; уже созданная, но не активированная release-директория
может остаться для ручного аудита и не влияет на `current`.

## Проверка deployment

После успешного workflow администратор выполняет read-only проверки под
`gravdeploy`:

```bash
readlink -f /srv/gravitation/current
release_dir="$(readlink -f /srv/gravitation/current)"
test -f "$release_dir/index.html"
test -f "$release_dir/assets/js/apply.js"
grep -F 'PUBLIC_BLOCKED' "$release_dir/assets/js/apply.js"
```

Затем проверьте публичный сайт в браузере: страницы открываются, а форма сообщает,
что приём заявок временно недоступен. Не отправляйте реальные персональные данные или
фотографии для проверки.

## Как определить развернутый commit

Выполните:

```bash
basename "$(readlink -f /srv/gravitation/current)"
```

Release ID содержит полный 40-символьный commit SHA между первым и последними двумя
компонентами (`GitHub run ID` и `run attempt`). Тот же release ID и commit SHA
показываются в job summary успешного deploy workflow.

## Rollback

Для возврата на непосредственно предыдущий release:

1. Запустите тот же workflow вручную.
2. Выберите операцию `rollback`.
3. Оставьте `rollback_release_id` пустым. Скрипт использует значение из
   `/srv/gravitation/shared/previous-release`.
4. После успешного job повторите read-only проверки из раздела выше.

Для переключения на другой известный release укажите его точное имя из
`/srv/gravitation/releases` в `rollback_release_id`. Скрипт принимает только простой
release ID, проверяет содержимое каталога и атомарно переключает `current`. Release,
который был активен до rollback, становится новым `previous-release`, поэтому
последнее переключение можно отменить ещё одним rollback с пустым полем.

Первый rollback после первого deployment может вернуть исходный
`bootstrap-blocked`. Для него скрипт отдельно проверяет наличие безопасной статической
заглушки «Сайт временно недоступен» и отсутствие исполняемых скриптов.

Rollback не пересобирает файлы и не обращается к DNS, Nginx или GitHub Pages.
