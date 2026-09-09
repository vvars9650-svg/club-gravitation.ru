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
  const FORM_VERSION = 'FORM-2.0';
  const CONSENT_VERSION = 'CONSENT-PD-2.0';
  const POLICY_VERSION = 'PPD-2.0';
  const MULTI_FIELDS = new Set([
    'desired_connections',
    'convenient_days',
  ]);
  const FORM_FIELDS = [
    'full_name',
    'age',
    'gender',
    'city',
    'visit_krasnodar',
    'phone',
    'telegram',
    'email',
    'preferred_contact',
    'public_profile_url',
    'occupation',
    'life_outside_work',
    'interests',
    'what_interested',
    'event_expectations',
    'desired_connections',
    'values_in_people',
    'barriers_to_meeting',
    'social_comfort',
    'initiative',
    'acquaintance_scenario',
    'successful_evening',
    'return_reason',
    'unacceptable_behavior',
    'convenient_days',
    'comfortable_price',
    'source',
  ];
  const FIELD_SET = new Set(FORM_FIELDS);
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

  function createIdempotencyKey(randomUUID) {
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
      if (!FIELD_SET.has(name) && name !== 'personal_data_consent') {
        continue;
      }

      if (name === 'personal_data_consent') {
        payload.personal_data_consent = rawValue === true || rawValue === 'true';
      } else if (MULTI_FIELDS.has(name)) {
        payload[name].push(String(rawValue));
      } else {
        payload[name] = String(rawValue).trim();
      }
    }

    payload.personal_data_consent = payload.personal_data_consent === true;
    payload.consent_version = CONSENT_VERSION;
    payload.policy_version = POLICY_VERSION;
    payload.form_version = FORM_VERSION;

    return payload;
  }

  function validateFrontendPayload(payload) {
    if (payload.personal_data_consent !== true) {
      return 'personal_data_consent';
    }

    for (const name of ['full_name', 'age', 'gender', 'city', 'phone']) {
      if (!String(payload[name] || '').trim()) {
        return name;
      }
    }

    const age = Number(payload.age);
    if (!Number.isInteger(age) || age < 25 || age > 52) {
      return 'age';
    }

    const phoneDigits = String(payload.phone).replace(/\D/gu, '');
    if (!/^\d{10}$/u.test(phoneDigits) && !/^[78]\d{10}$/u.test(phoneDigits)) {
      return 'phone';
    }

    const email = String(payload.email || '').trim();
    if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/u.test(email)) {
      return 'email';
    }

    if (payload.city !== 'Краснодар' && !payload.visit_krasnodar) {
      return 'visit_krasnodar';
    }

    const profileUrl = String(payload.public_profile_url || '').trim();
    if (profileUrl) {
      try {
        const parsed = new URL(profileUrl);
        if (!/^https?:$/u.test(parsed.protocol)) {
          return 'public_profile_url';
        }
      } catch {
        return 'public_profile_url';
      }
    }

    return null;
  }

  function responseResult(status, body, key) {
    if (status === 201 || (status === 200 && body.idempotent_replay === true)) {
      return {
        state: 'success',
        key,
        applicationId: body.application_id || '',
      };
    }

    if (status === 409) {
      return {
        state: 'recoverable_error',
        code: 'idempotency_conflict',
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

  function createSubmitController({
    fetchImpl,
    randomUUID,
    timeoutMs = 15000,
    AbortControllerImpl,
  }) {
    let idempotencyKey = createIdempotencyKey(randomUUID);
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
      if (inFlight) {
        return inFlight;
      }

      inFlight = performSubmit(payload).finally(() => {
        inFlight = null;
      });
      return inFlight;
    }

    function startNewSession() {
      if (inFlight) {
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

    const controller = createSubmitController({
      fetchImpl: root.fetch.bind(root),
      randomUUID: root.crypto.randomUUID.bind(root.crypto),
      AbortControllerImpl: root.AbortController,
    });
    const steps = [...form.querySelectorAll('.form-step')];
    const tabs = [...document.querySelectorAll('.form-tab')];
    const back = document.querySelector('#form-back');
    const next = document.querySelector('#form-next');
    const status = document.querySelector('#form-status');
    const review = document.querySelector('#review');
    const submit = document.querySelector('#form-submit');
    const progress = document.querySelector('#form-progress-bar');
    const progressBox = progress.closest('.form-progress');
    const mobile = document.querySelector('#mobile-step');
    let success = document.querySelector('#form-success');
    if (!success) {
      success = document.createElement('section');
      success.id = 'form-success';
      success.className = 'form-success';
      success.hidden = true;
      success.innerHTML = [
        '<div class="success-icon" aria-hidden="true">✓</div>',
        '<h2>TEST-заявка принята</h2>',
        '<p>Спасибо. Мы сохранили вашу тестовую заявку.</p>',
        '<small>ИДЕНТИФИКАТОР ЗАЯВКИ</small>',
        '<strong data-application-id></strong>',
        '<button class="form-next" id="form-new-session" type="button">',
        'НОВАЯ TEST-АНКЕТА</button>',
      ].join('');
      form.after(success);
    }
    const newForm = success.querySelector('#form-new-session');
    const city = form.elements.city;
    const visit = form.elements.visit_krasnodar;
    const names = [
      'Согласие',
      'Контакты',
      'О вас',
      'Знакомства',
      'Формат',
      'Проверка',
    ];
    const groups = [
      ['Контакты', 1, FORM_FIELDS.slice(0, 10)],
      ['О вас', 2, FORM_FIELDS.slice(10, 15)],
      ['Знакомства', 3, FORM_FIELDS.slice(15, 21)],
      ['Формат', 4, FORM_FIELDS.slice(21)],
    ];
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
      submit.disabled = submitting;
    }

    function syncVisit() {
      const required = city.value && city.value !== 'Краснодар';
      visit.closest('.city-visit').hidden = !required;
      visit.required = required;
      if (!required) {
        visit.value = '';
      }
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

      if (index === 0 && !form.elements.personal_data_consent.checked) {
        firstInvalid = form.elements.personal_data_consent;
      }

      if (index === 1) {
        for (const name of ['full_name', 'age', 'gender', 'city', 'phone']) {
          if (!String(form.elements[name].value).trim()) {
            firstInvalid ??= form.elements[name];
          }
        }

        const age = Number(form.elements.age.value);
        if (age < 25 || age > 52) {
          firstInvalid ??= form.elements.age;
        }

        const phoneDigits = form.elements.phone.value.replace(/\D/gu, '');
        const phoneValid = /^\d{10}$/u.test(phoneDigits)
          || /^[78]\d{10}$/u.test(phoneDigits);
        if (!phoneValid) {
          firstInvalid ??= form.elements.phone;
        }

        const email = form.elements.email.value.trim();
        if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/u.test(email)) {
          firstInvalid ??= form.elements.email;
        }

        if (city.value && city.value !== 'Краснодар' && !visit.value) {
          firstInvalid ??= visit;
        }

        const profileUrl = form.elements.public_profile_url.value.trim();
        if (profileUrl) {
          try {
            const parsed = new URL(profileUrl);
            if (!/^https?:$/u.test(parsed.protocol)) {
              throw new Error('invalid_protocol');
            }
          } catch {
            firstInvalid ??= form.elements.public_profile_url;
          }
        }
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
          term.textContent = field;
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
      if (index === 5) {
        reviewAll();
      }
      render();
    }

    function showForm() {
      form.hidden = false;
      progressBox.hidden = false;
      mobile.hidden = false;
      tabs[0].parentElement.hidden = false;
      success.hidden = true;
    }

    function showSuccess(applicationId) {
      form.hidden = true;
      progressBox.hidden = true;
      mobile.hidden = true;
      tabs[0].parentElement.hidden = true;
      success.hidden = false;
      success.querySelector('[data-application-id]').textContent =
        applicationId || 'TEST-заявка';
    }

    function showResult(result) {
      status.dataset.state = result.state;

      if (result.state === 'success') {
        status.textContent = '';
        showSuccess(result.applicationId);
      } else if (result.state === 'validation_error') {
        status.textContent =
          'Backend отклонил данные. Проверьте анкету и повторите отправку.';
      } else if (result.code === 'idempotency_conflict') {
        status.textContent =
          'Не удалось подтвердить эту отправку. Проверьте данные и повторите попытку.';
      } else if (result.code === 'unsupported_media_type') {
        status.textContent =
          'Техническая ошибка запроса. Повторите попытку позднее.';
      } else if (result.uncertain) {
        status.textContent =
          'Ответ сервера не получен. Заявка могла быть принята; повторная попытка безопасна.';
      } else {
        status.textContent =
          'TEST-сервис временно недоступен. Повторите попытку позднее.';
      }
    }

    city.addEventListener('change', syncVisit);
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
      if (controller.isSubmitting() || !validateStep(0) || !validateStep(1)) {
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
      status.textContent = 'Отправляем TEST-заявку…';
      const request = controller.submit(payload);
      render();
      const result = await request;
      showResult(result);
      render();
    });

    newForm.onclick = () => {
      if (!controller.startNewSession()) {
        return;
      }
      form.reset();
      current = 0;
      maxReached = 0;
      syncVisit();
      clearValidation();
      showForm();
      render();
    };

    render();
  }

  return {
    TEST_API_URL,
    FORM_FIELDS,
    FORM_VERSION,
    CONSENT_VERSION,
    POLICY_VERSION,
    buildPayload,
    createIdempotencyKey,
    createSubmitController,
    responseResult,
    validateFrontendPayload,
    mount,
  };
});
