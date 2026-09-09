const assert = require('node:assert/strict');
const fs = require('node:fs');
const admin = require('../assets/js/admin.js');
const auth = require('../assets/js/admin-auth.js');

const storage = () => { const values = new Map(); return {getItem: (key) => values.get(key) || null, setItem: (key, value) => values.set(key, value), removeItem: (key) => values.delete(key), values}; };
const config = {environment: 'TEST', issuer: 'https://issuer.test', client_id: 'v5-test-spa', redirect_uri: 'https://admin.test/admin/', scopes: ['openid', 'email', 'profile']};
const cryptoImpl = {getRandomValues: (bytes) => { bytes.fill(7); return bytes; }, subtle: crypto.subtle};

assert.equal(admin.STATUSES.length, 9);
assert.deepEqual(admin.OPERATIONAL, ['lifecycle_status', 'owner', 'priority', 'next_action', 'next_contact_at', 'decision', 'internal_comment']);
assert.ok(admin.FIELDS.includes('occupation'));
assert.ok(admin.FIELDS.includes('unacceptable_behavior'));
assert.match(fs.readFileSync(require.resolve('../assets/js/admin.js'), 'utf8'), /Загрузка заявок/);
assert.match(fs.readFileSync(require.resolve('../assets/js/admin.js'), 'utf8'), /Заявок по выбранным условиям нет/);
assert.match(fs.readFileSync(require.resolve('../assets/js/admin.js'), 'utf8'), /Не удалось загрузить заявки/);
assert.ok(!fs.readFileSync(require.resolve('../assets/js/admin-auth.js'), 'utf8').includes('localStorage'));

(async () => {
  assert.equal(await auth.pkceChallenge('dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk', crypto), 'E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM');
  const transient = storage(); let assigned = '';
  const oidc = auth.createAuthClient({config, cryptoImpl, storage: transient, location: {href: 'https://admin.test/admin/', assign: (url) => { assigned = url; }}, fetchImpl: async (url) => ({ok: true, json: async () => url.includes('openid') ? {authorization_endpoint: 'https://issuer.test/authorize', token_endpoint: 'https://issuer.test/token'} : {access_token: 'access.token.value'}})});
  await oidc.signIn();
  assert.match(assigned, /code_challenge_method=S256/);
  assert.ok(transient.values.has(auth.TRANSIENT_KEY));
  await assert.rejects(() => oidc.consumeCallback('https://admin.test/admin/?code=abc&state=wrong'), /oidc_state_mismatch/);
  const callbackState = JSON.parse(transient.getItem(auth.TRANSIENT_KEY)).state;
  const session = await oidc.consumeCallback(`https://admin.test/admin/?code=abc&state=${callbackState}`);
  assert.equal(session.accessToken, 'access.token.value');
  assert.equal(oidc.getAccessToken(), 'access.token.value');
  assert.equal(transient.getItem(auth.TRANSIENT_KEY), null);
  const calls = []; let authFailure = '';
  const client = admin.createClient({__V5_ADMIN_API_URL__: 'https://admin.test/'}, async (url, options = {}) => { calls.push({url, options}); return {status: 200, ok: true, json: async () => ({environment: 'TEST', applications: []})}; }, () => 'jwt-token', (reason) => { authFailure = reason; });
  await client.list({q: 'тест', sort: 'submitted_at', order: 'desc'});
  await client.save('PT-1', {owner: 'Влад'});
  assert.match(calls[0].url, /\/admin\/applications\?/);
  assert.equal(calls[0].options.headers.Authorization, 'Bearer jwt-token');
  assert.equal(calls[0].options.credentials, undefined);
  assert.equal(calls[1].options.headers['Content-Type'], 'application/json');
  await assert.rejects(() => admin.createClient({__V5_ADMIN_API_URL__: 'https://admin.test'}, async () => ({ok: true}), () => null).list({}), /authentication_required/);
  const expired = admin.createClient({__V5_ADMIN_API_URL__: 'https://admin.test'}, async () => ({status: 401, ok: false}), () => 'jwt', (reason) => { authFailure = reason; });
  await assert.rejects(() => expired.save('PT-1', {}), /session_expired/);
  assert.equal(authFailure, 'expired');
  const denied = admin.createClient({__V5_ADMIN_API_URL__: 'https://admin.test'}, async () => ({status: 403, ok: false}), () => 'jwt');
  await assert.rejects(() => denied.list({}), /access_denied/);
  console.log('admin auth/ui contract: ok');
})();
