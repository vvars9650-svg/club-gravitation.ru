'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const {
  TEST_API_URL,
  FORM_FIELDS,
  buildPayload,
  createSubmitController,
  validateFrontendPayload,
} = require('../assets/js/apply');


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
    json: async () => body,
  };
}

function controller(fetchImpl, randomUUID = uuidSequence(), options = {}) {
  return createSubmitController({fetchImpl, randomUUID, ...options});
}

function validPayload() {
  return buildPayload([
    ['full_name', 'TEST User'],
    ['age', '30'],
    ['gender', 'Мужчина'],
    ['city', 'Краснодар'],
    ['phone', '+79990000000'],
    ['desired_connections', 'Новые друзья'],
    ['desired_connections', 'Близкие по духу люди'],
    ['convenient_days', 'Суббота'],
    ['personal_data_consent', 'true'],
  ]);
}

async function testRequestContractAndPayload() {
  const calls = [];
  const submit = controller(async (...args) => {
    calls.push(args);
    return response(201, {application_id: 'APP-1'});
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
  assert.deepEqual(payload.convenient_days, ['Суббота']);
  assert.equal(payload.personal_data_consent, true);
  assert.equal(payload.consent_version, 'CONSENT-PD-2.0');
  assert.equal(payload.policy_version, 'PPD-2.0');
  assert.equal(payload.form_version, 'FORM-2.1');
  assert.equal(FORM_FIELDS.length, 26);
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
    validateFrontendPayload({...payload, personal_data_consent: false}),
    'personal_data_consent',
  );
  assert.equal(validateFrontendPayload({...payload, age: '24'}), 'age');
  assert.equal(validateFrontendPayload({...payload, age: '53'}), 'age');
  assert.equal(validateFrontendPayload({...payload, phone: '123'}), 'phone');
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
    [201, {application_id: 'APP-NEW'}, 'success'],
    [200, {application_id: 'APP-NEW', idempotent_replay: true}, 'success'],
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
  resolveFetch(response(201, {application_id: 'APP-ONCE'}));
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
    'photo',
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
}

(async () => {
  await testRequestContractAndPayload();
  testFrontendValidation();
  await testIdempotencyLifecycleAndErrors();
  await testTimeoutKeepsKey();
  await testNewSessionGetsNewKeyAfterSuccess();
  await testResponseStates();
  await testDoubleSubmitPrevention();
  testForbiddenFrontendIntegrations();
  console.log('V5 frontend submit tests passed');
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});

