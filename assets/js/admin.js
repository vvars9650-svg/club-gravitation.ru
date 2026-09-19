(function bootstrap(root, factory) {
  const admin = factory();
  if (typeof module === 'object' && module.exports) module.exports = admin;
  if (root && root.document) admin.mount(root);
})(typeof window === 'undefined' ? null : window, () => {
  'use strict';

  const STATUSES = ['Новая заявка', 'На рассмотрении', 'Нужен контакт', 'Интервью назначено', 'Интервью пройдено', 'Одобрен', 'Ожидаем ответ', 'Пауза', 'Активный участник', 'Не подходит'];
  const DECISIONS = STATUSES.slice(1);
  const OWNERS = ['Влад', 'Лара'];
  const PRIORITIES = ['Высокий', 'Средний', 'Низкий'];
  const NEXT_ACTIONS = ['Рассмотреть', 'Связаться', 'Назначить интервью', 'Провести интервью', 'Обсудить', 'Пригласить', 'Дождаться ответа', 'Добавить в участники', 'Связаться позже'];
  const WORKFLOW_ACTIONS = Object.freeze({
    'Новая заявка':['Рассмотреть'],
    'На рассмотрении':['Назначить интервью', 'Связаться'],
    'Нужен контакт':['Связаться'],
    'Интервью назначено':['Провести интервью'],
    'Интервью пройдено':['Обсудить'],
    'Одобрен':['Пригласить'],
    'Ожидаем ответ':['Дождаться ответа', 'Добавить в участники'],
    'Пауза':['Связаться позже'],
    'Активный участник':[],
    'Не подходит':[],
  });
  const OPERATIONAL = ['owner', 'priority', 'next_action', 'next_contact_at', 'decision', 'internal_comment'];
  const FIELDS = ['occupation', 'life_outside_work', 'what_interested', 'what_participant_brings', 'what_friends_value', 'desired_connections', 'desired_connections_other', 'values_in_people', 'barriers_to_meeting', 'acquaintance_methods', 'acquaintance_methods_other', 'return_reason', 'source'];
  const TEST_ADMIN_API_URL = 'https://d5ds805l71s68liu6ge4.fovt0b64.apigw.yandexcloud.net';
  const PROD_ADMIN_API_URL = 'https://d5dsivdtqjog5vgvn111.7qsg961h.apigw.yandexcloud.net';
  const labels = {submitted_at:'Дата заявки', full_name:'Имя', age:'Возраст', gender:'Пол', city:'Город', visit_krasnodar:'Посещение Краснодара', phone:'Телефон', email:'Email', preferred_contact:'Предпочтительный контакт', profile_or_messenger_url:'Профиль или мессенджер', occupation:'Сфера деятельности', public_profile_url:'Страница или сайт', status:'Статус заявки', owner:'Ответственный', priority:'Приоритет', next_action:'Следующее действие', next_contact_at:'Следующий контакт', decision:'Решение', internal_comment:'Внутренний комментарий', life_outside_work:'Чем наполнена ваша жизнь кроме работы?', what_interested:'Почему вам интересно попробовать «Гравитацию»?', what_participant_brings:'Что вы обычно привносите в компанию людей?', what_friends_value:'За что вас ценят друзья и знакомые?', desired_connections:'Какие знакомства вам сейчас интересны?', desired_connections_other:'Какие знакомства или формат общения вам интересны?', values_in_people:'Что вы особенно цените в людях?', barriers_to_meeting:'Что, возможно, мешает вам знакомиться с новыми людьми?', acquaintance_methods:'Какой способ знакомства для вас наиболее естественный?', acquaintance_methods_other:'Расскажите, как вам комфортнее знакомиться', return_reason:'Что должно произойти, чтобы захотелось прийти снова?', source:'Откуда узнали о нас?'};
  const text = (value) => value == null || value === '' ? '—' : String(value);
  const esc = (value) => text(value).replace(/[&<>'"]/gu, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
  const applicationNumber = (value) => Number.isInteger(Number(value)) && Number(value) > 0 ? String(value).padStart(6, '0') : text(value);
  const localDateTime = (value) => value ? String(value).replace(/Z$/u, '').slice(0, 16) : '';

  class ApiError extends Error { constructor(code, status) { super(code); this.code = code; this.status = status; } }
  const endpoint = (root) => {
    const config = root && root.__V5_ADMIN_CONFIG__;
    if (!config || !['TEST', 'PROD'].includes(config.environment)) throw new ApiError('admin_not_configured');
    const expected = config.environment === 'PROD' ? PROD_ADMIN_API_URL : TEST_ADMIN_API_URL;
    if (config.api_url !== expected) throw new ApiError('admin_not_configured');
    return expected;
  };

  function createClient(root, fetchImpl, getGatewayToken, onAuthFailure) {
    let base;
    try { base = endpoint(root); } catch { base = ''; }
    async function request(path, options = {}) {
      if (!base) throw new ApiError('admin_not_configured');
      const token = getGatewayToken && getGatewayToken();
      if (!token) throw new ApiError('authentication_required', 401);
      const response = await fetchImpl(`${base}${path}`, {...options, headers:{Authorization:`Bearer ${token}`, ...(options.headers || {})}});
      if (response.status === 401) { onAuthFailure && onAuthFailure('expired'); throw new ApiError('session_expired', 401); }
      if (response.status === 403) throw new ApiError('access_denied', 403);
      if (!response.ok) throw new ApiError('api_failed', response.status);
      return response.json();
    }
    return {
      list: (query, signal) => request(`/admin/applications?${new URLSearchParams(query)}`, {signal}),
      card: (id, signal) => request(`/admin/participants/${encodeURIComponent(id)}`, {signal}),
      save: (id, payload) => request(`/admin/participants/${encodeURIComponent(id)}`, {method:'PATCH', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)}),
    };
  }

  function createLatestRequest(AbortControllerImpl = globalThis.AbortController) {
    let generation = 0;
    let controller;
    return {
      begin() { generation += 1; if (controller) controller.abort(); controller = new AbortControllerImpl(); return {generation, signal:controller.signal}; },
      isLatest(value) { return value === generation; },
      cancel() { generation += 1; if (controller) controller.abort(); },
    };
  }

  function state(node, message, kind = '') { node.textContent = message; node.dataset.state = kind; }
  const optionList = (values, selected, emptyLabel = 'Не выбрано') => [`<option value="">${esc(emptyLabel)}</option>`, ...values.map((value) => `<option${selected === value ? ' selected' : ''}>${esc(value)}</option>`)].join('');
  const section = (title, values) => `<section class="card-section"><h3>${esc(title)}</h3><dl class="card-grid">${values.map(([key, value]) => `<div><dt>${esc(labels[key] || key)}</dt><dd>${esc(Array.isArray(value) ? value.join(', ') : value)}</dd></div>`).join('')}</dl></section>`;
  const eventLabel = (event) => {
    const action = String(event.action || '');
    if (action.startsWith('duplicate_submission')) return 'Повторная отправка · совпадение по нормализованному телефону';
    if (action.startsWith('application_operational_updated')) return 'Изменены рабочие поля заявки';
    if (action === 'application_created') return 'Заявка создана';
    return 'Служебное событие';
  };

  function mount(root) {
    const doc = root.document;
    const list = doc.querySelector('#admin-list');
    if (!list) return;
    const ui = {auth:doc.querySelector('#admin-auth'), app:doc.querySelector('#admin-workspace'), identity:doc.querySelector('#admin-identity'), login:doc.querySelector('#admin-login'), logout:doc.querySelector('#admin-logout'), state:doc.querySelector('#admin-state'), search:doc.querySelector('#admin-search'), status:doc.querySelector('#admin-status'), owner:doc.querySelector('#admin-owner'), priority:doc.querySelector('#admin-priority'), sort:doc.querySelector('#admin-sort'), drawer:doc.querySelector('#participant-drawer'), card:doc.querySelector('#participant-card'), cardNumber:doc.querySelector('#card-application-number'), cardName:doc.querySelector('#card-applicant-name')};
    STATUSES.forEach((value) => ui.status.add(new Option(value, value)));
    OWNERS.forEach((value) => ui.owner.add(new Option(value, value)));
    const authApi = root.V5AdminAuth;
    let auth;
    const showSignedOut = (message = 'Войдите с рабочей учётной записью.') => { ui.app.hidden = true; ui.auth.hidden = false; state(ui.auth.querySelector('[data-auth-state]'), message, 'signed-out'); };
    const authFailure = () => { auth.signOut(); showSignedOut('Сеанс завершён. Войдите снова.'); };
    if (!authApi) { showSignedOut('Не удалось подготовить вход. Обновите страницу или обратитесь к ответственному.'); return; }
    let runtimeConfig;
    try {
      runtimeConfig = root.__V5_ADMIN_CONFIG__;
      endpoint(root);
      auth = authApi.createAuthClient({config:runtimeConfig.auth, fetchImpl:root.fetch.bind(root), cryptoImpl:root.crypto, storage:root.sessionStorage, location:root.location});
    } catch { showSignedOut('Вход временно недоступен. Обратитесь к ответственному.'); return; }
    const client = createClient(root, root.fetch.bind(root), () => auth.getGatewayToken(), authFailure);
    const listRequests = createLatestRequest(root.AbortController);
    const cardRequests = createLatestRequest(root.AbortController);
    const query = () => { const [sort, order] = ui.sort.value.split(':'); return {q:ui.search.value.trim(), status:ui.status.value, owner:ui.owner.value, priority:ui.priority.value, sort, order}; };

    const load = async () => {
      const request = listRequests.begin();
      state(ui.state, 'Загрузка заявок…', 'loading');
      try {
        const body = await client.list(query(), request.signal);
        if (!listRequests.isLatest(request.generation)) return;
        if (body.environment !== runtimeConfig.environment) throw new ApiError('environment');
        const rows = body.applications || [];
        list.replaceChildren();
        if (!rows.length) { state(ui.state, 'Заявок по выбранным условиям нет.', 'empty'); return; }
        state(ui.state, `Найдено: ${rows.length}`, 'ready');
        rows.forEach((row) => {
          const tr = doc.createElement('tr');
          ['application_number','submitted_at','full_name','age','city','phone','profile_or_messenger_url','preferred_contact','status','owner','priority','next_action','next_contact_at','decision'].forEach((field, index) => {
            const td = doc.createElement('td');
            if (index === 0) td.textContent = `№${applicationNumber(row[field])}`;
            else if (index === 2) { const button = doc.createElement('button'); button.textContent = text(row[field]); button.onclick = () => openCard(row.application_id); td.append(button); }
            else td.textContent = text(row[field]);
            if (field === 'full_name' && Number(row.duplicate_attempt_count) > 0) { const warning = doc.createElement('span'); warning.className = 'duplicate-indicator'; warning.textContent = `Повтор: ${row.duplicate_attempt_count}`; td.append(warning); }
            tr.append(td);
          });
          list.append(tr);
        });
      } catch (error) {
        if (error && error.name === 'AbortError') return;
        if (!listRequests.isLatest(request.generation)) return;
        state(ui.state, error.code === 'access_denied' ? 'У вас нет прав для просмотра заявок.' : error.code === 'session_expired' ? 'Сеанс завершён. Войдите снова.' : 'Сервис временно недоступен. Попробуйте позже.', 'error');
      }
    };

    const openCard = async (id) => {
      const request = cardRequests.begin();
      ui.drawer.hidden = false;
      ui.card.textContent = 'Загрузка карточки…';
      ui.cardNumber.textContent = '';
      ui.cardName.textContent = '';
      try {
        const body = await client.card(id, request.signal);
        if (!cardRequests.isLatest(request.generation)) return;
        if (body.environment !== runtimeConfig.environment) throw new ApiError('environment');
        const application = body.application || {form:{}};
        const formData = application.form || {};
        const consents = body.consents || [];
        const events = body.events || [];
        ui.cardNumber.textContent = `№${applicationNumber(application.application_number)} · ${text(application.submitted_at)}`;
        ui.cardName.textContent = text(formData.full_name);
        const duplicateWarning = Number(application.duplicate_attempt_count) > 0 ? `<section class="duplicate-warning" role="status"><strong>Обнаружена повторная отправка</strong><p>Попыток: ${esc(application.duplicate_attempt_count)}. Последняя: ${esc(application.last_duplicate_at)}. Основание: совпадение по нормализованному телефону.</p></section>` : '';
        const possibleWarning = Number(application.possible_duplicate_count) > 0 ? `<section class="duplicate-warning possible-duplicate-warning" role="status"><strong>Возможный дубликат — требуется ручная проверка</strong><p>Основание: ${esc(application.possible_duplicate_match_basis)}. Связанная заявка: ${esc(application.possible_duplicate_application_id)}.</p></section>` : '';
        const consentSummary = consents.length ? consents.map((item) => `Согласие: ${item.granted === true ? 'получено' : 'не получено'} · Дата: ${esc(item.granted_at)} · Версия согласия: ${esc(item.consent_version)} · Политика: ${esc(item.policy_version)} · Анкета: ${esc(item.form_version)}`).join('<br>') : '—';
        const eventHistory = events.length ? events.map((item) => `<article class="history-item"><strong>${esc(eventLabel(item))}</strong><br>${esc(item.timestamp)}</article>`).join('') : '—';
        ui.card.innerHTML = `${duplicateWarning}${possibleWarning}${section('Основные сведения', ['submitted_at','full_name','age','gender','city','phone','profile_or_messenger_url','preferred_contact','email','public_profile_url'].map((key) => [key, key === 'submitted_at' ? application.submitted_at : formData[key]]))}${section('Анкета', FIELDS.map((key) => [key,formData[key]]))}<section class="card-section"><h3>Работа с заявкой</h3><form class="operational" id="operational-form"><div class="read-only-status"><span>${esc(labels.status)}</span><strong>${esc(application.status)}</strong></div><label>${esc(labels.owner)}<select name="owner">${optionList(OWNERS, application.owner)}</select></label><label>${esc(labels.priority)}<select name="priority">${optionList(PRIORITIES, application.priority)}</select></label><label>${esc(labels.next_action)}<select name="next_action">${optionList(NEXT_ACTIONS, application.next_action)}</select></label><label>${esc(labels.next_contact_at)}<input name="next_contact_at" type="datetime-local" value="${esc(localDateTime(application.next_contact_at))}"></label><label>${esc(labels.decision)}<select name="decision">${optionList(DECISIONS, application.decision)}</select></label><label>${esc(labels.internal_comment)}<textarea name="internal_comment">${application.internal_comment ? esc(application.internal_comment) : ''}</textarea></label><div class="save-row"><button>Сохранить изменения</button><span id="save-state"></span></div></form></section><section class="card-section"><h3>События заявки</h3>${eventHistory}</section><section class="card-section technical"><h3>Сведения о согласии</h3>${consentSummary}</section>`;
        const form = doc.querySelector('#operational-form');
        const decisionSelect = form.elements.decision;
        const actionSelect = form.elements.next_action;
        const syncWorkflowActions = (status) => {
          const allowed = WORKFLOW_ACTIONS[status] || NEXT_ACTIONS;
          const selected = allowed.includes(actionSelect.value) ? actionSelect.value : '';
          actionSelect.innerHTML = optionList(allowed, selected, allowed.length ? 'Выбрать действие' : 'Не требуется');
          actionSelect.disabled = false;
        };
        syncWorkflowActions(decisionSelect.value || application.status);
        decisionSelect.addEventListener('change', () => syncWorkflowActions(decisionSelect.value || application.status));
        form.onsubmit = async (event) => {
          event.preventDefault();
          const saveState = doc.querySelector('#save-state');
          saveState.textContent = 'Сохраняем…';
          try {
            await client.save(id, Object.fromEntries(new FormData(form)));
            saveState.textContent = 'Сохранено';
            await load();
            await openCard(id);
          } catch (error) { saveState.textContent = error.code === 'access_denied' ? 'У вас нет прав для этого действия.' : 'Не удалось сохранить изменения. Проверьте выбранные значения и дату контакта.'; }
        };
      } catch (error) {
        if (error && error.name === 'AbortError') return;
        if (cardRequests.isLatest(request.generation)) ui.card.textContent = 'Не удалось загрузить карточку. Попробуйте позже.';
      }
    };

    const showSignedIn = (session) => { ui.auth.hidden = true; ui.app.hidden = false; ui.identity.textContent = [session.user.name, session.user.email].filter(Boolean).join(' · ') || 'Сотрудник клуба'; load(); };
    ui.login.onclick = () => auth.signIn().catch(() => showSignedOut('Не удалось начать вход.'));
    ui.logout.onclick = () => { listRequests.cancel(); cardRequests.cancel(); auth.signOut(); showSignedOut(); };
    doc.querySelector('#drawer-close').onclick = () => { cardRequests.cancel(); ui.drawer.hidden = true; };
    [ui.status,ui.owner,ui.priority,ui.sort].forEach((node) => node.addEventListener('change', load));
    let searchTimer;
    ui.search.addEventListener('input', () => { root.clearTimeout(searchTimer); searchTimer = root.setTimeout(load, 180); });
    ui.search.addEventListener('search', load);
    state(ui.auth.querySelector('[data-auth-state]'), 'Проверяем доступ…', 'loading');
    auth.consumeCallback().then((session) => {
      if (session && root.history && typeof root.history.replaceState === 'function') root.history.replaceState({}, doc.title, runtimeConfig.auth.redirect_uri);
      const active = session || auth.getSession(); if (active) showSignedIn(active); else showSignedOut();
    }).catch(() => showSignedOut('Не удалось подтвердить вход.'));
  }

  return {STATUSES,DECISIONS,OWNERS,PRIORITIES,NEXT_ACTIONS,WORKFLOW_ACTIONS,OPERATIONAL,FIELDS,TEST_ADMIN_API_URL,ApiError,endpoint,createClient,createLatestRequest,applicationNumber,mount};
});
