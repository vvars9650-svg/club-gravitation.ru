'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const {
  TEST_API_URL,
  FRONTEND_MODES,
  PHOTO_INITIATE_URL,
  PHOTO_COMPLETE_URL,
  FORM_FIELDS,
  buildPayload,
  createPhotoUploadAdapter,
  createSubmitController,
  responseResult,
  validateFrontendPayload,
  normalizeRussianPhone,
} = require('../assets/js/apply');
const apiContract = require('../api/application');


const EXPECTED_TEST_API =
  'https://d5ds805l71s68liu6ge4.fovt0b64.apigw.yandexcloud.net/applications';

function uuidSequence() {
  let value = 0;
  return () => {
    value += 1;
    return `00000000-0000-4000-8000-${String(value).padStart(12, '0')}`;
  };
}

function response(status, body = {}) {
  return {
    status,
    ok: status >= 200 && status < 300,
    json: async () => body,
  };
}

async function testPhotoUploadAdapterFlow() {
  const calls = [];
  const file = {type: 'image/jpeg', bytes: 'SYNTHETIC-BINARY'};
  const adapter = createPhotoUploadAdapter({
    mode: FRONTEND_MODES.TEST_ENABLED,
    fetchImpl: async (url, options) => {
      calls.push([url, options]);
      if (url === PHOTO_INITIATE_URL) {
        return response(201, {
          photo_object_id: 'PHOTO-0000000000000001',
          upload_url: 'https://storage.example.test/presigned',
          upload_method: 'PUT',
        });
      }
      if (url === PHOTO_COMPLETE_URL) {
        return response(200, {
          photo_object_id: 'PHOTO-0000000000000001',
          lifecycle_state: 'READY',
        });
      }
      return response(200);
    },
  });
  const result = await adapter(file, 'v5-upload-key');

  assert.equal(result.photo_object_id, 'PHOTO-0000000000000001');
  assert.deepEqual(calls.map(([url]) => url), [
    PHOTO_INITIATE_URL,
    'https://storage.example.test/presigned',
    PHOTO_COMPLETE_URL,
  ]);
  assert.equal(calls[0][1].headers['Idempotency-Key'], 'v5-upload-key');
  assert.equal(calls[1][1].method, 'PUT');
  assert.equal(calls[1][1].body, file);
  assert.equal(calls[2][1].headers['Idempotency-Key'], 'v5-upload-key');
  assert.deepEqual(JSON.parse(calls[2][1].body), {
    photo_object_id: 'PHOTO-0000000000000001',
  });
  assert.equal(JSON.stringify(calls[0][1].body).includes('base64'), false);
  assert.equal(JSON.stringify(calls[2][1].body).includes('SYNTHETIC-BINARY'), false);

  const applicationCalls = [];
  const submit = controller(async (url, options) => {
    applicationCalls.push([url, options]);
    return response(201, {application_id: 'APP-1', application_number: '000001'});
  }, () => '00000000-0000-4000-8000-000000000042');
  const sharedKey = submit.getIdempotencyKey();
  await adapter(file, sharedKey);
  await submit.submit(validPayload());
  assert.equal(applicationCalls[0][1].headers['Idempotency-Key'], sharedKey);
  assert.equal(calls.at(-1)[1].headers['Idempotency-Key'], sharedKey);
}

async function testPhotoUploadFailureAndRetry() {
  let attempt = 0;
  const calls = [];
  const adapter = createPhotoUploadAdapter({
    mode: FRONTEND_MODES.TEST_ENABLED,
    fetchImpl: async (url, options) => {
      calls.push([url, options]);
      if (url === PHOTO_INITIATE_URL) {
        return response(201, {
          photo_object_id: `PHOTO-000000000000000${attempt + 1}`,
          upload_url: 'https://storage.example.test/presigned',
          upload_method: 'PUT',
        });
      }
      if (url.startsWith('https://storage')) {
        attempt += 1;
        if (attempt === 1) return response(503);
        return response(200);
      }
      return response(200, {
        photo_object_id: 'PHOTO-0000000000000002', lifecycle_state: 'READY',
      });
    },
  });
  await assert.rejects(() => adapter({type: 'image/png'}, 'same-key'), /photo_put_failed/);
  const result = await adapter({type: 'image/png'}, 'same-key');
  assert.equal(result.photo_object_id, 'PHOTO-0000000000000002');
  assert.deepEqual(calls.filter(([url]) => url === PHOTO_INITIATE_URL)
    .map(([, options]) => options.headers['Idempotency-Key']), ['same-key', 'same-key']);
  assert.equal(calls.filter(([url]) => url === PHOTO_COMPLETE_URL).length, 1);
}

function controller(fetchImpl, randomUUID = uuidSequence(), options = {}) {
  return createSubmitController({
    fetchImpl,
    randomUUID,
    mode: FRONTEND_MODES.TEST_ENABLED,
    ...options,
  });
}

function validPayload() {
  return buildPayload([
    ['full_name', 'TEST User'],
    ['age', '30'],
    ['gender', 'Мужчина'],
    ['city', 'Краснодар'],
    ['phone', '8 (999) 000-00-00'],
    ['email', 'user@example.com'],
    ['occupation', 'Инженер'],
    ['life_outside_work', 'Спорт'],
    ['desired_connections', 'Новые друзья'],
    ['desired_connections', 'Близкие по духу люди'],
    ['acquaintance_methods', 'Через живой разговор'],
    ['source', 'Сайт / поиск'],
    ['photo_object_id', 'PHOTO-0000000000000001'],
    ['policy_acknowledged', 'true'],
    ['personal_data_consent', 'true'],
  ]);
}

async function testRequestContractAndPayload() {
  const calls = [];
  const submit = controller(async (...args) => {
    calls.push(args);
    return response(201, {application_id: 'APP-1', application_number: '000001'});
  });
  const payload = validPayload();
  const result = await submit.submit(payload);

  assert.equal(result.state, 'success');
  assert.equal(calls.length, 1);
  assert.equal(calls[0][0], EXPECTED_TEST_API);
  assert.equal(TEST_API_URL, EXPECTED_TEST_API);
  assert.equal(calls[0][1].method, 'POST');
  assert.equal(calls[0][1].headers['Content-Type'], 'application/json');
  assert.equal(
    calls[0][1].headers['Idempotency-Key'],
    submit.getIdempotencyKey(),
  );
  assert.ok(submit.getIdempotencyKey().length >= 16);
  assert.ok(submit.getIdempotencyKey().length <= 128);
  assert.deepEqual(JSON.parse(calls[0][1].body), payload);

  assert.deepEqual(payload.desired_connections, [
    'Новые друзья',
    'Близкие по духу люди',
  ]);
  assert.deepEqual(payload.acquaintance_methods, ['Через живой разговор']);
  assert.equal(payload.phone, '+79990000000');
  assert.equal(payload.policy_acknowledged, true);
  assert.equal(payload.personal_data_consent, true);
  assert.equal(payload.consent_version, 'CONSENT-PD-2.2');
  assert.equal(payload.policy_version, 'PPD-2.2');
  assert.equal(payload.form_version, 'FORM-2.2');
  assert.equal(payload.photo_object_id, 'PHOTO-0000000000000001');
  assert.equal(Object.hasOwn(payload, 'photo_upload'), false);
  assert.equal(FORM_FIELDS.length, 24);
  assert.deepEqual(FORM_FIELDS, apiContract.FORM_FIELDS);
  assert.equal(FORM_FIELDS.includes('comfortable_price'), false);

  for (const serverOwned of [
    'environment',
    'granted_at',
    'consent_text_hash',
    'participant_id',
    'application_id',
  ]) {
    assert.equal(Object.hasOwn(payload, serverOwned), false, serverOwned);
  }
}

function testFrontendValidation() {
  const payload = validPayload();
  assert.equal(validateFrontendPayload(payload), null);
  assert.equal(
    validateFrontendPayload({...payload, policy_acknowledged: false}),
    'policy_acknowledged',
  );
  assert.equal(
    validateFrontendPayload({...payload, personal_data_consent: false}),
    'personal_data_consent',
  );
  assert.equal(validateFrontendPayload({...payload, photo_object_id: ''}), 'photo_object_id');
  assert.equal(validateFrontendPayload({...payload, photo_object_id: 'PHOTO-short'}), 'photo_object_id');
  assert.equal(validateFrontendPayload({...payload, age: '24'}), 'age');
  assert.equal(validateFrontendPayload({...payload, age: '53'}), 'age');
  assert.equal(validateFrontendPayload({...payload, phone: '123'}), 'phone');
  assert.equal(normalizeRussianPhone('9990000000'), '+79990000000');
  assert.equal(normalizeRussianPhone('7 999 000-00-00'), '+79990000000');
  assert.equal(normalizeRussianPhone('8 (999) 000-00-00'), '+79990000000');
  assert.equal(normalizeRussianPhone('9abcdefghij'), null);
  assert.equal(validateFrontendPayload({...payload, email: 'bad'}), 'email');
  assert.equal(
    validateFrontendPayload({...payload, public_profile_url: 'ftp://example.test'}),
    'public_profile_url',
  );
  assert.equal(
    validateFrontendPayload({
      ...payload,
      city: 'Сочи',
      visit_krasnodar: '',
    }),
    'visit_krasnodar',
  );
  assert.equal(
    validateFrontendPayload({...payload, desired_connections: ['Другое']}),
    'desired_connections_other',
  );
  assert.equal(
    validateFrontendPayload({...payload, acquaintance_methods: ['Другое']}),
    'acquaintance_methods_other',
  );
  assert.equal(
    validateFrontendPayload({...payload, acquaintance_methods: ['unknown']}),
    'acquaintance_methods',
  );
}

async function testIdempotencyLifecycleAndErrors() {
  const statuses = [
    () => {
      throw new TypeError('network failed');
    },
    () => response(503, {error: {code: 'temporarily_unavailable'}}),
    () => response(409, {error: {code: 'idempotency_conflict'}}),
  ];
  const keys = [];
  const submit = controller(async (_url, options) => {
    keys.push(options.headers['Idempotency-Key']);
    return statuses.shift()();
  });
  const originalKey = submit.getIdempotencyKey();

  let result = await submit.submit(validPayload());
  assert.equal(result.state, 'recoverable_error');
  assert.equal(result.code, 'network_error');
  assert.equal(result.uncertain, true);

  result = await submit.submit(validPayload());
  assert.equal(result.state, 'recoverable_error');
  assert.equal(result.code, 'temporarily_unavailable');

  result = await submit.submit(validPayload());
  assert.equal(result.state, 'recoverable_error');
  assert.equal(result.code, 'idempotency_conflict');
  assert.deepEqual(keys, [originalKey, originalKey, originalKey]);

  assert.equal(submit.getIdempotencyKey(), originalKey);
}

async function testTimeoutKeepsKey() {
  const submit = controller(
    (_url, options) => new Promise((_resolve, reject) => {
      options.signal.addEventListener('abort', () => {
        const error = new Error('timed out');
        error.name = 'AbortError';
        reject(error);
      });
    }),
    uuidSequence(),
    {timeoutMs: 1, AbortControllerImpl: AbortController},
  );
  const originalKey = submit.getIdempotencyKey();
  const result = await submit.submit(validPayload());

  assert.equal(result.state, 'recoverable_error');
  assert.equal(result.code, 'timeout');
  assert.equal(result.uncertain, true);
  assert.equal(submit.getIdempotencyKey(), originalKey);
}

async function testNewSessionGetsNewKeyAfterSuccess() {
  const submit = controller(async () => response(201, {
    application_id: 'APP-COMPLETE',
    application_number: '000001',
  }));
  const originalKey = submit.getIdempotencyKey();

  const result = await submit.submit(validPayload());
  assert.equal(result.state, 'success');

  const nextKey = submit.startNewSession();
  assert.notEqual(nextKey, originalKey);
  assert.equal(submit.getState(), 'idle');
}

async function testResponseStates() {
  const cases = [
    [201, {application_id: 'APP-NEW', application_number: '000001'}, 'success'],
    [200, {application_id: 'APP-NEW', application_number: '000001', idempotent_replay: true}, 'success'],
    [422, {error: {code: 'invalid_age'}}, 'validation_error'],
    [415, {error: {code: 'unsupported_media_type'}}, 'recoverable_error'],
    [503, {error: {code: 'ydb_unavailable'}}, 'recoverable_error'],
    [409, {error: {code: 'processing_blocked'}}, 'recoverable_error'],
  ];

  for (const [status, body, expectedState] of cases) {
    const submit = controller(async () => response(status, body));
    const result = await submit.submit(validPayload());
    assert.equal(result.state, expectedState, String(status));
  }
}

async function testDoubleSubmitPrevention() {
  let resolveFetch;
  let calls = 0;
  const fetchResult = new Promise((resolve) => {
    resolveFetch = resolve;
  });
  const submit = controller(() => {
    calls += 1;
    return fetchResult;
  });

  const first = submit.submit(validPayload());
  const second = submit.submit(validPayload());

  assert.strictEqual(first, second);
  assert.equal(calls, 1);
  assert.equal(submit.getState(), 'submitting');
  resolveFetch(response(201, {application_id: 'APP-ONCE', application_number: '000001'}));
  const [firstResult, secondResult] = await Promise.all([first, second]);
  assert.deepEqual(firstResult, secondResult);
  assert.equal(firstResult.state, 'success');
}

function testForbiddenFrontendIntegrations() {
  const frontend = [
    fs.readFileSync('apply/index.html', 'utf8'),
    fs.readFileSync('assets/js/apply.js', 'utf8'),
  ].join('\n').toLowerCase();

  for (const forbidden of [
    'no-cors',
    'script.google',
    'google apps script',
    'contact_consent',
    'photo_data',
    'base64',
    'relationship_context',
    'rules_consent',
    'submission_mode',
    'legal_versions',
    'v3',
  ]) {
    assert.equal(frontend.includes(forbidden), false, forbidden);
  }

  assert.match(frontend, /заявка №\$\{applicationnumber\}/u);
  assert.equal(frontend.includes('data-application-id'), false);
}

function testApplicationNumberResponseContract() {
  assert.deepEqual(
    responseResult(201, {application_id: 'APP-1', application_number: '000001'}, 'key').applicationNumber,
    '000001',
  );
  assert.equal(
    responseResult(201, {application_id: 'APP-1'}, 'key').code,
    'application_number_unavailable',
  );
  assert.equal(
    responseResult(200, {application_id: 'APP-1', application_number: '000001', idempotent_replay: true}, 'key').applicationNumber,
    '000001',
  );
}

(async () => {
  await testPhotoUploadAdapterFlow();
  await testPhotoUploadFailureAndRetry();
  await testRequestContractAndPayload();
  testFrontendValidation();
  await testIdempotencyLifecycleAndErrors();
  await testTimeoutKeepsKey();
  await testNewSessionGetsNewKeyAfterSuccess();
  await testResponseStates();
  await testDoubleSubmitPrevention();
  testForbiddenFrontendIntegrations();
  testApplicationNumberResponseContract();
  console.log('V5 frontend submit tests passed');
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});

