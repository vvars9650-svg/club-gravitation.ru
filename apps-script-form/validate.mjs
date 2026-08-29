// CI guard for the custom Apps Script form.
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const required = ['Code.gs','Authorize.gs','E2E.gs','Index.html','Styles.html','Script.html','appsscript.json'];
const errors = [];

const read = name => fs.readFileSync(path.join(here, name), 'utf8');
const fail = message => errors.push(message);
const assert = (condition, message) => { if (!condition) fail(message); };

for (const file of required) {
  assert(fs.existsSync(path.join(here, file)), `Missing required file: ${file}`);
}

if (!errors.length) {
  let manifest;
  try {
    manifest = JSON.parse(read('appsscript.json'));
  } catch (error) {
    fail(`appsscript.json is invalid JSON: ${error.message}`);
  }

  if (manifest) {
    assert(manifest.timeZone === 'Europe/Moscow', 'Manifest timeZone must be Europe/Moscow');
    assert(manifest.runtimeVersion === 'V8', 'Manifest runtimeVersion must be V8');
    assert(manifest.webapp?.access === 'ANYONE_ANONYMOUS', 'Web app access must be ANYONE_ANONYMOUS');
    assert(manifest.webapp?.executeAs === 'USER_DEPLOYING', 'Web app must execute as USER_DEPLOYING');
    const scopes = new Set(manifest.oauthScopes || []);
    assert(scopes.has('https://www.googleapis.com/auth/spreadsheets'), 'Missing spreadsheets OAuth scope');
    assert(scopes.has('https://www.googleapis.com/auth/drive'), 'Missing Drive OAuth scope');
  }

  for (const file of ['Code.gs','Authorize.gs','E2E.gs']) {
    try {
      new vm.Script(read(file), { filename: file });
    } catch (error) {
      fail(`${file} syntax error: ${error.message}`);
    }
  }

  const index = read('Index.html');
  const client = read('Script.html');
  const clientJs = client.replace(/^\s*<script>\s*/i, '').replace(/\s*<\/script>\s*$/i, '');

  try {
    new vm.Script(clientJs, { filename: 'Script.html' });
  } catch (error) {
    fail(`Script.html JavaScript syntax error: ${error.message}`);
  }

  assert(index.includes('id="application-form"'), 'Index.html must contain #application-form');
  assert(index.includes("<?!= include_('Styles'); ?>"), 'Index.html must include Styles.html');
  assert(index.includes("<?!= include_('Script'); ?>"), 'Index.html must include Script.html');
  assert(client.includes('google.script.run'), 'Client must submit through google.script.run');
  assert(client.includes('.saveApplication(form)'), 'Client must call saveApplication(form)');
  assert(read('Code.gs').includes('function saveApplication(form)'), 'Server must expose saveApplication(form)');
  assert(read('E2E.gs').includes('function e2eVerifyCleanup(id)'), 'E2E helper must expose e2eVerifyCleanup(id)');

  const forbidden = [
    ['fetch(', 'fetch transport'],
    ['XMLHttpRequest', 'XMLHttpRequest transport'],
    ['postMessage(', 'postMessage transport'],
    ['localStorage', 'localStorage draft persistence'],
    ['sessionStorage', 'sessionStorage draft persistence']
  ];
  for (const [needle, label] of forbidden) {
    assert(!client.includes(needle), `Forbidden legacy mechanism in Script.html: ${label}`);
  }

  const lastStep = index.match(/<section class="step" data-step="5">([\s\S]*?)<\/section>/i)?.[1] || '';
  assert(Boolean(lastStep), 'Could not locate final step data-step="5"');
  assert(!lastStep.includes('data-next'), 'Final step must not contain a Next button');
  assert(lastStep.includes('type="submit"'), 'Final step must contain the submit button');

  assert(index.includes('id="photo-preview"'), 'Photo preview element is missing');
  assert(client.includes('URL.createObjectURL(file)'), 'Photo preview must use a local object URL');
}

if (errors.length) {
  console.error('Apps Script form validation failed:');
  for (const error of errors) console.error(` - ${error}`);
  process.exit(1);
}

console.log('Apps Script form validation passed.');
