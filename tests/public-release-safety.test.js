'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const {
  FRONTEND_MODES,
  PHOTO_COMPLETE_URL,
  PHOTO_INITIATE_URL,
  PUBLIC_SUBMISSION_MESSAGE,
  TEST_API_URL,
  TEST_FRONTEND_HOST,
  createMountedPhotoUploadAdapter,
  createPhotoUploadAdapter,
  createSubmitController,
  mount,
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

class FakeClassList {
  constructor(...names) {
    this.names = new Set(names);
  }

  add(name) {
    this.names.add(name);
  }

  remove(name) {
    this.names.delete(name);
  }

  contains(name) {
    return this.names.has(name);
  }

  toggle(name, force) {
    const enabled = force === undefined ? !this.names.has(name) : Boolean(force);
    if (enabled) this.names.add(name);
    else this.names.delete(name);
    return enabled;
  }
}

class FakeElement {
  constructor(...classNames) {
    this.classList = new FakeClassList(...classNames);
    this.dataset = {};
    this.style = {};
    this.hidden = false;
    this.disabled = false;
    this.required = false;
    this.checked = false;
    this.value = '';
    this.files = [];
    this.textContent = '';
    this.parentElement = {hidden: false};
    this.listeners = new Map();
  }

  addEventListener(type, listener) {
    const listeners = this.listeners.get(type) || [];
    listeners.push(listener);
    this.listeners.set(type, listeners);
  }

  async dispatch(type, event = {}) {
    for (const listener of this.listeners.get(type) || []) {
      await listener(event);
    }
  }

  setAttribute(name, value) {
    this[name] = value;
  }

  closest() {
    return this.closestElement || {hidden: false};
  }

  focus() {
    this.focused = true;
  }
}

function createPublicMountHarness() {
  const steps = Array.from({length: 5}, (_, index) =>
    new FakeElement(...(index === 0 ? ['form-step', 'is-active'] : ['form-step'])));
  const tabs = Array.from({length: 5}, (_, index) =>
    new FakeElement(...(index === 0 ? ['form-tab', 'is-active'] : ['form-tab'])));
  const controls = {};
  const control = (name) => {
    controls[name] = new FakeElement();
    return controls[name];
  };

  for (const name of [
    'policy_acknowledged', 'personal_data_consent', 'full_name', 'age', 'gender',
    'city', 'visit_krasnodar', 'phone', 'email', 'profile_or_messenger_url',
    'public_profile_url', 'photo_upload', 'photo_object_id', 'occupation',
    'life_outside_work', 'desired_connections_other', 'acquaintance_methods_other',
    'source',
  ]) control(name);

  controls.age.options = [];
  controls.age.add = (option) => controls.age.options.push(option);
  controls.city.options = [];
  controls.city.add = (option) => controls.city.options.push(option);
  const cityVisit = new FakeElement();
  controls.visit_krasnodar.closestElement = cityVisit;
  controls.desired_connections = [new FakeElement()];
  controls.acquaintance_methods = [new FakeElement()];

  const photoStatus = new FakeElement();
  const retryPhoto = new FakeElement();
  const conditionalGroups = {
    desired_connections: new FakeElement(),
    acquaintance_methods: new FakeElement(),
  };
  const conditionalWrappers = {
    desired_connections: new FakeElement(),
    acquaintance_methods: new FakeElement(),
  };
  const form = new FakeElement();
  form.hidden = true;
  form.elements = controls;
  form.querySelectorAll = (selector) => {
    if (selector === '.form-step') return steps;
    if (selector === '.is-invalid') {
      return Object.values(controls).flat()
        .filter((element) => element.classList?.contains('is-invalid'));
    }
    const checked = selector.match(/^\[name="([^"]+)"\]:checked$/u);
    if (checked) return (controls[checked[1]] || []).filter((element) => element.checked);
    return [];
  };
  form.querySelector = (selector) => {
    if (selector === '[data-photo-status]') return photoStatus;
    if (selector === '[data-photo-retry]') return retryPhoto;
    const group = selector.match(/^\[data-conditional-group="([^"]+)"\]$/u);
    if (group) return conditionalGroups[group[1]];
    const wrapper = selector.match(/^\[data-conditional="([^"]+)"\]$/u);
    if (wrapper) return conditionalWrappers[wrapper[1]];
    return null;
  };

  const back = new FakeElement();
  const next = new FakeElement();
  const status = new FakeElement();
  const review = new FakeElement();
  const submit = new FakeElement();
  const progress = new FakeElement();
  progress.closestElement = new FakeElement();
  progress.closestElement.hidden = true;
  const mobile = new FakeElement();
  mobile.hidden = true;
  const availability = new FakeElement();
  const tabsBox = new FakeElement();
  tabsBox.hidden = true;
  const newForm = new FakeElement();
  const applicationNumber = new FakeElement();
  const success = new FakeElement();
  success.querySelector = (selector) => selector === '#form-new-session'
    ? newForm
    : applicationNumber;

  const byId = new Map([
    ['#application-v5', form], ['#form-back', back], ['#form-next', next],
    ['#form-status', status], ['#review', review], ['#form-submit', submit],
    ['#form-progress-bar', progress], ['#mobile-step', mobile],
    ['#application-availability', availability], ['#form-success', success],
    ['.form-tabs', tabsBox], ['.form-progress', progress.closestElement],
  ]);
  const document = {
    querySelector: (selector) => byId.get(selector) || null,
    querySelectorAll: (selector) => selector === '.form-tab' ? tabs : [],
  };
  const networkCalls = [];
  const root = {
    document,
    location: {hostname: '135.106.219.97', search: ''},
    crypto: {},
    fetch: async (...args) => {
      networkCalls.push(args);
      return response(500);
    },
    AbortController,
  };

  return {
    root, form, steps, back, next, submit, status, photoStatus, retryPhoto,
    progressBox: progress.closestElement, mobile, availability, tabsBox,
    controls, networkCalls,
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
  assert.throws(
    () => createSubmitController({
      fetchImpl: async () => response(201),
      mode: FRONTEND_MODES.TEST_ENABLED,
    }),
    /secure_random_uuid_unavailable/u,
  );
}

function testPublicMountShowsOnlyBlockedState() {
  const harness = createPublicMountHarness();
  assert.doesNotThrow(() => mount(harness.root));
  assert.equal(harness.form.dataset.mode, FRONTEND_MODES.PUBLIC_BLOCKED);
  assert.equal(harness.availability.hidden, false);
  assert.equal(harness.availability.textContent, PUBLIC_SUBMISSION_MESSAGE);
  assert.equal(harness.form.hidden, true);
  assert.equal(harness.progressBox.hidden, true);
  assert.equal(harness.tabsBox.hidden, true);
  assert.equal(harness.mobile.hidden, true);
  assert.equal(harness.next.onclick, undefined);
  assert.equal(harness.back.onclick, undefined);
  assert.equal(harness.form.listeners.has('submit'), false);
  assert.equal(harness.controls.photo_upload.listeners.has('change'), false);
  assert.deepEqual(harness.networkCalls, []);
}

function testEnabledMountKeepsFullForm() {
  const previousOption = global.Option;
  global.Option = class Option {
    constructor(text, value) {
      this.text = text;
      this.value = value;
    }
  };

  try {
    const harness = createPublicMountHarness();
    harness.root.location = TEST_LOCATION;
    harness.root.crypto = {randomUUID: uuid};
    assert.doesNotThrow(() => mount(harness.root));
    assert.equal(harness.form.dataset.mode, FRONTEND_MODES.TEST_ENABLED);
    assert.equal(harness.availability.hidden, true);
    assert.equal(harness.form.hidden, false);
    assert.equal(harness.progressBox.hidden, false);
    assert.equal(harness.tabsBox.hidden, false);
    assert.equal(harness.mobile.hidden, false);
    assert.equal(harness.submit.disabled, false);
    assert.equal(harness.controls.photo_upload.disabled, false);
    assert.equal(typeof harness.next.onclick, 'function');
    assert.equal(typeof harness.back.onclick, 'function');
    assert.equal(harness.form.listeners.has('submit'), true);
    assert.equal(harness.controls.photo_upload.listeners.has('change'), true);

    harness.controls.policy_acknowledged.checked = true;
    harness.controls.personal_data_consent.checked = true;
    harness.next.onclick();
    assert.equal(harness.steps[0].classList.contains('is-active'), false);
    assert.equal(harness.steps[1].classList.contains('is-active'), true);
    assert.deepEqual(harness.networkCalls, []);
  } finally {
    if (previousOption === undefined) delete global.Option;
    else global.Option = previousOption;
  }
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

async function testMountedDefaultPhotoAdapterUsesResolvedMode() {
  const testCalls = [];
  const testRoot = {
    fetch: async (url, options) => {
      testCalls.push([url, options]);
      if (url === PHOTO_INITIATE_URL) {
        return response(201, {
          upload_url: 'https://storage.example.test/presigned',
          photo_object_id: 'PHOTO-0000000000000001',
          upload_method: 'PUT',
        });
      }
      if (url === 'https://storage.example.test/presigned') {
        return response(200);
      }
      return response(200, {
        photo_object_id: 'PHOTO-0000000000000001',
        lifecycle_state: 'READY',
      });
    },
  };
  const testMode = resolveFrontendMode(TEST_LOCATION);
  const testUpload = createMountedPhotoUploadAdapter(testRoot, testMode);
  const result = await testUpload({type: 'image/jpeg'}, 'test-runtime-key');

  assert.equal(result.photo_object_id, 'PHOTO-0000000000000001');
  assert.deepEqual(testCalls.map(([url]) => url), [
    PHOTO_INITIATE_URL,
    'https://storage.example.test/presigned',
    PHOTO_COMPLETE_URL,
  ]);

  const publicCalls = [];
  const publicRoot = {
    fetch: async (...args) => {
      publicCalls.push(args);
      return response(200);
    },
  };
  const publicMode = resolveFrontendMode({hostname: 'club-gravitation.ru', search: ''});
  const publicUpload = createMountedPhotoUploadAdapter(publicRoot, publicMode);
  await assert.rejects(
    () => publicUpload({type: 'image/jpeg'}, 'public-runtime-key'),
    /public_submission_blocked/,
  );
  assert.deepEqual(publicCalls, []);
}

function testPublicCopyAndNoLegacyFallback() {
  const html = fs.readFileSync('apply/index.html', 'utf8');
  const js = fs.readFileSync('assets/js/apply.js', 'utf8');
  const css = fs.readFileSync('assets/css/apply.css', 'utf8');
  const visible = html.replace(/<script[\s\S]*?<\/script>/giu, '')
    .replace(/<[^>]+>/gu, ' ')
    .replace(/\s+/gu, ' ');
  assert.match(visible, /Приём заявок временно недоступен/u);
  assert.doesNotMatch(visible, /\b(?:TEST|PROD|API|backend|endpoint|server|JWT|YDB|Object Storage|environment)\b/iu);
  assert.doesNotMatch(js, /script\.google|google apps script/iu);
  assert.doesNotMatch(js, /fallback/iu);
  assert.doesNotMatch(js, /Math\.random/u);
  assert.match(html, /id="application-availability" role="status">Приём заявок временно недоступен\. Мы откроем его после завершения подготовки\.<\/p>/u);
  assert.match(html, /class="form-progress" hidden/u);
  assert.match(html, /class="mobile-step" id="mobile-step" hidden/u);
  assert.match(html, /class="form-tabs"[^>]* hidden/u);
  assert.match(html, /<form id="application-v5" novalidate hidden>/u);
  assert.match(css, /\.page-apply \[hidden\]\{display:none!important\}/u);
}

(async () => {
  testModeMatrix();
  await testSubmitGuard();
  testPublicMountShowsOnlyBlockedState();
  testEnabledMountKeepsFullForm();
  await testPhotoGuard();
  await testMountedDefaultPhotoAdapterUsesResolvedMode();
  testPublicCopyAndNoLegacyFallback();
  console.log('Public release safety tests passed');
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
