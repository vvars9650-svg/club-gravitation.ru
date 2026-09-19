'use strict';

const fs = require('node:fs');
const path = require('node:path');

const ROOT = path.resolve(__dirname, '..');
const OUTPUT = path.join(ROOT, 'admin-prod-dist');
const ADMIN_PATH = '/admin-prod/';
const PROD_ORIGIN = 'https://club-gravitation.ru';
const PROD_API_URL = 'https://d5dsivdtqjog5vgvn111.7qsg961h.apigw.yandexcloud.net';
const FILES = ['assets/css/site.css', 'assets/css/admin.css', 'assets/js/admin-auth.js', 'assets/js/admin.js'];

function buildAdminProd() {
  fs.rmSync(OUTPUT, {recursive: true, force: true});
  fs.mkdirSync(OUTPUT, {recursive: true});
  for (const file of FILES) {
    const destination = path.join(OUTPUT, file);
    fs.mkdirSync(path.dirname(destination), {recursive: true});
    fs.copyFileSync(path.join(ROOT, file), destination);
  }
  const html = fs.readFileSync(path.join(ROOT, 'admin/index.html'), 'utf8')
    .replaceAll('href="/assets/', 'href="assets/')
    .replace('src="/assets/js/admin-config.test.js"', 'src="assets/js/admin-config.prod.js"')
    .replaceAll('src="/assets/js/', 'src="assets/js/');
  fs.writeFileSync(path.join(OUTPUT, 'index.html'), html);
  fs.copyFileSync(path.join(ROOT, 'assets/js/admin-config.prod.js'), path.join(OUTPUT, 'assets/js/admin-config.prod.js'));
  console.log(`PROD Admin artifact built at ${path.relative(ROOT, OUTPUT)} for ${PROD_ORIGIN}${ADMIN_PATH} → ${PROD_API_URL}`);
  return {output: OUTPUT, origin: PROD_ORIGIN, redirectUri: `${PROD_ORIGIN}${ADMIN_PATH}`};
}

if (require.main === module) buildAdminProd();
module.exports = {OUTPUT, buildAdminProd};
