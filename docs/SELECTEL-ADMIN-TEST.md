# Selectel: standalone TEST Admin frontend

Этот документ описывает следующий ручной этап. Он не разрешает и не выполняет
deployment, изменение DNS, публикацию PROD backend или включение public intake.

## Граница артефактов

Публичный сайт собирается командой `node scripts/build-public.js` в `public-dist`.
В нём `/admin/` остаётся статической заглушкой без JavaScript, OIDC и TEST Admin
config, а `/apply/` остаётся в режиме `PUBLIC_BLOCKED`.

Admin собирается отдельно:

```bash
ADMIN_SELECTEL_ORIGIN=https://<selectel-https-origin> node scripts/build-admin-selectel.js
```

Результат — `admin-selectel-dist` с шестью файлами: `index.html`, двумя CSS и
тремя JavaScript-файлами. В артефакт не входят backend, legal, public intake,
credentials или секреты. Build завершается ошибкой без точного HTTPS origin.
Admin жёстко принимает только TEST API
`https://d5ds805l71s68liu6ge4.fovt0b64.apigw.yandexcloud.net` и не имеет PROD
fallback.

Рекомендуемый URL — `https://<selectel-https-origin>/admin-test/`. Отдельный path
не смешивает operator acceptance с публичной заглушкой `/admin/` и позволяет
переключать Admin независимо от public release. OIDC Redirect URI должен в точности
совпадать с этим URL, включая завершающий `/`.

## Требования до ручного deployment

1. На Selectel уже должен работать доверенный TLS-сертификат для выбранного origin.
   HTTP допустим в Yandex Identity Hub только для `localhost`/`127.0.0.1` и для
   Selectel не подходит.
2. OIDC client `aje25t7tefbfr547phru` должен иметь тип Single-Page Application,
   PKCE и точный redirect URI `https://<selectel-https-origin>/admin-test/`.
3. TEST API Gateway должен получить `admin_origin` с точным origin без path:
   `https://<selectel-https-origin>`. В CORS должны остаться только методы
   `GET, PATCH, OPTIONS` и headers `Authorization, Content-Type`; credentials не
   нужны, так как браузер отправляет bearer token, а не cookie.
4. До acceptance нужно подтвердить реальным входом, что access token содержит
   `aud=aje25t7tefbfr547phru`, `sub` и scopes `admin:read`/`admin:write`. Если
   Identity Hub не выдаёт эти custom scopes для текущего client, Gateway вернёт
   `403`; расширять CORS или ослаблять backend authorizer нельзя.

Текущий SPA запрашивает оба Admin scope одновременно. Это подходит для одного
полнофункционального TEST-оператора (Влада), но не создаёт отдельную read-only
роль: для разных ролей потребуется отдельное решение по выдаче scopes/claims и
повторная security review.

Gateway/CORS и OIDC redirect изменяются в Yandex Cloud отдельной ручной операцией;
Cloud Function, TEST YDB и private photo storage менять не требуется.

## Рекомендуемый Nginx block

Артефакт следует распаковать в версионированный каталог и атомарно направить
`/srv/gravitation-admin/current` на выбранный release. Минимальная схема:

```nginx
location = /admin-test {
    return 308 /admin-test/;
}

location ^~ /admin-test/ {
    alias /srv/gravitation-admin/current/;
    index index.html;

    add_header Cache-Control "no-store" always;
    add_header Content-Security-Policy "default-src 'self'; base-uri 'none'; frame-ancestors 'none'; script-src 'self'; style-src 'self'; connect-src 'self' https://auth.yandex.cloud https://d5ds805l71s68liu6ge4.fovt0b64.apigw.yandexcloud.net; img-src 'self' data:; form-action 'none'" always;
    add_header Referrer-Policy "no-referrer" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;
}
```

Перед применением нужно выполнить `nginx -t`. Если фактический discovery document
указывает token endpoint на другой HTTPS origin, его нужно добавить в `connect-src`
после ручной проверки; использовать `connect-src *` нельзя.

## Ручная проверка после разрешённого deployment

1. Проверить TLS и заголовки у `/admin-test/`; убедиться, что `/admin/` по-прежнему
   показывает закрытую заглушку, а `/apply/` — блокировку приёма.
2. В DevTools убедиться, что Admin загружает только свои static assets, discovery
   Identity Hub и TEST API; запросов к PROD или public intake нет.
3. Проверить login/callback, очистку `code` из address bar и logout.
4. Проверить `GET /admin/applications`, открытие карточки и сохранение одного
   синтетического operational-поля. Проверить ожидаемые `401` без token и `403`
   без нужного scope.
5. Проверить preflight для `Authorization` и для PATCH с `Content-Type`.
6. Не использовать реальные персональные данные. Фото в текущем Admin не
   отображаются: backend не предоставляет Admin download endpoint/presigned URL.
