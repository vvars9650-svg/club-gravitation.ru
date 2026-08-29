(() => {
  'use strict';

  const body = document.body;
  const menuToggle = document.querySelector('.menu-toggle');
  const nav = document.querySelector('.nav');
  const year = document.getElementById('year');
  const applicationFrame = document.getElementById('application-frame');

  if (year) year.textContent = new Date().getFullYear();

  menuToggle?.addEventListener('click', () => {
    const open = body.classList.toggle('menu-open');
    menuToggle.setAttribute('aria-expanded', String(open));
  });

  nav?.querySelectorAll('a').forEach(link => link.addEventListener('click', () => {
    body.classList.remove('menu-open');
    menuToggle?.setAttribute('aria-expanded', 'false');
  }));

  if (applicationFrame) {
    const base = applicationFrame.dataset.src || applicationFrame.src;
    const url = new URL(base);
    const current = new URLSearchParams(window.location.search);
    ['utm_source','utm_medium','utm_campaign','utm_content','utm_term'].forEach(key => {
      const value = current.get(key);
      if (value) url.searchParams.set(key, value);
    });
    url.searchParams.set('parent_url', window.location.href);
    applicationFrame.src = url.toString();
  }
})();
