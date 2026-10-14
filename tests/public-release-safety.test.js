const assert = require('node:assert/strict');
const fs = require('node:fs');
const {TEST_API_URL, PROD_API_URL, PHOTO_INITIATE_URL, FRONTEND_MODES, PUBLIC_SUBMISSION_MESSAGE, createSubmitController, createPhotoUploadAdapter, resolveFrontendMode} = require('../assets/js/apply');
const uuid = () => '00000000-0000-4000-8000-000000000001';
const response = (status, body={}) => ({status, ok:status<400, json:async()=>body});
const PUBLIC_LOCATIONS = [{hostname:'club-gravitation.ru'}, {hostname:'www.club-gravitation.ru'}, {hostname:'vvars9650-svg.github.io'}, {hostname:'example.test'}];
async function testSubmitGuard() {
  const publicCalls = [];
  const publicSubmit = createSubmitController({
    fetchImpl: async (...args) => {
      publicCalls.push(args);
      return response(201);
    },
    mode: FRONTEND_MODES.PUBLIC_BLOCKED,
  });
  assert.equal(publicSubmit.getIdempotencyKey(), null);
  assert.equal(publicSubmit.startNewSession(), null);
  const blocked = await publicSubmit.submit({full_name: 'blocked'});
  assert.equal(blocked.state, 'blocked');
  assert.equal(blocked.code, 'public_submission_blocked');
  assert.deepEqual(publicCalls, []);

  const testCalls = [];
  const testSubmit = createSubmitController({
    fetchImpl: async (...args) => {
      testCalls.push(args);
      return response(201, {application_id: 'APP-1', application_number: '000001'});
    },
    randomUUID: uuid,
    mode: FRONTEND_MODES.TEST_ENABLED,
  });
  await testSubmit.submit({full_name: 'synthetic'});
  assert.equal(testCalls.length, 1);
  assert.equal(testCalls[0][0], TEST_API_URL);
  assert.match(testSubmit.getIdempotencyKey(), /^v5-[0-9a-f-]{36}$/u);
  const prodCalls = [];
  const prodSubmit = createSubmitController({
    fetchImpl: async (...args) => {
      prodCalls.push(args);
      return response(201, {application_id: 'APP-PROD', application_number: '000002'});
    },
    randomUUID: uuid,
    mode: FRONTEND_MODES.PROD_ENABLED,
    apiUrl: PROD_API_URL,
  });
  await prodSubmit.submit({full_name: 'synthetic'});
  assert.equal(prodCalls[0][0], PROD_API_URL);
  assert.throws(
    () => createSubmitController({
      fetchImpl: async () => response(201),
      mode: FRONTEND_MODES.TEST_ENABLED,
    }),
    /secure_random_uuid_unavailable/u,
  );
}

async function testPhotoGuard() {
  const publicCalls = [];
  const publicUpload = createPhotoUploadAdapter({
    fetchImpl: async (...args) => {
      publicCalls.push(args);
      return response(201, {
        upload_url: 'https://storage.example.test/presigned',
        photo_object_id: 'PHOTO-0000000000000001',
        upload_method: 'PUT',
      });
    },
    mode: FRONTEND_MODES.PUBLIC_BLOCKED,
  });
  await assert.rejects(
    () => publicUpload({type: 'image/jpeg'}, 'public-key'),
    /public_submission_blocked/,
  );
  assert.deepEqual(publicCalls, []);

  const defaultCalls = [];
  const defaultUpload = createPhotoUploadAdapter({
    fetchImpl: async (...args) => {
      defaultCalls.push(args);
      return response(201);
    },
  });
  await assert.rejects(
    () => defaultUpload({type: 'image/jpeg'}, 'default-key'),
    /public_submission_blocked/,
  );
  assert.deepEqual(defaultCalls, []);
  assert.equal(PHOTO_INITIATE_URL.includes(TEST_API_URL.replace('/applications', '')), true);
}


(async () => {
  for (const location of PUBLIC_LOCATIONS) {
    assert.equal(resolveFrontendMode(location), FRONTEND_MODES.PUBLIC_BLOCKED);
    assert.equal(resolveFrontendMode(location, {mode:'PROD_ENABLED', prod_api_url:PROD_API_URL}), FRONTEND_MODES.PUBLIC_BLOCKED);
  }
  assert.equal(resolveFrontendMode({hostname:'localhost', search:''}), FRONTEND_MODES.PUBLIC_BLOCKED);
  assert.equal(resolveFrontendMode({hostname:'localhost', search:'?test=true'}), FRONTEND_MODES.TEST_ENABLED);
  await testSubmitGuard(); await testPhotoGuard();
  assert.match(fs.readFileSync('apply/index.html','utf8'), /<form id="application-v5" novalidate hidden>/);
  assert.match(fs.readFileSync('assets/js/apply.js','utf8'), /if \(!enabled\) \{ form.hidden = true; return; \}/);
  console.log('Public release safety tests passed');
})().catch(e => {console.error(e); process.exitCode=1;});
