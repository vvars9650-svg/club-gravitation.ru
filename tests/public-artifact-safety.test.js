'use strict';

const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const {OUTPUT, buildPublic} = require('../scripts/build-public');

function filesUnder(directory) {
  const result = [];
  function visit(current) {
    for (const entry of fs.readdirSync(current, {withFileTypes: true})) {
      const full = path.join(current, entry.name);
      if (entry.isDirectory()) visit(full);
      else result.push(path.relative(directory, full).replaceAll(path.sep, '/'));
    }
  }
  visit(directory);
  return result.sort();
}

function artifactPath(relativePath) {
  return path.join(OUTPUT, relativePath);
}

function read(relativePath) {
  return fs.readFileSync(artifactPath(relativePath), 'utf8');
}

function routeToFile(urlPath) {
  const clean = urlPath.split(/[?#]/u)[0];
  if (clean === '/') return 'index.html';
  if (clean.endsWith('/')) return `${clean.slice(1)}index.html`;
  return clean.slice(1);
}

function assertLocalReferences() {
  for (const html of filesUnder(OUTPUT).filter((file) => file.endsWith('.html'))) {
    const source = read(html);
    const references = [...source.matchAll(/(?:href|src)=["']([^"']+)["']/giu),
      ...source.matchAll(/fetch\(["']([^"']+)["']/giu)];
    for (const [, reference] of references) {
      if (!reference.startsWith('/') || reference.startsWith('//')) continue;
      if (reference.endsWith('/')) continue;
      assert.equal(fs.existsSync(artifactPath(routeToFile(reference))), true,
        `${html} references missing ${reference}`);
    }
  }
}

async function assertNetworkGuards() {
  const apply = require('../public-dist/assets/js/apply.js');
  const calls = [];
  const response = await apply.createSubmitController({
    mode: apply.FRONTEND_MODES.PUBLIC_BLOCKED,
    fetchImpl: async (...args) => { calls.push(args); return {ok: true, status: 201, json: async () => ({})}; },
    randomUUID: () => '00000000-0000-4000-8000-000000000001',
  }).submit({full_name: 'blocked'});
  assert.equal(response.state, 'blocked');
  assert.deepEqual(calls, []);

  await assert.rejects(
    () => apply.createPhotoUploadAdapter({
      mode: apply.FRONTEND_MODES.PUBLIC_BLOCKED,
      fetchImpl: async (...args) => { calls.push(args); return {ok: true, status: 201}; },
    })({type: 'image/jpeg'}, 'public-key'),
    /public_submission_blocked/u,
  );
  assert.deepEqual(calls, []);
}

async function main() {
  buildPublic();
  const actual = filesUnder(OUTPUT);
  const forbiddenPath = /^(?:backend|tests|\.github|\.codex|\.hero-build-v2|__pycache__)\//u;
  assert.equal(actual.some((file) => forbiddenPath.test(file)), false);
  assert.equal(actual.some((file) => /(?:^|\/).*\.py$/u.test(file)), false);
  assert.equal(actual.some((file) => /(?:deployment|ADMIN-AUTH|V5-CONTRACT|README|\.test\.)/iu.test(file)), false);
  assert.equal(actual.some((file) => file.endsWith('.md') || file.endsWith('.yaml') || file.endsWith('.yml') || file.endsWith('.json')), false);

  for (const route of [
    'index.html', '404.html', 'CNAME', 'about/index.html', 'events/index.html',
    'founders/index.html', 'apply/index.html', 'privacy/index.html',
    'consent-pd/index.html', 'offer/index.html', 'terms/index.html', 'admin/index.html',
  ]) assert.equal(fs.existsSync(artifactPath(route)), true, route);

  const admin = read('admin/index.html');
  assert.doesNotMatch(admin, /<script\b/iu);
  assert.doesNotMatch(admin, /admin-config\.test\.js|admin-auth\.js|admin\.js/iu);
  assert.doesNotMatch(admin, /TEST|PROD|API|JWT|OIDC|token|scope|backend|YDB|endpoint|localhost|redirect URI|database/iu);
  assert.doesNotMatch(admin, /d5ds805l71s68liu6ge4|127\.0\.0\.1:8000\/admin\//u);

  const completeArtifact = filesUnder(OUTPUT).map((file) => read(file).toLowerCase()).join('\n');
  assert.equal(completeArtifact.includes('127.0.0.1:8000/admin/'), false);
  assert.equal(completeArtifact.includes('admin-config.test.js'), false);
  assert.equal(completeArtifact.includes('-----begin private key-----'), false);
  assert.equal(completeArtifact.includes('client_secret'), false);
  assertLocalReferences();

  const expectedHashes = {
    'hero-desktop.webp': 'e038fff69a9557cac1222617c64950cf74a3c3b35974b93c28d482d2dc92b443',
    'hero-tablet-landscape.webp': '06cb429fbd105da7deb8feb642b0701b31bdd5ad3e044d25176097411177bac0',
    'hero-tablet-portrait.webp': 'f8bd0ace1775eca5cbb9c0a30c7f1923fefca7ec31b8963af02de01c63f27b93',
    'hero-mobile.webp': 'f1e9735129a87fc9b471207d73d996815c8a383081c85bd1f9d9fc6ace75c302',
  };
  for (const [name, expected] of Object.entries(expectedHashes)) {
    const actualHash = crypto.createHash('sha256').update(fs.readFileSync(artifactPath(`assets/images/hero/${name}`))).digest('hex');
    assert.equal(actualHash, expected, name);
  }
  assert.match(read('privacy/index.html'), /PPD','2\.2/u);
  assert.match(read('consent-pd/index.html'), /CONSENT','PD','2\.2/u);
  await assertNetworkGuards();
  console.log(`Public artifact safety: ${actual.length} files, all checks passed`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
