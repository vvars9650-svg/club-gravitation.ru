// Read-only verification: build locally; optionally compare HTTPS and SSH TEST.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {execFileSync} from 'node:child_process';
const root = path.dirname(fileURLToPath(import.meta.url));
const expected = JSON.parse(fs.readFileSync(path.join(root, 'accepted-manifest.json')));
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
for (const [file, hash] of Object.entries(expected.sources)) {
  if (sha(fs.readFileSync(path.join(root, file))) !== hash) throw Error(`Source mismatch: ${file}`);
}
execFileSync(process.execPath, [path.join(root, 'build.mjs')], {stdio:'inherit'});
execFileSync(process.execPath, [path.join(root, 'prepare-test-release.mjs'),
  '--base', expected.base, '--release', expected.release,
  '--output', 'public-dist/verified-release'], {stdio:'inherit'});
const built = fs.readFileSync(path.join(root, 'public-dist/verified-release', expected.path));
if (built.length !== expected.fileBytes || sha(built) !== expected.fileSha256) throw Error('Accepted artifact mismatch');
const result = {sourceChecks:true, build:true, fileSha256:sha(built), fileBytes:built.length};
if (process.argv.includes('--live')) {
  const response = await fetch(expected.url);
  const bytes = Buffer.from(await response.arrayBuffer());
  if (response.status !== 200 || sha(bytes) !== expected.fileSha256) throw Error('HTTPS TEST mismatch');
  const status = JSON.parse(execFileSync('ssh', ['selectel-gravitation',
    'sudo -n /usr/local/sbin/gravitation-test-release status'], {encoding:'utf8'}));
  if (status.current !== expected.release) throw Error('SSH TEST release mismatch');
  const command = "python3 -c 'import hashlib,json; from pathlib import Path; p=Path(\"/srv/gravitation-test/current/card/lara/index.html\"); print(json.dumps({\"sha256\":hashlib.sha256(p.read_bytes()).hexdigest(),\"bytes\":p.stat().st_size}))'";
  const server = JSON.parse(execFileSync('ssh', ['selectel-gravitation', command], {encoding:'utf8'}));
  if (server.sha256 !== expected.fileSha256 || server.bytes !== expected.fileBytes) throw Error('SSH artifact mismatch');
  const configResponse = await fetch('https://test.club-gravitation.ru/assets/js/public-config.js');
  const config = await configResponse.text();
  if (!configResponse.ok || !config.includes('"mode":"PUBLIC_BLOCKED"') || !config.includes('"prod_api_url":""')) throw Error('TEST gate mismatch');
  Object.assign(result, {https:true, ssh:true, publicBlocked:true, current:status.current, previous:status.previous});
}
console.log(JSON.stringify(result, null, 2));
