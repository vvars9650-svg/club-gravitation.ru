# Публичный Selectel TEST: deploy и rollback

> Актуализация 19.10.2026: после отдельного разрешения Влада в установленную TEST allowlist добавлены только `terms/index.html` и `offer/index.html`. Они публикуются штатным SSH `deploy`; root-консоль для повторных публикаций этих путей не требуется. Frozen legal TXT, FORM, PPD, CONSENT-PD, apply, JS/config и Admin остаются защищены. [Подробности и evidence](LEGAL-SBP-TEST-20261019.md). Перед каждым deploy брать фактический `status`; ID в истории установки не является текущим baseline.


**Статус 18.10.2026: SELECTEL TEST DEPLOY READY.** Установлено после отдельного разрешения Влада через открытую им root-консоль Selectel. Будущие сессии используют готовые команды ниже; переустановка, повторная диагностика SSH и изменение прав не нужны.

Backup установки: `/var/backups/gravitation-test-deploy/20261018T190115Z`. Активный TEST: `event01-20261016-7605aba`; previous после контрольных откатов: `infra-smoke-20261018-b`. Содержимое TEST осталось прежним, ABOUT 18.10 не публиковался.

Проверено: два нулевых delta release (`infra-smoke-20261018-a`, `infra-smoke-20261018-b`), два rollback и повторное использование из новых SSH-процессов. Во всех состояниях полный manifest содержит прежние 64 файла, HTTPS отвечает 200, PUBLIC_BLOCKED сохранён. Полные manifests и targets TEST/PROD/TEST Admin до/после идентичны. Admin snippet неизменен; TEST Nginx отличается только согласованной root-директивой. sudo permission queries подтвердили отсутствие прав на shell, Nginx и initialize; защищённый public-config, неверная checksum и stale base отклонены установленным script.

Установленный manager SHA-256: `4686bf1b4f9d863d602c040cafb13e7f0378985ea11e3c2bf5907f9eeb8f3d79`. Исходники Linux scripts зафиксированы с LF через точечные `.gitattributes`.


SSH: `ssh selectel-gravitation`, пользователь `gravdeploy`, домашний ПК. Ключи заново не диагностировать и не создавать; см. [SSH-runbook](SELECTEL-SSH-CLI.md).

## Границы процедуры

Постоянный root-owned `/usr/local/sbin/gravitation-test-release` выполняет только операции в `/srv/gravitation-test` и `/var/lib/gravitation-test-deploy`. Нет shell/subprocess, произвольных путей, переменных окружения, исполнения загруженного кода или операций Nginx. Shebang `/usr/bin/python3 -I` исключает Python environment/user-site overrides.

`gravdeploy` получает NOPASSWD/NOSETENV только на три формы вызова: `status`, `deploy ID SHA256`, `rollback`. Sudoers wildcard для deploy ограничен дополнительно точным количеством аргументов и регулярными выражениями в script. Инициализация и installer через sudoers не разрешены. Скрипт/политика/состояние и релизы принадлежат root; прямые права записи gravdeploy не расширяются. Общий sudo, root shell, Nginx reload и TEST Admin не разрешаются.

Разрешены изменения существующих восьми публичных HTML: `/`, `/404.html`, `/about/`, `/events/`, `/first-contact/`, `/founders/`, `/terms/`, `/offer/`; семи публичных CSS (`site`, `story`, `polish`, `tz-20260831`, `events-hub`, `first-contact`, `founders`) и существующих PNG/JPEG/WebP внутри `assets/images/`. Набор файлов release неизменяемый: новые пути/удаления требуют отдельной проверки политики владельцем, штатная команда это не позволяет.

Все JavaScript, public-config, apply, Admin, юридические frozen TXT, CNAME, бренд/SVG и прочие файлы защищены SHA-256 исходной TEST-базы. Их изменение запрещено. Проверяется точный JSON `PUBLIC_BLOCKED` и пустой PROD endpoint. Это гарантия сохранности gate-файлов, а не анализ произвольного HTML/CSS: одобрение содержимого и browser/live QA обязательны перед/после каждого deploy. Backend и данные процедура не обслуживает.

## Как устроена публикация

1. JSON delta приходит через stdin, максимум 48 MiB; файл максимум 20 MiB, не более 64 файлов. До записи проверяются SHA-256 всего пакета и каждого файла, уникальность JSON keys, base release, ID и root-owned allowlist.
2. Script блокирует параллельную операцию flock, проверяет manifest и неизменяемые файлы действующего TEST. Symlink, hardlink, нестандартные типы файлов, владелец не root и group/world write отвергаются.
3. Действующий TEST копируется в новый root-owned staging; заменяются только явно перечисленные файлы. Итоговый полный manifest должен совпасть с ожидаемым. Новые релизы не перезаписываются и автоматически не удаляются.
4. Новый release переименовывается в окончательный каталог. Записывается журнал переключения, затем временная ссылка заменяет `current` через атомарный `os.replace` на той же ФС. Старый release записывается как previous; содержимое активного release не редактируется.
5. `rollback` переключает только на предыдущий проверенный release. Повторный rollback возвращает обратное направление. При незавершённом переключении следующая команда сверяет журнал с current и восстанавливает метаданные; неоднозначное состояние требует владельца. В релизах выполняется fsync файлов и директорий переключения; гарантии диска при полном отказе питания отдельно не сертифицированы.

Лимит — 20 каталогов release, перед копированием проверяется место под копию с резервом 512 MiB. При достижении лимита процедура останавливается; удаление старых релизов не делегировано и требует отдельного решения владельца. Автоматической очистки нет.

SHA-256 здесь обеспечивает целостность и сверку с одобренным исходником; отправитель с разрешённым sudo deploy сам задаёт checksum, это не криптографическая подпись и не независимый approval gate. Код страницы должен быть согласован в задаче.

## Однократная установка — справка для восстановления, повторно не запускать

Предлагаемый Nginx diff: [SELECTEL-TEST-NGINX.patch](SELECTEL-TEST-NGINX.patch). Меняется одна директива TEST root:

```diff
- root /srv/gravitation-test/releases/event01-20261016-7605aba;
+ root /srv/gravitation-test/current;
```

Первоначально `current` указывает на тот же `event01-20261016-7605aba`: содержимое сайта не меняется, ABOUT не публикуется. TEST Admin include сохраняется байт в байт.

В утверждённом root-сеансе использовать проверенный по SHA-256 пакет из root-controlled staging, затем `python3 -I scripts/install-selectel-test-release.py`. Installer НЕ включается в sudoers и не остаётся постоянной привилегированной командой. Он:

- отказывается при изменении Nginx baseline SHA-256 `c447613454acac782ee1a957a95d4ae5f5be8fda8bcc51d14fdd18eaa076f9a1` или существующей установке;
- сохраняет TEST Nginx до/после, контрольные суммы sources и read-only снимок PROD/Admin symlink в `/var/backups/gravitation-test-deploy/<UTC timestamp>/` (root 0700);
- устанавливает command root:root 0755, state root:root 0700 и `/etc/sudoers.d/gravitation-test-public` root:root 0440;
- фиксирует inventory, baseline checksums, allowlist и initial manifest; создаёт TEST current;
- меняет только TEST root, выполняет `nginx -t`, `visudo -cf` candidate, затем `visudo -c`, reload Nginx и status;
- при обычной ошибке удаляет созданное sudo-правило/command, восстанавливает исходный TEST config, выполняет nginx test/reload и возвращает прямой root. Диагностические state/backup сохраняются для разбора. Жёсткое прерывание самого installer требует root-восстановления из backup.

Reload затрагивает общий процесс Nginx. PROD/Admin-конфигурации не меняются; до reload проверить отсутствие посторонних pending изменений в Nginx, после — HTTPS smoke и hashes обоих контуров.

Ручной аварийный rollback установки в том же утверждённом root-сеансе: восстановить `test-nginx.before` в **только TEST vhost**, проверить `nginx -t`, reload; убрать **только** новое sudoers-правило и command. TEST releases не удалять. Не использовать production rollback. Перед любым повтором installer сначала изучить retained state, не удалять его вслепую.

## Команды после установки

```powershell
ssh selectel-gravitation 'sudo -n /usr/local/sbin/gravitation-test-release status'
```

Сначала взять current из ответа. Пакет формируется локально из явно согласованных файлов, не из целого production artifact:

```powershell
python scripts/package-test-release.py --base CURRENT_TEST_ID --root APPROVED_SOURCE --output test-package.json about/index.html assets/css/story.css
```

Это пример будущей отдельной контентной задачи. В инфраструктурной приёмке **не использовать ABOUT-пакет**; создать пакет без списка файлов (нулевой delta), SHA-256 выведет packager. Пакет передавать бинарно через subprocess stdin, не через PowerShell Get-Content/текстовый pipeline:

```python
from pathlib import Path
import subprocess
import hashlib
payload = Path('test-package.json').read_bytes()
sha = hashlib.sha256(payload).hexdigest()
subprocess.run(['ssh', 'selectel-gravitation',
    'sudo -n /usr/local/sbin/gravitation-test-release deploy APPROVED_RELEASE_ID ' + sha],
    input=payload, check=True)
```

Release ID должен быть отдельно определён задачей, допустимы только латинские буквы/цифры/`_`/`-`, максимум 96 символов; не подставлять непроверенный ввод в SSH remote command.

Отдельный rollback:

```powershell
ssh selectel-gravitation 'sudo -n /usr/local/sbin/gravitation-test-release rollback'
```

## Проверенная процедура приёмки и будущих повторных проверок

В новом терминальном процессе проверить sudo rights: разрешены только status/deploy/rollback, initialize/root shell/произвольная команда запрещены. Не проверять запрет фактической опасной командой; достаточно `sudo -n -l` и command permission query.

Снять baseline HTTPS/status/hashes TEST, PROD, TEST Admin (включая конфигурации), затем опубликовать нулевой delta smoke release, проверить новый current, точное совпадение всего inventory, `PUBLIC_BLOCKED` и HTTPS. Выполнить rollback к исходному TEST и подтвердить hashes. Ещё одним новым SSH-процессом выполнить status и повторный smoke deploy/rollback с новым ID. Финальным активным release оставить исходный TEST; предыдущие релизы сохранены.

При существенном live сбое выполнить TEST rollback, подтвердить HTTPS и исходные hashes. Если Nginx миграция дала сбой — rollback установки из backup через разрешённый root-сеанс. Записать результаты и только затем поставить `SELECTEL TEST DEPLOY READY`.

## Проверки подготовленного кода

18.10.2026: 12 Linux unit-тестов PASS под gravdeploy на временных fixtures. Для fixtures эмулируется uid root, реальные проверки modes/types/links/manifests остаются; отдельный тест проверяет отказ чужому uid. Это не live/root-приёмка установки. Серверные /srv, sudoers и Nginx unit-тестами не изменялись.

Связанные файлы: `scripts/selectel-test-release.py`, `scripts/package-test-release.py`, `scripts/selectel-test-deploy.sudoers`, `scripts/install-selectel-test-release.py`, `tests/test_selectel_test_release.py`.
