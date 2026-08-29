(() => {
  'use strict';

  const MOBILE_QUERY = '(max-width: 980px)';
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

  const appUrl = new URL(base);
  const query = new URLSearchParams(window.location.search);
  ['utm_source','utm_medium','utm_campaign','utm_content','utm_term'].forEach(key => {
    const value = query.get(key);
    if (value) appUrl.searchParams.set(key, value);
  });
  appUrl.searchParams.set('parent_url', window.location.href);

  const wrap = applicationFrame.closest('.application-frame-wrap');
  const isMobile = window.matchMedia(MOBILE_QUERY).matches;

  if (isMobile) {
    // Apps Script HTML Service is stable as a top-level page on Android, while
    // nested cross-origin rendering can fall back to a Google Drive error page.
    // Do not load the iframe at all on mobile.
    applicationFrame.remove();
    if (!wrap) return;
    wrap.classList.add('is-mobile-link');

    const card = document.createElement('div');
    card.className = 'mobile-apply-card';

    const copy = document.createElement('p');
    copy.textContent = 'Анкета откроется отдельной фирменной страницей клуба. После отправки вы сразу увидите номер участника.';

    const link = document.createElement('a');
    link.className = 'button button--primary';
    link.href = appUrl.toString();
    link.textContent = 'Открыть анкету';
    link.setAttribute('data-mobile-apply-link', '');

    card.append(copy, link);
    wrap.appendChild(card);
  } else {
    applicationFrame.src = appUrl.toString();
  }
})();
