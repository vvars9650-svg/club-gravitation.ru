(function bootstrap(root, factory) {
  'use strict';

  const application = factory();

  if (typeof module === 'object' && module.exports) {
    module.exports = application;
  }

  if (root && root.document) {
    application.mount(root);
  }
})(typeof window === 'undefined' ? null : window, () => {
  'use strict';

  const TEST_API_URL =
    'https://d5ds805l71s68liu6ge4.fovt0b64.apigw.yandexcloud.net/applications';
  const TEST_FRONTEND_HOST =
    'gravitation-v5-test-frontend-b1g4bdjb.storage.yandexcloud.net';
  const FRONTEND_MODES = Object.freeze({
    TEST_ENABLED: 'TEST_ENABLED',
    PUBLIC_BLOCKED: 'PUBLIC_BLOCKED',
  });
  const LOCAL_HOSTNAMES = new Set(['localhost', '127.0.0.1', '::1']);
  const PUBLIC_SUBMISSION_MESSAGE =
    'Приём заявок временно недоступен. Мы откроем его после завершения подготовки.';
  const PHOTO_UPLOAD_BASE_URL = TEST_API_URL.replace(/\/applications$/u, '');
  const PHOTO_INITIATE_URL = `${PHOTO_UPLOAD_BASE_URL}/photo-uploads/initiate`;
  const PHOTO_COMPLETE_URL = `${PHOTO_UPLOAD_BASE_URL}/photo-uploads/complete`;
  const FORM_VERSION = 'FORM-2.2';
  const CONSENT_VERSION = 'CONSENT-PD-2.2';
  const POLICY_VERSION = 'PPD-2.2';
  const MULTI_FIELDS = new Set([
    'desired_connections',
    'acquaintance_methods',
  ]);
  const FORM_FIELDS = [
    'full_name',
    'age',
    'gender',
    'city',
    'visit_krasnodar',
    'phone',
    'email',
    'preferred_contact',
    'profile_or_messenger_url',
    'public_profile_url',
    'occupation',
    'life_outside_work',
    'what_interested',
    'what_participant_brings',
    'what_friends_value',
    'desired_connections',
    'desired_connections_other',
    'values_in_people',
    'barriers_to_meeting',
    'acquaintance_methods',
    'acquaintance_methods_other',
    'return_reason',
    'source',
    'photo_object_id',
  ];
  const FIELD_SET = new Set(FORM_FIELDS);
  const GENDERS = new Set(['Мужчина', 'Женщина']);
  const VISIT_OPTIONS = new Set(['Да, регулярно', 'Да, время от времени', 'Пока не уверен(а)']);
  const CONTACT_OPTIONS = new Set(['', 'по телефону', 'по email', 'через профиль или мессенджер по указанной ссылке']);
  const DESIRED_CONNECTION_OPTIONS = new Set(['Романтические отношения', 'Новые друзья', 'Близкие по духу люди', 'Партнёрство / бизнес', 'Творческие и совместные проекты', 'Новый круг общения и впечатления', 'Интересные люди без заданной цели', 'Весело провести время', 'Другое']);
  const ACQUAINTANCE_METHOD_OPTIONS = new Set(['Через общее дело или занятие', 'Через живой разговор', 'Через игру или активность', 'Когда знакомят друзья', 'Когда первый шаг делает другой человек', 'Зависит от человека и ситуации', 'Другое']);
  const SOURCE_OPTIONS = new Set(['Сайт / поиск', 'От знакомого / рекомендация', 'Мессенджер', 'Социальные сети', 'Сайт знакомств', 'Другое']);
  const CITIES = [
    'Абинск', 'Адыгейск', 'Азов', 'Аксай', 'Алупка', 'Алушта', 'Анапа',
    'Апшеронск', 'Армавир', 'Армянск', 'Астрахань', 'Ахтубинск', 'Батайск',
    'Бахчисарай', 'Белая Калитва', 'Белогорск', 'Белореченск', 'Волгоград',
    'Волгодонск', 'Волжский', 'Геленджик', 'Городовиковск', 'Горячий Ключ',
    'Гуково', 'Гулькевичи', 'Джанкой', 'Донецк', 'Дубовка', 'Евпатория',
    'Ейск', 'Жирновск', 'Зверево', 'Зерноград', 'Знаменск', 'Инкерман',
    'Калач-на-Дону', 'Каменск-Шахтинский', 'Камызяк', 'Камышин', 'Керчь',
    'Константиновск', 'Кореновск', 'Котельниково', 'Котово', 'Краснодар',
    'Красноперекопск', 'Краснослободск', 'Красный Сулин', 'Кропоткин',
    'Крымск', 'Курганинск', 'Лабинск', 'Лагань', 'Ленинск', 'Майкоп',
    'Миллерово', 'Михайловка', 'Морозовск', 'Нариманов', 'Николаевск',
    'Новоаннинский', 'Новокубанск', 'Новороссийск', 'Новочеркасск',
    'Новошахтинск', 'Палласовка', 'Петров Вал', 'Приморско-Ахтарск',
    'Пролетарск', 'Ростов-на-Дону', 'Саки', 'Сальск', 'Севастополь',
    'Семикаракорск', 'Серафимович', 'Симферополь', 'Славянск-на-Кубани',
    'Сочи', 'Старый Крым', 'Судак', 'Суровикино', 'Таганрог', 'Темрюк',
    'Тимашёвск', 'Тихорецк', 'Туапсе', 'Урюпинск', 'Усть-Лабинск',
    'Феодосия', 'Фролово', 'Хадыженск', 'Харабали', 'Цимлянск', 'Шахты',
    'Щёлкино', 'Элиста', 'Ялта',
  ];

  function normalizeHostname(hostname) {
    return typeof hostname === 'string' ? hostname.trim().toLowerCase() : '';
  }

  function resolveFrontendMode(locationLike = {}) {
    const hostname = normalizeHostname(locationLike.hostname);

    if (hostname === TEST_FRONTEND_HOST) {
      return FRONTEND_MODES.TEST_ENABLED;
    }

    if (LOCAL_HOSTNAMES.has(hostname)) {
      const search = typeof locationLike.search === 'string' ? locationLike.search : '';
      if (new URLSearchParams(search).get('test') === 'true') {
        return FRONTEND_MODES.TEST_ENABLED;
      }
    }

    return FRONTEND_MODES.PUBLIC_BLOCKED;
  }

  function assertTestEnabled(mode) {
    if (mode !== FRONTEND_MODES.TEST_ENABLED) {
      throw new Error('public_submission_blocked');
    }
  }

  function createIdempotencyKey(randomUUID) {
    if (typeof randomUUID !== 'function') {
      throw new Error('secure_random_uuid_unavailable');
    }
    const uuid = randomUUID();
    const key = `v5-${uuid}`;

    if (key.length < 16 || key.length > 128) {
      throw new Error('invalid_idempotency_key');
    }

    return key;
  }

  function buildPayload(entries) {
    const payload = {};

    for (const field of FORM_FIELDS) {
      payload[field] = MULTI_FIELDS.has(field) ? [] : '';
    }

    for (const [name, rawValue] of entries) {
      if (!FIELD_SET.has(name) && name !== 'personal_data_consent'
        && name !== 'policy_acknowledged') {
        continue;
      }

      if (name === 'personal_data_consent' || name === 'policy_acknowledged') {
        payload[name] = rawValue === true || rawValue === 'true';
      } else if (MULTI_FIELDS.has(name)) {
        payload[name].push(String(rawValue));
      } else {
        payload[name] = String(rawValue).trim();
      }
    }

    payload.personal_data_consent = payload.personal_data_consent === true;
    payload.policy_acknowledged = payload.policy_acknowledged === true;
    payload.phone = normalizeRussianPhone(payload.phone) || payload.phone;
    payload.consent_version = CONSENT_VERSION;
    payload.policy_version = POLICY_VERSION;
    payload.form_version = FORM_VERSION;

    return payload;
  }

  function validateFrontendPayload(payload) {
    if (payload.policy_acknowledged !== true) {
      return 'policy_acknowledged';
    }
    if (payload.personal_data_consent !== true) {
      return 'personal_data_consent';
    }
    if (!/^PHOTO-[A-Za-z0-9_-]{16,120}$/u.test(payload.photo_object_id || '')) {
      return 'photo_object_id';
    }

    for (const name of ['full_name', 'age', 'gender', 'city', 'phone', 'email',
      'occupation', 'life_outside_work', 'source']) {
      if (!String(payload[name] || '').trim()) {
        return name;
      }
    }

    const age = Number(payload.age);
    if (!Number.isInteger(age) || age < 25 || age > 52) {
      return 'age';
    }

    if (!normalizeRussianPhone(payload.phone)) {
      return 'phone';
    }

    if (!GENDERS.has(payload.gender)) {
      return 'gender';
    }

    if (!CONTACT_OPTIONS.has(payload.preferred_contact || '')) return 'preferred_contact';
    if (payload.city !== 'Краснодар' && !VISIT_OPTIONS.has(payload.visit_krasnodar)) {
      return 'visit_krasnodar';
    }
    if (payload.city === 'Краснодар' && payload.visit_krasnodar) return 'visit_krasnodar';

    const email = String(payload.email || '').trim();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/u.test(email)) {
      return 'email';
    }

    if (payload.city !== 'Краснодар' && !payload.visit_krasnodar) {
      return 'visit_krasnodar';
    }

    for (const field of ['profile_or_messenger_url', 'public_profile_url']) {
      const profileUrl = String(payload[field] || '').trim();
      if (!profileUrl) continue;
      try {
        const parsed = new URL(profileUrl);
        if (!/^https?:$/u.test(parsed.protocol)) {
          return field;
        }
      } catch {
        return field;
      }
    }

    const allowedMulti = {desired_connections: DESIRED_CONNECTION_OPTIONS, acquaintance_methods: ACQUAINTANCE_METHOD_OPTIONS};
    for (const field of MULTI_FIELDS) {
      if (!Array.isArray(payload[field]) || payload[field].length === 0
        || new Set(payload[field]).size !== payload[field].length
        || payload[field].some((value) => !allowedMulti[field].has(value))) return field;
    }
    if (payload.desired_connections.includes('Другое')
      && !payload.desired_connections_other) return 'desired_connections_other';
    if (!payload.desired_connections.includes('Другое')
      && payload.desired_connections_other) return 'desired_connections_other';
    if (payload.acquaintance_methods.includes('Другое')
      && !payload.acquaintance_methods_other) return 'acquaintance_methods_other';
    if (!payload.acquaintance_methods.includes('Другое')
      && payload.acquaintance_methods_other) return 'acquaintance_methods_other';
    if (!SOURCE_OPTIONS.has(payload.source)) return 'source';

    return null;
  }

  function normalizeRussianPhone(value) {
    const input = String(value || '').trim();
    if (!input || /[^\d+\s()-]/u.test(input)
      || (input.includes('+') && !/^\+\d/u.test(input))
      || (input.startsWith('+') && !input.startsWith('+7'))
      || (input.match(/\+/gu) || []).length > 1) return null;
    let digits = input.replace(/\D/gu, '');
    if (digits.length === 11) {
      if (!/^[78]/u.test(digits)) return null;
      digits = digits.slice(1);
    }
    return /^\d{10}$/u.test(digits) ? `+7${digits}` : null;
  }

  function responseResult(status, body, key) {
    if (status === 201 || (status === 200 && (body.idempotent_replay === true || body.already_registered === true))) {
      if (typeof body.application_number !== 'string'
        || !/^\d{6,}$/u.test(body.application_number)
        || Number(body.application_number) < 1) {
        return {
          state: 'recoverable_error',
          code: 'application_number_unavailable',
          key,
        };
      }
      return {
        state: 'success',
        key,
        applicationId: body.application_id || '',
        applicationNumber: body.application_number,
        alreadyRegistered: body.already_registered === true,
      };
    }

    if (status === 409) {
      return {
        state: 'recoverable_error',
        code: body.error?.code || 'idempotency_conflict',
        key,
      };
    }

    if (status === 422) {
      return {
        state: 'validation_error',
        code: body.error?.code || 'validation_error',
        key,
      };
    }

    if (status === 415) {
      return {
        state: 'recoverable_error',
        code: 'unsupported_media_type',
        key,
      };
    }

    if (status === 503) {
      return {
        state: 'recoverable_error',
        code: body.error?.code || 'temporarily_unavailable',
        key,
      };
    }

    return {
      state: 'recoverable_error',
      code: 'unexpected_response',
      key,
    };
  }

  async function parseJsonResponse(response) {
    const body = await response.json().catch(() => ({}));
    if (!response || !response.ok) {
      const error = new Error(body.error?.code || 'upload_request_failed');
      error.code = body.error?.code || 'upload_request_failed';
      error.status = response?.status;
      throw error;
    }
    return body;
  }

  function createPhotoUploadAdapter({fetchImpl, mode = FRONTEND_MODES.PUBLIC_BLOCKED}) {
    if (typeof fetchImpl !== 'function') throw new TypeError('fetchImpl_required');

    return async function uploadPhoto(file, idempotencyKey) {
      assertTestEnabled(mode);
      const headers = {
        'Content-Type': 'application/json',
        Accept: 'application/json',
        'Idempotency-Key': idempotencyKey,
      };
      const initiated = await parseJsonResponse(await fetchImpl(PHOTO_INITIATE_URL, {
        method: 'POST', headers, body: JSON.stringify({}),
      }));
      assertTestEnabled(mode);
      if (!initiated.upload_url || !initiated.photo_object_id
        || initiated.upload_method !== 'PUT') throw new Error('invalid_upload_contract');

      // The binary goes directly to Object Storage, never through the Function.
      const putResponse = await fetchImpl(initiated.upload_url, {
        method: 'PUT', headers: {'Content-Type': file.type}, body: file,
      });
      assertTestEnabled(mode);
      if (!putResponse || !putResponse.ok) throw new Error('photo_put_failed');

      return parseJsonResponse(await fetchImpl(PHOTO_COMPLETE_URL, {
        method: 'POST', headers,
        body: JSON.stringify({photo_object_id: initiated.photo_object_id}),
      }));
    };
  }

  function createMountedPhotoUploadAdapter(root, mode) {
    return root.__V5_PHOTO_UPLOAD_ADAPTER__
      || createPhotoUploadAdapter({fetchImpl: root.fetch.bind(root), mode});
  }

  function createSubmitController({
    fetchImpl,
    randomUUID,
    mode = FRONTEND_MODES.PUBLIC_BLOCKED,
    timeoutMs = 15000,
    AbortControllerImpl,
  }) {
    let idempotencyKey = mode === FRONTEND_MODES.TEST_ENABLED
      ? createIdempotencyKey(randomUUID)
      : null;
    let state = 'idle';
    let inFlight = null;

    async function performSubmit(payload) {
      state = 'submitting';
      const abortController = AbortControllerImpl
        ? new AbortControllerImpl()
        : null;
      const timeout = abortController
        ? setTimeout(() => abortController.abort(), timeoutMs)
        : null;

      try {
        const response = await fetchImpl(TEST_API_URL, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Accept: 'application/json',
            'Idempotency-Key': idempotencyKey,
          },
          body: JSON.stringify(payload),
          ...(abortController ? { signal: abortController.signal } : {}),
        });
        const body = await response.json().catch(() => ({}));
        const result = responseResult(response.status, body, idempotencyKey);
        state = result.state;
        return result;
      } catch (error) {
        state = 'recoverable_error';
        return {
          state,
          code: error?.name === 'AbortError' ? 'timeout' : 'network_error',
          uncertain: true,
          key: idempotencyKey,
        };
      } finally {
        if (timeout !== null) {
          clearTimeout(timeout);
        }
      }
    }

    function submit(payload) {
      if (mode !== FRONTEND_MODES.TEST_ENABLED) {
        state = 'blocked';
        return Promise.resolve({
          state,
          code: 'public_submission_blocked',
        });
      }

      if (inFlight) {
        return inFlight;
      }

      inFlight = performSubmit(payload).finally(() => {
        inFlight = null;
      });
      return inFlight;
    }

    function startNewSession() {
      if (mode !== FRONTEND_MODES.TEST_ENABLED || inFlight) {
        return null;
      }

      idempotencyKey = createIdempotencyKey(randomUUID);
      state = 'idle';
      return idempotencyKey;
    }

    return {
      submit,
      startNewSession,
      getIdempotencyKey: () => idempotencyKey,
      getState: () => state,
      isSubmitting: () => inFlight !== null,
    };
  }

  function mount(root) {
    const document = root.document;
    const form = document.querySelector('#application-v5');
    if (!form) {
      return;
    }

    const mode = resolveFrontendMode(root.location);
    const isTestEnabled = mode === FRONTEND_MODES.TEST_ENABLED;
    const tabsBox = document.querySelector('.form-tabs');
    const progressBox = document.querySelector('.form-progress');
    const mobile = document.querySelector('#mobile-step');
    const availability = document.querySelector('#application-availability');

    if (!isTestEnabled) {
      form.dataset.mode = FRONTEND_MODES.PUBLIC_BLOCKED;
      form.hidden = true;
      progressBox.hidden = true;
      tabsBox.hidden = true;
      mobile.hidden = true;
      availability.hidden = false;
      availability.textContent = PUBLIC_SUBMISSION_MESSAGE;
      return;
    }

    availability.hidden = true;
    form.hidden = false;
    progressBox.hidden = false;
    tabsBox.hidden = false;
    mobile.hidden = false;

    const tabs = [...document.querySelectorAll('.form-tab')];
    const progress = document.querySelector('#form-progress-bar');
    const controller = createSubmitController({
      fetchImpl: root.fetch.bind(root),
      randomUUID: typeof root.crypto?.randomUUID === 'function'
        ? root.crypto.randomUUID.bind(root.crypto)
        : undefined,
      mode,
      AbortControllerImpl: root.AbortController,
    });
    const steps = [...form.querySelectorAll('.form-step')];
    const back = document.querySelector('#form-back');
    const next = document.querySelector('#form-next');
    const status = document.querySelector('#form-status');
    const review = document.querySelector('#review');
    const submit = document.querySelector('#form-submit');
    let success = document.querySelector('#form-success');
    if (!success) {
      success = document.createElement('section');
      success.id = 'form-success';
      success.className = 'form-success';
      success.hidden = true;
      success.innerHTML = [
        '<div class="success-icon" aria-hidden="true">✓</div>',
        '<h2 data-application-number></h2>',
        '<p>Спасибо. Мы получили вашу заявку.</p>',
        '<button class="form-next" id="form-new-session" type="button">',
        'НОВАЯ АНКЕТА</button>',
      ].join('');
      form.after(success);
    }
    const newForm = success.querySelector('#form-new-session');
    const city = form.elements.city;
    const visit = form.elements.visit_krasnodar;
    const photoInput = form.elements.photo_upload;
    const photoReference = form.elements.photo_object_id;
    const photoStatus = form.querySelector('[data-photo-status]');
    const retryPhoto = form.querySelector('[data-photo-retry]');
    const uploadPhoto = createMountedPhotoUploadAdapter(root, mode);
    const names = [
      'Согласие',
      'Контакты',
      'О вас',
      'Знакомства',
      'Проверка',
    ];
    const groups = [
      ['Контакты', 1, FORM_FIELDS.slice(0, 10)],
      ['О вас', 2, FORM_FIELDS.slice(10, 15)],
      ['Знакомства', 3, FORM_FIELDS.slice(15)],
    ];
    const labels = {
      full_name: 'Имя и фамилия', age: 'Возраст', gender: 'Пол', city: 'Город',
      visit_krasnodar: 'Посещение Краснодара', phone: 'Телефон', email: 'Email',
      preferred_contact: 'Как удобнее связаться',
      profile_or_messenger_url: 'Ссылка на профиль или мессенджер',
      public_profile_url: 'Ссылка на страницу или сайт', occupation: 'Ваша сфера деятельности',
      life_outside_work: 'Чем наполнена ваша жизнь кроме работы',
      what_interested: 'Почему вам интересна «Гравитация»',
      what_participant_brings: 'Что вы привносите в компанию людей',
      what_friends_value: 'За что вас ценят друзья и знакомые',
      desired_connections: 'Какие знакомства вам интересны',
      desired_connections_other: 'Другие знакомства или формат общения',
      values_in_people: 'Что вы цените в людях',
      barriers_to_meeting: 'Что, возможно, мешает знакомиться',
      acquaintance_methods: 'Естественные способы знакомства',
      acquaintance_methods_other: 'Как ещё вам комфортнее знакомиться',
      return_reason: 'Что должно произойти, чтобы прийти снова', source: 'Откуда узнали о нас',
    };
    let current = 0;
    let maxReached = 0;

    status.setAttribute('aria-live', 'polite');

    for (let age = 25; age <= 52; age += 1) {
      form.elements.age.add(new Option(String(age), String(age)));
    }
    CITIES.forEach((name) => city.add(new Option(name, name)));

    function render() {
      const submitting = controller.isSubmitting();
      steps.forEach((step, index) => {
        step.classList.toggle('is-active', index === current);
      });
      tabs.forEach((tab, index) => {
        tab.classList.toggle('is-active', index === current);
        tab.disabled = index > maxReached || submitting;
      });
      progress.style.width = `${(100 * (current + 1)) / steps.length}%`;
      mobile.textContent = names[current];
      back.hidden = current === 0;
      next.hidden = current === steps.length - 1;
      submit.disabled = submitting || !isTestEnabled;
    }

    function syncVisit() {
      const required = city.value && city.value !== 'Краснодар';
      visit.closest('.city-visit').hidden = !required;
      visit.required = required;
      if (!required) {
        visit.value = '';
      }
    }

    function syncConditional(field) {
      const checked = [...form.querySelectorAll(`[name="${field}"]:checked`)]
        .some((control) => control.value === 'Другое');
      const wrapper = form.querySelector(`[data-conditional="${field}"]`);
      const control = form.elements[`${field}_other`];
      wrapper.hidden = !checked;
      control.required = checked;
      if (!checked) control.value = '';
    }

    function clearValidation() {
      form.querySelectorAll('.is-invalid').forEach((element) => {
        element.classList.remove('is-invalid');
      });
      status.textContent = '';
      status.dataset.state = 'idle';
    }

    function validateStep(index) {
      clearValidation();
      let firstInvalid;

      if (index === 0) {
        for (const name of ['policy_acknowledged', 'personal_data_consent']) {
          if (!form.elements[name].checked) firstInvalid ??= form.elements[name];
        }
      }

      if (index === 1) {
        for (const name of ['full_name', 'age', 'gender', 'city', 'phone', 'email']) {
          if (!String(form.elements[name].value).trim()) {
            firstInvalid ??= form.elements[name];
          }
        }

        const age = Number(form.elements.age.value);
        if (age < 25 || age > 52) {
          firstInvalid ??= form.elements.age;
        }

        if (!normalizeRussianPhone(form.elements.phone.value)) {
          firstInvalid ??= form.elements.phone;
        }

        const email = form.elements.email.value.trim();
        if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/u.test(email)) {
          firstInvalid ??= form.elements.email;
        }

        if (city.value && city.value !== 'Краснодар' && !visit.value) {
          firstInvalid ??= visit;
        }

        for (const field of ['profile_or_messenger_url', 'public_profile_url']) {
          const profileUrl = form.elements[field].value.trim();
          if (!profileUrl) continue;
          try {
            const parsed = new URL(profileUrl);
            if (!/^https?:$/u.test(parsed.protocol)) {
              throw new Error('invalid_protocol');
            }
          } catch {
            firstInvalid ??= form.elements[field];
          }
        }
        if (!photoReference.value) firstInvalid ??= photoInput;
      }

      if (index === 2) {
        for (const name of ['occupation', 'life_outside_work']) {
          if (!form.elements[name].value.trim()) firstInvalid ??= form.elements[name];
        }
      }

      if (index === 3) {
        for (const name of ['desired_connections', 'acquaintance_methods']) {
          if (!form.querySelector(`[name="${name}"]:checked`)) {
            firstInvalid ??= form.elements[name][0];
          }
          if ([...form.querySelectorAll(`[name="${name}"]:checked`)]
            .some((control) => control.value === 'Другое')
            && !form.elements[`${name}_other`].value.trim()) {
            firstInvalid ??= form.elements[`${name}_other`];
          }
        }
        if (!form.elements.source.value) firstInvalid ??= form.elements.source;
      }

      if (firstInvalid) {
        firstInvalid.classList.add('is-invalid');
        status.dataset.state = 'validation_error';
        status.textContent = 'Проверьте обязательные поля и формат данных.';
        firstInvalid.focus();
        return false;
      }

      return true;
    }

    function collect() {
      return buildPayload(new FormData(form));
    }

    function reviewAll() {
      const data = collect();
      review.replaceChildren();
      groups.forEach(([title, stepIndex, fields]) => {
        const card = document.createElement('article');
        card.className = 'review-card';
        const head = document.createElement('div');
        head.className = 'review-head';
        const strong = document.createElement('strong');
        strong.textContent = title;
        const edit = document.createElement('button');
        edit.type = 'button';
        edit.textContent = 'Изменить';
        edit.onclick = () => go(stepIndex);
        head.append(strong, edit);
        card.append(head);
        const list = document.createElement('dl');
        list.className = 'review-grid';
        fields.forEach((field) => {
          const term = document.createElement('dt');
          const description = document.createElement('dd');
          term.textContent = labels[field];
          description.textContent = Array.isArray(data[field])
            ? data[field].join(', ')
            : (data[field] || '—');
          list.append(term, description);
        });
        card.append(list);
        review.append(card);
      });
    }

    function go(index) {
      current = index;
      maxReached = Math.max(maxReached, index);
      if (index === 4) {
        reviewAll();
      }
      render();
    }

    function showForm() {
      form.hidden = false;
      progressBox.hidden = false;
      mobile.hidden = false;
      tabsBox.hidden = false;
      success.hidden = true;
    }

    function showSuccess(applicationNumber, alreadyRegistered = false) {
      form.hidden = true;
      progressBox.hidden = true;
      mobile.hidden = true;
      tabsBox.hidden = true;
      success.hidden = false;
      success.querySelector('[data-application-number]').textContent =
        alreadyRegistered
          ? `Ваша заявка уже зарегистрирована. №${applicationNumber}`
          : `Ваша заявка принята. №${applicationNumber}`;
    }

    function showResult(result) {
      status.dataset.state = result.state;

      if (result.state === 'blocked') {
        status.textContent = PUBLIC_SUBMISSION_MESSAGE;
      } else if (result.state === 'success') {
        status.textContent = '';
        showSuccess(result.applicationNumber, result.alreadyRegistered);
      } else if (result.state === 'validation_error') {
        status.textContent =
          'Не удалось принять данные. Проверьте анкету и повторите отправку.';
      } else if (result.code === 'processing_blocked') {
        status.textContent =
          'Отправка заявки сейчас недоступна. Свяжитесь с клубом удобным способом.';
      } else if (result.code === 'idempotency_conflict') {
        status.textContent =
          'Не удалось подтвердить эту отправку. Проверьте данные и повторите попытку.';
      } else if (result.code === 'unsupported_media_type') {
        status.textContent =
          'Не удалось обработать заявку. Повторите попытку позднее.';
      } else if (result.uncertain) {
        status.textContent =
          'Не удалось получить подтверждение. Повторите попытку позднее.';
      } else {
        status.textContent =
          'Приём заявок временно недоступен. Повторите попытку позднее.';
      }
    }

    city.addEventListener('change', syncVisit);
    async function uploadSelectedPhoto() {
      if (!isTestEnabled) {
        photoReference.value = '';
        photoInput.value = '';
        retryPhoto.hidden = true;
        photoStatus.textContent = PUBLIC_SUBMISSION_MESSAGE;
        return;
      }

      photoReference.value = '';
      const file = photoInput.files?.[0];
      if (!file) {
        photoStatus.textContent = '';
        retryPhoto.hidden = true;
        return;
      }
      if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)
        || file.size > 10 * 1024 * 1024) {
        photoStatus.textContent = 'Допустимы JPEG, PNG или WebP до 10 МБ.';
        retryPhoto.hidden = false;
        return;
      }
      retryPhoto.hidden = true;
      photoInput.disabled = true;
      photoStatus.textContent = 'Загрузка фотографии…';
      try {
        const result = await uploadPhoto(file, controller.getIdempotencyKey());
        if (!/^PHOTO-[A-Za-z0-9_-]{16,120}$/u.test(result?.photo_object_id || '')) {
          throw new Error('invalid_photo_reference');
        }
        photoReference.value = result.photo_object_id;
        photoStatus.textContent = 'Фотография загружена.';
      } catch {
        photoStatus.textContent = 'Не удалось загрузить фотографию. Повторите попытку.';
        retryPhoto.hidden = false;
      } finally {
        photoInput.disabled = false;
      }
    }
    photoInput.addEventListener('change', uploadSelectedPhoto);
    retryPhoto.addEventListener('click', uploadSelectedPhoto);
    for (const field of ['desired_connections', 'acquaintance_methods']) {
      form.querySelector(`[data-conditional-group="${field}"]`)
        .addEventListener('change', () => syncConditional(field));
      syncConditional(field);
    }
    syncVisit();
    next.onclick = () => {
      if (validateStep(current)) {
        go(current + 1);
      }
    };
    back.onclick = () => go(Math.max(0, current - 1));
    tabs.forEach((tab, index) => {
      tab.onclick = () => {
        if (index <= maxReached && !controller.isSubmitting()) {
          go(index);
        }
      };
    });

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (!isTestEnabled) {
        showResult({state: 'blocked'});
        return;
      }
      if (current !== steps.length - 1 || controller.isSubmitting()
        || !validateStep(0) || !validateStep(1) || !validateStep(2) || !validateStep(3)) {
        return;
      }

      const payload = collect();
      const invalidField = validateFrontendPayload(payload);
      if (invalidField) {
        const control = form.elements[invalidField];
        control?.classList.add('is-invalid');
        control?.focus();
        status.dataset.state = 'validation_error';
        status.textContent = 'Проверьте обязательные поля и формат данных.';
        return;
      }

      status.dataset.state = 'submitting';
      status.textContent = 'Отправляем заявку…';
      const request = controller.submit(payload);
      render();
      const result = await request;
      showResult(result);
      render();
    });

    form.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' && current !== steps.length - 1) event.preventDefault();
    });

    newForm.onclick = () => {
      if (!controller.startNewSession()) {
        return;
      }
      form.reset();
      photoStatus.textContent = '';
      current = 0;
      maxReached = 0;
      syncVisit();
      syncConditional('desired_connections');
      syncConditional('acquaintance_methods');
      clearValidation();
      showForm();
      render();
    };

    form.dataset.mode = FRONTEND_MODES.TEST_ENABLED;
    render();
  }

  return {
    TEST_API_URL,
    TEST_FRONTEND_HOST,
    FRONTEND_MODES,
    PUBLIC_SUBMISSION_MESSAGE,
    PHOTO_UPLOAD_BASE_URL,
    PHOTO_INITIATE_URL,
    PHOTO_COMPLETE_URL,
    FORM_FIELDS,
    FORM_VERSION,
    CONSENT_VERSION,
    POLICY_VERSION,
    buildPayload,
    createIdempotencyKey,
    createMountedPhotoUploadAdapter,
    createPhotoUploadAdapter,
    createSubmitController,
    resolveFrontendMode,
    responseResult,
    validateFrontendPayload,
    normalizeRussianPhone,
    mount,
  };
});

