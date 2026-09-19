'use strict';

const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');

const ROOT = path.resolve(__dirname, '..');
const OUTPUT = path.join(ROOT, 'public-dist');

const FILES = [
  'index.html',
  '404.html',
  'CNAME',
  'favicon.svg',
  'about/index.html',
  'events/index.html',
  'first-contact/index.html',
  'founders/index.html',
  'apply/index.html',
  'admin-prod/index.html',
  'privacy/index.html',
  'consent-pd/index.html',
  'offer/index.html',
  'terms/index.html',
  'assets/brand/logo-mark.svg',
  'assets/brand/privacy-logo-transparent.png',
  'assets/css/site.css',
  'assets/css/first-contact.css',
  'assets/css/events-hub.css',
  'assets/css/founders.css',
  'assets/css/polish.css',
  'assets/css/tz-20260831.css',
  'assets/css/story.css',
  'assets/images/story/hero-desktop.png',
  'assets/images/story/hero-mobile.png',
  'assets/images/story/about-1.png',
  'assets/images/story/about-2.png',
  'assets/images/story/about-3.png',
  'assets/images/story/about-4.png',
  'assets/images/story/about-1-mobile.png',
  'assets/images/story/about-2-mobile.png',
  'assets/images/story/about-3-mobile.png',
  'assets/images/story/about-4-mobile.png',
  'assets/images/event-01-horizontal.png',
  'assets/images/event-01-vertical.png',
  'assets/css/apply.css',
  'assets/css/admin.css',
  'assets/js/site.js',
  'assets/js/apply.js',
  'assets/js/admin-config.prod.js',
  'legal/frozen/PPD-2.2.txt',
  'legal/frozen/CONSENT-PD-2.2.txt',
  'legal/frozen/OFFER-1.0.txt',
  'legal/frozen/TERMS-1.2.txt',
];

const HEROES = {
  'hero-desktop.webp': {
    source: '.hero-build-v2/desktop',
    sha256: 'e038fff69a9557cac1222617c64950cf74a3c3b35974b93c28d482d2dc92b443',
  },
  'hero-tablet-landscape.webp': {
    source: '.hero-build-v2/tablet-landscape',
    sha256: '06cb429fbd105da7deb8feb642b0701b31bdd5ad3e044d25176097411177bac0',
  },
  'hero-tablet-portrait.webp': {
    source: '.hero-build-v2/tablet-portrait',
    sha256: 'f8bd0ace1775eca5cbb9c0a30c7f1923fefca7ec31b8963af02de01c63f27b93',
  },
  'hero-mobile.webp': {
    source: '.hero-build-v2/mobile',
    sha256: 'f1e9735129a87fc9b471207d73d996815c8a383081c85bd1f9d9fc6ace75c302',
  },
};

function copyFile(relativePath) {
  const source = path.join(ROOT, relativePath);
  const destination = path.join(OUTPUT, relativePath);
  fs.mkdirSync(path.dirname(destination), {recursive: true});
  fs.copyFileSync(source, destination);
}

function buildHero(name, config) {
  const sourceDir = path.join(ROOT, config.source);
  const parts = fs.readdirSync(sourceDir)
    .filter((file) => file.endsWith('.b64'))
    .sort();
  if (!parts.length) throw new Error(`No hero chunks found in ${config.source}`);

  const encoded = parts.map((file) => fs.readFileSync(path.join(sourceDir, file), 'utf8').trim()).join('');
  const image = Buffer.from(encoded, 'base64');
  const actualHash = crypto.createHash('sha256').update(image).digest('hex');
  if (actualHash !== config.sha256) {
    throw new Error(`Hero hash mismatch for ${name}: ${actualHash}`);
  }

  const destination = path.join(OUTPUT, 'assets/images/hero', name);
  fs.mkdirSync(path.dirname(destination), {recursive: true});
  fs.writeFileSync(destination, image);
}

function buildPublic() {
  fs.rmSync(OUTPUT, {recursive: true, force: true});
  fs.mkdirSync(OUTPUT, {recursive: true});
  FILES.forEach(copyFile);
  const mode = process.env.V5_PUBLIC_MODE === 'PROD_ENABLED' ? 'PROD_ENABLED' : 'PUBLIC_BLOCKED';
  const prodApiUrl = process.env.V5_PROD_API_URL || '';
  if (mode === 'PROD_ENABLED' && !/^https:\/\/[^\s/]+(?:\/[^\s]*)?\/applications$/u.test(prodApiUrl)) {
    throw new Error('V5_PROD_API_URL must be an HTTPS /applications endpoint when PROD_ENABLED');
  }
  fs.writeFileSync(path.join(OUTPUT, 'assets/js/public-config.js'),
    `window.__V5_PUBLIC_CONFIG__=${JSON.stringify({mode, prod_api_url: mode === 'PROD_ENABLED' ? prodApiUrl : ''})};\n`);
  for (const file of ['assets/css/site.css', 'assets/css/admin.css', 'assets/js/admin.js', 'assets/js/admin-auth.js', 'assets/js/admin-config.prod.js']) {
    const destination = path.join(OUTPUT, 'admin-prod', file);
    fs.mkdirSync(path.dirname(destination), {recursive: true});
    fs.copyFileSync(path.join(ROOT, file), destination);
  }
  copyFile('scripts/public-admin.html');
  fs.mkdirSync(path.join(OUTPUT, 'admin'), {recursive: true});
  fs.renameSync(
    path.join(OUTPUT, 'scripts/public-admin.html'),
    path.join(OUTPUT, 'admin/index.html'),
  );
  fs.rmSync(path.join(OUTPUT, 'scripts'), {recursive: true, force: true});
  Object.entries(HEROES).forEach(([name, config]) => buildHero(name, config));
  console.log(`Public artifact built at ${path.relative(ROOT, OUTPUT)}`);
}

if (require.main === module) buildPublic();

module.exports = {FILES, HEROES, OUTPUT, buildPublic};
