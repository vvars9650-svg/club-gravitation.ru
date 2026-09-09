/* Public TEST-only OIDC SPA configuration. No token or client secret belongs here. */
window.__V5_ADMIN_AUTH_CONFIG__ = {
  environment: 'TEST',
  issuer: 'https://auth.yandex.cloud',
  openid_configuration_url: 'https://auth.yandex.cloud/.well-known/openid-configuration',
  client_id: 'aje25t7tefbfr547phru',
  redirect_uri: 'http://127.0.0.1:8000/admin/',
  scopes: ['openid', 'email', 'profile']
};
