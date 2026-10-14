const assert=require('node:assert/strict');
const fs=require('node:fs');
const {buildPublic,verifyApprovedLegal,canonicalLegalHash}=require('../scripts/build-public');
const apply=require('../assets/js/apply');
const approval=verifyApprovedLegal();
assert.equal(apply.CONSENT_VERSION,'CONSENT-PD-2.3');assert.equal(apply.POLICY_VERSION,'PPD-2.3');
for(const entry of Object.values(approval.documents))assert.equal(canonicalLegalHash(fs.readFileSync(entry.path,'utf8')),entry.canonical_sha256);
const previous={mode:process.env.V5_PUBLIC_MODE,url:process.env.V5_PROD_API_URL};
try {
 process.env.V5_PUBLIC_MODE='PROD_ENABLED';process.env.V5_PROD_API_URL=apply.TEST_API_URL;
 assert.throws(buildPublic,/V5_PROD_API_URL/);
 process.env.V5_PROD_API_URL=apply.PROD_API_URL;buildPublic();
 const config=fs.readFileSync('public-dist/assets/js/public-config.js','utf8');
 const runtime=JSON.parse(config.match(/=(.*);/)[1]);
 assert.equal(runtime.consent_text_hash,apply.CONSENT_TEXT_HASH);
 assert.equal(apply.resolveFrontendMode({hostname:'club-gravitation.ru'},runtime),'PROD_ENABLED');
 assert.equal(apply.resolveFrontendMode({hostname:'club-gravitation.ru'},{...runtime,consent_version:'CONSENT-PD-2.2'}),'PUBLIC_BLOCKED');
 assert.equal(apply.resolveFrontendMode({hostname:'club-gravitation.ru'},{...runtime,consent_text_hash:'invalid'}),'PUBLIC_BLOCKED');
} finally {
 if(previous.mode===undefined)delete process.env.V5_PUBLIC_MODE;else process.env.V5_PUBLIC_MODE=previous.mode;
 if(previous.url===undefined)delete process.env.V5_PROD_API_URL;else process.env.V5_PROD_API_URL=previous.url;
 buildPublic();
}
console.log('Legal 2.3 activation and exact PROD runtime tests passed');
