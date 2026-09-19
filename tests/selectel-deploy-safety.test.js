'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');

const workflow = fs.readFileSync('.github/workflows/selectel-deploy.yml', 'utf8');
const releaseScript = fs.readFileSync('scripts/selectel-release.sh', 'utf8');
const combined = `${workflow}\n${releaseScript}`;

assert.match(workflow, /^\s*workflow_dispatch:/mu);
assert.doesNotMatch(workflow, /^\s*(?:push|pull_request|schedule):/mu);
assert.match(workflow, /^permissions:\s*\n\s+contents: read$/mu);
assert.match(workflow, /cancel-in-progress: false/u);
assert.match(workflow, /environment: selectel-production/u);
const externalActions = [...workflow.matchAll(/^\s*uses:\s*([^\s#]+)/gmu)]
  .map((match) => match[1]);
assert.equal(externalActions.length, 2);
for (const action of externalActions) {
  assert.match(action, /^actions\/(?:checkout|setup-node)@[a-f0-9]{40}$/u, action);
}

for (const secret of [
  'SELECTEL_SSH_PRIVATE_KEY',
  'SELECTEL_SSH_HOST',
  'SELECTEL_SSH_USER',
  'SELECTEL_SSH_KNOWN_HOSTS',
]) {
  assert.match(workflow, new RegExp(`secrets\\.${secret}\\b`, 'u'), secret);
}

assert.match(workflow, /StrictHostKeyChecking yes/u);
assert.doesNotMatch(workflow, /StrictHostKeyChecking\s+(?:no|accept-new)/iu);
assert.match(workflow, /node scripts\/build-public\.js/u);
assert.match(workflow, /node tests\/public-release-safety\.test\.js/u);
assert.match(workflow, /node tests\/public-artifact-safety\.test\.js/u);
assert.match(workflow, /tar --create --gzip[^\n]+--directory public-dist/u);
assert.match(workflow, /sha256sum/u);

assert.match(releaseScript, /BASE=\/srv\/gravitation/u);
assert.match(releaseScript, /sha256sum --check --status/u);
assert.match(releaseScript, /grep -Fq "PUBLIC_BLOCKED"/u);
assert.match(releaseScript, /RELEASES\/bootstrap-blocked/u);
assert.match(releaseScript, /Сайт временно недоступен/u);
assert.match(releaseScript, /mv -T -- "\$temporary_link" "\$CURRENT"/u);
assert.match(releaseScript, /PREVIOUS_FILE="\$SHARED\/previous-release"/u);
assert.match(releaseScript, /another release operation is in progress/u);
assert.doesNotMatch(workflow, /\bnginx\s+-[tT]\b/u);
assert.match(workflow, /curl --fail --silent --show-error --resolve "\$host:443:127\.0\.0\.1" "https:\/\/\$host\//u);
assert.doesNotMatch(workflow, /curl[^\n]*--insecure/u);

assert.doesNotMatch(combined, /\bsudo\b/u);
assert.doesNotMatch(combined, /135\.106\.219\.97/u);
assert.doesNotMatch(combined, /-----BEGIN (?:OPENSSH |RSA )?PRIVATE KEY-----/u);
assert.doesNotMatch(combined, /(?:backend\/v5\/build_deployment|api\/application\.js)/u);

console.log('Selectel deployment safety tests passed');
