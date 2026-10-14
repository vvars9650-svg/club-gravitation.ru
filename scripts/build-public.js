'use strict';

const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const {execFileSync} = require('node:child_process');

const ROOT = path.resolve(__dirname, '..');
const OUTPUT = path.join(ROOT, 'public-dist');

const FILES = [
  'assets/images/event-01-collage-desktop.png',
  'assets/images/event-01-collage-mobile.png',
  'assets/images/founders/founders-Lara.jpg',
  'assets/images/founders/founders_Vlad.jpg',

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
  'assets/images/share/event-01-first-contact-20260919.png',
  'assets/css/apply.css',
  'assets/css/admin.css',
  'assets/js/site.js',
  'assets/js/apply.js',
  'assets/js/admin-config.prod.js',
  'legal/frozen/PPD-2.3.txt',
  'legal/frozen/CONSENT-PD-2.3.txt',
  'legal/frozen/FORM-2.3.txt',
  'legal/frozen/PPD-2.2.txt',
  'legal/frozen/CONSENT-PD-2.2.txt',
  'legal/frozen/FORM-2.2.txt',
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


function canonicalLegalHash(source) {
  const lines = source.replace(/^\uFEFF/u, '').replace(/\r\n?/gu, '\n').normalize('NFC').split('\n').map(line => line.replace(/[ \t]+$/u, ''));
  while (lines.length && lines.at(-1) === '') lines.pop();
  return crypto.createHash('sha256').update(lines.join('\n') + '\n').digest('hex');
}

function verifyApprovedLegal() {
  const approval = JSON.parse(fs.readFileSync(path.join(ROOT, 'legal/approval-2.3.json'), 'utf8'));
  if (approval.approved_source_head !== 'a0a6c6f6199b9d29096a9fa6d935724b4d24860b' || approval.approved_at !== '14.10.2026') throw new Error('legal_approval_required');
  for (const version of ['PPD-2.3','CONSENT-PD-2.3','FORM-2.3']) {
    const document = approval.documents[version];
    if (document.path !== `legal/frozen/${version}.txt` || canonicalLegalHash(fs.readFileSync(path.join(ROOT, document.path), 'utf8')) !== document.canonical_sha256) throw new Error('frozen_legal_hash_mismatch');
  }
  if (approval.documents['CONSENT-PD-2.3'].canonical_sha256 !== require('../assets/js/apply').CONSENT_TEXT_HASH) throw new Error('frontend_legal_hash_mismatch');
  return approval;
}

function buildPublic() {
  const approval = verifyApprovedLegal();
  const sourceHead = execFileSync('git', ['rev-parse','HEAD'], {cwd:ROOT, encoding:'utf8'}).trim();
  const mode = process.env.V5_PUBLIC_MODE === 'PROD_ENABLED' ? 'PROD_ENABLED' : 'PUBLIC_BLOCKED';
  const prodApiUrl = process.env.V5_PROD_API_URL || '';
  if (mode === 'PROD_ENABLED' && prodApiUrl !== require('../assets/js/apply').PROD_API_URL) {
    throw new Error('V5_PROD_API_URL must equal the approved PROD /applications endpoint');
  }
  fs.rmSync(OUTPUT, {recursive: true, force: true});
  fs.mkdirSync(OUTPUT, {recursive: true});
  FILES.forEach(copyFile);
  fs.writeFileSync(path.join(OUTPUT, 'assets/js/public-config.js'),
    `window.__V5_PUBLIC_CONFIG__=${JSON.stringify({mode, prod_api_url: mode === 'PROD_ENABLED' ? prodApiUrl : '', source_head:sourceHead, form_version:'FORM-2.3', policy_version:'PPD-2.3', consent_version:'CONSENT-PD-2.3', consent_text_hash:approval.documents['CONSENT-PD-2.3'].canonical_sha256, short_form_legal_approved:true})};\n`);
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

module.exports = {FILES, HEROES, OUTPUT, buildPublic, canonicalLegalHash, verifyApprovedLegal};
