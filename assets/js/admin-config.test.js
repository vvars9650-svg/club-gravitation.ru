/* Public TEST-only SPA configuration. No token or client secret belongs here. */
window.__V5_ADMIN_CONFIG__ = Object.freeze({
  environment: 'TEST',
  api_url: 'https://d5ds805l71s68liu6ge4.fovt0b64.apigw.yandexcloud.net',
  auth: Object.freeze({
    environment: 'TEST',
    issuer: 'https://auth.yandex.cloud',
    openid_configuration_url: 'https://auth.yandex.cloud/.well-known/openid-configuration',
    client_id: 'aje25t7tefbfr547phru',
    redirect_uri: 'http://127.0.0.1:8000/admin/',
    scopes: Object.freeze(['openid', 'email', 'profile', 'admin:read', 'admin:write'])
  })
});
