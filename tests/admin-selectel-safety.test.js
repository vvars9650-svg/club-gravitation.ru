'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {OUTPUT: PUBLIC_OUTPUT, buildPublic} = require('../scripts/build-public');
const {
  ADMIN_PATH,
  OUTPUT,
  SELECTEL_TEST_ORIGIN,
  TEST_ADMIN_API_URL,
  buildAdminSelectel,
  normalizeOrigin,
} = require('../scripts/build-admin-selectel');

function filesUnder(directory) {
  const files = [];
  function visit(current) {
    for (const entry of fs.readdirSync(current, {withFileTypes: true})) {
      const full = path.join(current, entry.name);
      if (entry.isDirectory()) visit(full);
      else files.push(path.relative(directory, full).replaceAll(path.sep, '/'));
    }
  }
  visit(directory);
  return files.sort();
}

function read(directory, relativePath) {
  return fs.readFileSync(path.join(directory, relativePath), 'utf8');
}

assert.throws(() => normalizeOrigin(), /required/u);
assert.throws(() => buildAdminSelectel({origin: ''}), /required/u);
for (const origin of [
  'http://selectel.example.test',
  'https://selectel.example.test/admin-test/',
  'https://user:password@selectel.example.test',
  'https://selectel.example.test?environment=TEST',
]) assert.throws(() => normalizeOrigin(origin), /exact HTTPS origin/u);
assert.throws(() => normalizeOrigin('https://selectel.example.test'), /must equal/u);

const origin = SELECTEL_TEST_ORIGIN;
const result = buildAdminSelectel({origin});
assert.equal(result.redirectUri, `${origin}${ADMIN_PATH}`);
assert.deepEqual(filesUnder(OUTPUT), [
  'assets/css/admin.css',
  'assets/css/site.css',
  'assets/js/admin-auth.js',
  'assets/js/admin-config.js',
  'assets/js/admin.js',
  'index.html',
]);

const adminHtml = read(OUTPUT, 'index.html');
const adminConfig = read(OUTPUT, 'assets/js/admin-config.js');
const adminBundle = filesUnder(OUTPUT).map((file) => read(OUTPUT, file)).join('\n');
assert.match(adminHtml, /href="assets\/css\/site\.css"/u);
assert.match(adminHtml, /src="assets\/js\/admin-config\.js"/u);
assert.doesNotMatch(adminHtml, /admin-config\.test\.js|(?:href|src)="\/assets\//u);
assert.match(adminConfig, new RegExp(TEST_ADMIN_API_URL.replaceAll('.', '\\.')));
assert.match(adminConfig, /environment: 'TEST'/u);
assert.match(adminConfig, /redirect_uri: 'https:\/\/test\.club-gravitation\.ru\/admin-test\/'/u);
assert.match(adminConfig, /scopes: Object\.freeze\(\['openid', 'email', 'profile'\]\)/u);
assert.doesNotMatch(adminBundle, /admin:read|admin:write/u);
assert.doesNotMatch(adminBundle, /\bPROD\b|client_secret|refresh_token|-----BEGIN (?:OPENSSH |RSA )?PRIVATE KEY-----/iu);
assert.doesNotMatch(adminBundle, /\/photo-uploads\//u);
assert.doesNotMatch(adminBundle, /apigw\.yandexcloud\.net\/applications/u);
assert.match(read(OUTPUT, 'assets/js/admin.js'), /\/admin\/applications/u);

for (const file of filesUnder(OUTPUT)) {
  const source = read(OUTPUT, file);
  if (source.includes(TEST_ADMIN_API_URL)) {
    assert.ok(['assets/js/admin-config.js', 'assets/js/admin.js'].includes(file), file);
  }
}

buildPublic();
const publicFiles = filesUnder(PUBLIC_OUTPUT);
const publicAdmin = read(PUBLIC_OUTPUT, 'admin/index.html');
const publicBundle = publicFiles.map((file) => read(PUBLIC_OUTPUT, file)).join('\n');
assert.match(publicAdmin, /Раздел закрыт/u);
assert.doesNotMatch(publicAdmin, /<script\b|admin-config(?:\.test)?\.js|src=["'][^"']*admin(?:-auth)?\.js/iu);
assert.equal(publicFiles.some((file) => /admin-config|admin-auth/iu.test(file)), false);
assert.doesNotMatch(publicBundle, /__V5_ADMIN_CONFIG__|admin:read|admin:write/iu);
assert.match(read(PUBLIC_OUTPUT, 'assets/js/apply.js'), /PUBLIC_BLOCKED/u);
assert.match(read(PUBLIC_OUTPUT, 'apply/index.html'), /Приём заявок временно недоступен/u);

console.log('Selectel TEST Admin artifact safety checks passed');
