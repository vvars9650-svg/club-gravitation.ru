(() => {
  'use strict';

  const MOBILE_QUERY = '(max-width: 980px)';
  const UTM_KEYS = ['utm_source','utm_medium','utm_campaign','utm_content','utm_term'];
  const body = document.body;
  const menuToggle = document.querySelector('.menu-toggle');
  const nav = document.querySelector('.nav');
  const year = document.getElementById('year');
  const applicationFrame = document.getElementById('application-frame');

  if (year) year.textContent = new Date().getFullYear();

  function closeMenu() {
    body.classList.remove('menu-open');
    menuToggle?.setAttribute('aria-expanded', 'false');
  }

  menuToggle?.addEventListener('click', () => {
    const willOpen = !body.classList.contains('menu-open');
    body.classList.toggle('menu-open', willOpen);
    menuToggle.setAttribute('aria-expanded', String(willOpen));
  });

  nav?.querySelectorAll('a').forEach(link => link.addEventListener('click', closeMenu));
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') closeMenu();
  });

  if (!applicationFrame) return;

  const base = applicationFrame.dataset.src;
  if (!base) return;

  const query = new URLSearchParams(window.location.search);
  const wrap = applicationFrame.closest('.application-frame-wrap');
  const isMobile = window.matchMedia(MOBILE_QUERY).matches;

  if (isMobile) {
    // Never navigate an Android user to Apps Script/Google Drive UI.
    // The public questionnaire lives on our own domain and uses Apps Script
    // only as a hidden server transport for saving Sheets + Drive data.
    applicationFrame.remove();
    if (!wrap) return;
    wrap.classList.add('is-mobile-link');

    const mobileUrl = new URL('apply.html', window.location.href);
    mobileUrl.search = '';
    UTM_KEYS.forEach(key => {
      const value = query.get(key);
      if (value) mobileUrl.searchParams.set(key, value);
    });

    const card = document.createElement('div');
    card.className = 'mobile-apply-card';

    const copy = document.createElement('p');
    copy.textContent = 'Анкета откроется на отдельной фирменной странице клуба. После отправки вы сразу увидите номер участника.';

    const link = document.createElement('a');
    link.className = 'button button--primary';
    link.href = mobileUrl.toString();
    link.textContent = 'Открыть анкету';
    link.setAttribute('data-mobile-apply-link', '');

    card.append(copy, link);
    wrap.appendChild(card);
    return;
  }

  const appUrl = new URL(base);
  UTM_KEYS.forEach(key => {
    const value = query.get(key);
    if (value) appUrl.searchParams.set(key, value);
  });
  appUrl.searchParams.set('parent_url', window.location.href);
  applicationFrame.src = appUrl.toString();
})();
