# Гравитация — кастомная анкета на Apps Script

Это отдельное веб-приложение Apps Script с полностью нашей HTML/CSS-формой. Google Forms не используется.

Архитектура формы:

`HtmlService → google.script.run.saveApplication(form) → Google Sheets + Google Drive`

Никаких CORS, JSONP, postMessage-подтверждений, polling или внешнего POST.

## GitHub — источник истины

Рабочие исходники находятся только в этой папке:

- `Code.gs`
- `Authorize.gs`
- `Index.html`
- `Styles.html`
- `Script.html`
- `appsscript.json`

Ручное редактирование кода в `script.google.com` после включения CI/CD не используется.

## Автоматизация

Workflow: `.github/workflows/apps-script-form.yml`.

На каждом изменении `apps-script-form/**` он:

1. запускает `validate.mjs`;
2. устанавливает официальный `@google/clasp` 3.3.0;
3. авторизуется через секрет `CLASPRC_JSON`;
4. при первом запуске сам создаёт standalone Apps Script-проект `Гравитация — анкета FORM`;
5. сохраняет `.clasp.json` в репозиторий;
6. выполняет `clasp push --force`;
7. создаёт или обновляет одно и то же web app deployment;
8. сохраняет `.deployment-id` и `.webapp-url` в репозиторий;
9. делает HTTP smoke-test опубликованной формы.

Таким образом после bootstrap изменение кода выглядит так:

`ChatGPT → commit GitHub → CI validation → clasp push → deployment → smoke-test`.

## Единственный секрет

В GitHub Actions требуется один repository secret:

`CLASPRC_JSON`

Это содержимое `~/.clasprc.json`, созданное командой:

```bash
npx @google/clasp@3.3.0 login --no-localhost
```

Содержимое `.clasprc.json` нельзя коммитить в репозиторий или отправлять в чат. Его нужно вставить только в:

`GitHub → Settings → Secrets and variables → Actions → New repository secret`.

Перед первым запуском также должен быть включён Apps Script API в настройках аккаунта Google.

## Однократная авторизация runtime

После первого автоматического создания проекта Google может потребовать один раз выдать самому скрипту права на Sheets и Drive. Для этого в созданном проекте запускается `authorizeFormApp_` и подтверждаются разрешения. Это OAuth-согласие Google; его нельзя безопасно обойти автоматизацией.

После этого обычные изменения кода и deployment выполняются GitHub Actions без ручного копирования файлов.

## Защита от регрессий

`validate.mjs` останавливает deployment, если:

- отсутствует обязательный файл;
- сломан JavaScript-синтаксис `.gs` или `Script.html`;
- манифест потерял web app / Drive / Sheets настройки;
- вернулся `fetch`, XHR, postMessage или localStorage;
- на последнем шаге снова появилась кнопка `Далее`;
- исчез `google.script.run.saveApplication(form)`;
- сломан обязательный предпросмотр фотографии.
