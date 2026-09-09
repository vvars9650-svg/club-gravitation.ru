(function bootstrap(root, factory) {
  const admin = factory();
  if (typeof module === 'object' && module.exports) module.exports = admin;
  if (root && root.document) admin.mount(root);
})(typeof window === 'undefined' ? null : window, () => {
  'use strict';
  const STATUSES = ['Новая заявка', 'На рассмотрении', 'Нужен контакт', 'Интервью назначено', 'Интервью пройдено', 'Одобрен', 'Активный участник', 'Пауза', 'Не подходит'];
  const OPERATIONAL = ['lifecycle_status', 'owner', 'priority', 'next_action', 'next_contact_at', 'decision', 'internal_comment'];
  const FIELDS = ['occupation', 'life_outside_work', 'interests', 'what_interested', 'event_expectations', 'desired_connections', 'values_in_people', 'barriers_to_meeting', 'social_comfort', 'initiative', 'acquaintance_scenario', 'successful_evening', 'return_reason', 'unacceptable_behavior', 'convenient_days', 'comfortable_price', 'source'];
  const labels = {full_name:'Имя', age:'Возраст', gender:'Пол', city:'Город', visit_krasnodar:'Посещение Краснодара', phone:'Телефон', telegram:'Telegram', email:'Email', preferred_contact:'Предпочтительный контакт', public_profile_url:'Публичный профиль', lifecycle_status:'Статус', owner:'Ответственный', priority:'Приоритет', next_action:'Следующее действие', next_contact_at:'Следующий контакт', decision:'Решение', internal_comment:'Внутренний комментарий'};
  const text = (value) => value == null || value === '' ? '—' : String(value);
  const esc = (value) => text(value).replace(/[&<>'"]/gu, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
  const endpoint = (root) => String(root.__V5_ADMIN_API_URL__ || '').replace(/\/$/u, '');
  class ApiError extends Error { constructor(code, status) { super(code); this.code = code; this.status = status; } }
  function createClient(root, fetchImpl, getAccessToken, onAuthFailure) {
    const base = endpoint(root);
    async function request(path, options = {}) {
      if (!base) throw new ApiError('admin_not_configured');
      const token = getAccessToken && getAccessToken();
      if (!token) throw new ApiError('authentication_required', 401);
      const response = await fetchImpl(`${base}${path}`, { ...options, headers: {'Authorization': `Bearer ${token}`, ...(options.headers || {})} });
      if (response.status === 401) { onAuthFailure && onAuthFailure('expired'); throw new ApiError('session_expired', 401); }
      if (response.status === 403) throw new ApiError('access_denied', 403);
      if (!response.ok) throw new ApiError('api_failed', response.status);
      return response.json();
    }
    return {list: (query) => request(`/admin/applications?${new URLSearchParams(query)}`), card: (id) => request(`/admin/participants/${encodeURIComponent(id)}`), save: (id, payload) => request(`/admin/participants/${encodeURIComponent(id)}`, {method:'PATCH', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)})};
  }
  function state(node, message, kind = '') { node.textContent = message; node.dataset.state = kind; }
  function mount(root) {
    const doc = root.document;
    const list = doc.querySelector('#admin-list');
    if (!list) return;
    const ui = {auth: doc.querySelector('#admin-auth'), app: doc.querySelector('#admin-workspace'), identity: doc.querySelector('#admin-identity'), login: doc.querySelector('#admin-login'), logout: doc.querySelector('#admin-logout'), state: doc.querySelector('#admin-state'), search: doc.querySelector('#admin-search'), status: doc.querySelector('#admin-status'), owner: doc.querySelector('#admin-owner'), priority: doc.querySelector('#admin-priority'), sort: doc.querySelector('#admin-sort'), drawer: doc.querySelector('#participant-drawer'), card: doc.querySelector('#participant-card')};
    STATUSES.forEach((value) => ui.status.add(new Option(value, value)));
    const authApi = root.V5AdminAuth;
    let auth;
    const showSignedOut = (message = 'Войдите через корпоративную Identity Hub учётную запись.') => { ui.app.hidden = true; ui.auth.hidden = false; state(ui.auth.querySelector('[data-auth-state]'), message, 'signed-out'); };
    const authFailure = () => { auth.signOut(); showSignedOut('Сессия истекла. Войдите снова.'); };
    if (!authApi) { showSignedOut('OIDC-модуль не загружен.'); return; }
    try { auth = authApi.createAuthClient({config: root.__V5_ADMIN_AUTH_CONFIG__, fetchImpl: root.fetch.bind(root), cryptoImpl: root.crypto, storage: root.sessionStorage, location: root.location}); } catch { showSignedOut('OIDC TEST-конфигурация ещё не задана.'); return; }
    const client = createClient(root, root.fetch.bind(root), () => auth.getAccessToken(), authFailure);
    const query = () => { const [sort, order] = ui.sort.value.split(':'); return {q: ui.search.value.trim(), lifecycle_status: ui.status.value, owner: ui.owner.value.trim(), priority: ui.priority.value, sort, order}; };
    const load = async () => { state(ui.state, 'Загрузка заявок…', 'loading'); list.replaceChildren(); try { const body = await client.list(query()); if (body.environment !== 'TEST') throw new ApiError('environment'); const rows = body.applications || []; if (!rows.length) { state(ui.state, 'Заявок по выбранным условиям нет.', 'empty'); return; } state(ui.state, `Найдено: ${rows.length}`, 'ready'); rows.forEach((row) => { const tr = doc.createElement('tr'); ['submitted_at','full_name','age','city','phone','telegram','preferred_contact','lifecycle_status','owner','priority','next_action','next_contact_at','decision'].forEach((field, index) => { const td = doc.createElement('td'); if (index === 1) { const button = doc.createElement('button'); button.textContent = text(row[field]); button.onclick = () => openCard(row.participant_id); td.append(button); } else td.textContent = text(row[field]); tr.append(td); }); list.append(tr); }); } catch (error) { state(ui.state, error.code === 'access_denied' ? 'Доступ запрещён.' : error.code === 'session_expired' ? 'Сессия истекла. Войдите снова.' : 'Не удалось загрузить заявки. Повторите попытку.', 'error'); } };
    const section = (title, values) => `<section class="card-section"><h3>${esc(title)}</h3><dl class="card-grid">${values.map(([key, value]) => `<div><dt>${esc(labels[key] || key)}</dt><dd>${esc(Array.isArray(value) ? value.join(', ') : value)}</dd></div>`).join('')}</dl></section>`;
    const openCard = async (id) => { ui.drawer.hidden = false; ui.card.textContent = 'Загрузка карточки…'; try { const body = await client.card(id); if (body.environment !== 'TEST') throw new ApiError('environment'); const p = body.participant, application = body.applications[0] || {form:{}}; ui.card.innerHTML = `<h2>${esc(p.full_name)} <small class="env-badge">TEST</small></h2>${section('Контакты', ['phone','telegram','email','preferred_contact','public_profile_url','city'].map((key) => [key,p[key]]))}${section('Анкета', FIELDS.map((key) => [key,application.form[key]]))}<section class="card-section"><h3>Operational</h3><form class="operational" id="operational-form">${OPERATIONAL.map((key) => key === 'lifecycle_status' ? `<label>${esc(labels[key])}<select name="${key}">${STATUSES.map((item) => `<option ${p[key] === item ? 'selected' : ''}>${esc(item)}</option>`).join('')}</select></label>` : key === 'internal_comment' ? `<label>${esc(labels[key])}<textarea name="${key}">${p[key] ? esc(p[key]) : ''}</textarea></label>` : `<label>${esc(labels[key])}<input name="${key}" value="${p[key] ? esc(p[key]) : ''}"></label>`).join('')}<div class="save-row"><button>Сохранить изменения</button><span id="save-state"></span></div></form></section><section class="card-section"><h3>История заявок</h3>${(body.applications || []).map((item) => `<article class="history-item"><strong>${esc(item.application_id)}</strong><br>${esc(item.submitted_at)} · ${esc(item.form_version)}</article>`).join('') || '—'}</section><section class="card-section technical"><h3>Consent evidence (read-only)</h3>${(body.consents || []).map((item) => `${esc(item.consent_id)}: ${esc(item.consent_version)}, ${esc(item.policy_version)}, ${esc(item.form_version)}, granted=${esc(item.granted)}`).join('<br>') || '—'}</section>`; const form = doc.querySelector('#operational-form'); form.onsubmit = async (event) => { event.preventDefault(); const saveState = doc.querySelector('#save-state'); saveState.textContent = 'Сохраняем…'; try { await client.save(id, Object.fromEntries(new FormData(form))); saveState.textContent = 'Сохранено'; load(); } catch (error) { saveState.textContent = error.code === 'access_denied' ? 'Доступ запрещён' : 'Не удалось сохранить'; } }; } catch { ui.card.textContent = 'Не удалось загрузить карточку.'; } };
    const showSignedIn = (session) => { ui.auth.hidden = true; ui.app.hidden = false; ui.identity.textContent = [session.user.name, session.user.email].filter(Boolean).join(' · ') || 'Авторизованный пользователь'; load(); };
    ui.login.onclick = () => auth.signIn().catch(() => showSignedOut('Не удалось начать вход.'));
    ui.logout.onclick = () => { auth.signOut(); showSignedOut(); };
    doc.querySelector('#drawer-close').onclick = () => { ui.drawer.hidden = true; };
    [ui.search,ui.status,ui.owner,ui.priority,ui.sort].forEach((node) => node.addEventListener('change', load)); ui.search.addEventListener('search', load);
    state(ui.auth.querySelector('[data-auth-state]'), 'Проверяем авторизацию…', 'loading');
    auth.consumeCallback().then((session) => { const active = session || auth.getSession(); if (active) showSignedIn(active); else showSignedOut(); }).catch(() => showSignedOut('Не удалось подтвердить вход.'));
  }
  return {STATUSES,OPERATIONAL,FIELDS,ApiError,createClient,mount};
});
