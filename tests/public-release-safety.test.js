'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const {
  FRONTEND_MODES,
  PHOTO_INITIATE_URL,
  TEST_API_URL,
  TEST_FRONTEND_HOST,
  createPhotoUploadAdapter,
  createSubmitController,
  resolveFrontendMode,
} = require('../assets/js/apply');

const TEST_LOCATION = {hostname: TEST_FRONTEND_HOST, search: ''};

function uuid() {
  return '00000000-0000-4000-8000-000000000001';
}

function response(status, body = {}) {
  return {
    status,
    ok: status >= 200 && status < 300,
    json: async () => body,
  };
}

function assertBlocked(locationLike) {
  assert.equal(resolveFrontendMode(locationLike), FRONTEND_MODES.PUBLIC_BLOCKED);
}

function testModeMatrix() {
  assert.equal(resolveFrontendMode(TEST_LOCATION), FRONTEND_MODES.TEST_ENABLED);
  assertBlocked({hostname: 'club-gravitation.ru', search: ''});
  assertBlocked({hostname: 'www.club-gravitation.ru', search: ''});
  assertBlocked({hostname: 'example.com', search: ''});
  assertBlocked({hostname: 'example.com', search: '?test=true'});
  assertBlocked({hostname: 'localhost', search: ''});
  assert.equal(
    resolveFrontendMode({hostname: 'localhost', search: '?test=true'}),
    FRONTEND_MODES.TEST_ENABLED,
  );
  assert.equal(
    resolveFrontendMode({hostname: '127.0.0.1', search: '?test=true'}),
    FRONTEND_MODES.TEST_ENABLED,
  );
}

async function testSubmitGuard() {
  const publicCalls = [];
  const publicSubmit = createSubmitController({
    fetchImpl: async (...args) => {
      publicCalls.push(args);
      return response(201);
    },
    randomUUID: uuid,
    mode: FRONTEND_MODES.PUBLIC_BLOCKED,
  });
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

function testPublicCopyAndNoLegacyFallback() {
  const html = fs.readFileSync('apply/index.html', 'utf8');
  const js = fs.readFileSync('assets/js/apply.js', 'utf8');
  const visible = html.replace(/<script[\s\S]*?<\/script>/giu, '')
    .replace(/<[^>]+>/gu, ' ')
    .replace(/\s+/gu, ' ');
  assert.match(visible, /Приём заявок временно недоступен/u);
  assert.doesNotMatch(visible, /\b(?:TEST|PROD|API|backend|endpoint|server|JWT|YDB|Object Storage|environment)\b/iu);
  assert.doesNotMatch(js, /script\.google|google apps script/iu);
  assert.doesNotMatch(js, /fallback/iu);
}

(async () => {
  testModeMatrix();
  await testSubmitGuard();
  await testPhotoGuard();
  testPublicCopyAndNoLegacyFallback();
  console.log('Public release safety tests passed');
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
