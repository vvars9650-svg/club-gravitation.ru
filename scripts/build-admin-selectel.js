'use strict';

const fs = require('node:fs');
const path = require('node:path');

const ROOT = path.resolve(__dirname, '..');
const OUTPUT = path.join(ROOT, 'admin-selectel-dist');
const ADMIN_PATH = '/admin-test/';
const TEST_ADMIN_API_URL = 'https://d5ds805l71s68liu6ge4.fovt0b64.apigw.yandexcloud.net';
const TEST_ISSUER = 'https://auth.yandex.cloud';
const TEST_CLIENT_ID = 'aje25t7tefbfr547phru';
const SELECTEL_TEST_ORIGIN = 'https://test.club-gravitation.ru';
const FILES = [
  'assets/css/site.css',
  'assets/css/admin.css',
  'assets/js/admin-auth.js',
  'assets/js/admin.js',
];

function normalizeOrigin(value) {
  if (!value) throw new Error('ADMIN_SELECTEL_ORIGIN is required');
  let origin;
  try { origin = new URL(value); } catch { throw new Error('ADMIN_SELECTEL_ORIGIN must be an absolute HTTPS origin'); }
  if (origin.protocol !== 'https:' || origin.username || origin.password
    || origin.pathname !== '/' || origin.search || origin.hash || origin.origin !== value.replace(/\/$/u, '')) {
    throw new Error('ADMIN_SELECTEL_ORIGIN must be an exact HTTPS origin without path, query, or credentials');
  }
  if (origin.origin !== SELECTEL_TEST_ORIGIN) {
    throw new Error(`ADMIN_SELECTEL_ORIGIN must equal ${SELECTEL_TEST_ORIGIN}`);
  }
  return origin.origin;
}

function copyFile(relativePath) {
  const source = path.join(ROOT, relativePath);
  const destination = path.join(OUTPUT, relativePath);
  fs.mkdirSync(path.dirname(destination), {recursive: true});
  fs.copyFileSync(source, destination);
}

function buildAdminSelectel({origin = process.env.ADMIN_SELECTEL_ORIGIN} = {}) {
  const adminOrigin = normalizeOrigin(origin);
  const redirectUri = `${adminOrigin}${ADMIN_PATH}`;
  fs.rmSync(OUTPUT, {recursive: true, force: true});
  fs.mkdirSync(OUTPUT, {recursive: true});
  FILES.forEach(copyFile);

  const html = fs.readFileSync(path.join(ROOT, 'admin/index.html'), 'utf8')
    .replaceAll('href="/assets/', 'href="assets/')
    .replace('src="/assets/js/admin-config.test.js"', 'src="assets/js/admin-config.js"')
    .replaceAll('src="/assets/js/', 'src="assets/js/');
  fs.writeFileSync(path.join(OUTPUT, 'index.html'), html);

  const config = `/* Generated TEST-only Selectel Admin configuration. Public values only. */
window.__V5_ADMIN_CONFIG__ = Object.freeze({
  environment: 'TEST',
  api_url: '${TEST_ADMIN_API_URL}',
  auth: Object.freeze({
    environment: 'TEST',
    issuer: '${TEST_ISSUER}',
    openid_configuration_url: '${TEST_ISSUER}/.well-known/openid-configuration',
    client_id: '${TEST_CLIENT_ID}',
    redirect_uri: '${redirectUri}',
    scopes: Object.freeze(['openid', 'email', 'profile'])
  })
});
`;
  fs.writeFileSync(path.join(OUTPUT, 'assets/js/admin-config.js'), config);
  console.log(`Selectel TEST Admin artifact built at ${path.relative(ROOT, OUTPUT)} for ${redirectUri}`);
  return {output: OUTPUT, origin: adminOrigin, redirectUri};
}

if (require.main === module) buildAdminSelectel();

module.exports = {
  ADMIN_PATH,
  FILES,
  OUTPUT,
  SELECTEL_TEST_ORIGIN,
  TEST_ADMIN_API_URL,
  TEST_CLIENT_ID,
  TEST_ISSUER,
  buildAdminSelectel,
  normalizeOrigin,
};
