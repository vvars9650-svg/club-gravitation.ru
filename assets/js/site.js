(() => {
'use strict';

const polishHref = '/assets/css/polish.css';
if (!document.querySelector(`link[href="${polishHref}"]`)) {
  const polish = document.createElement('link');
  polish.rel = 'stylesheet';
  polish.href = polishHref;
  document.head.appendChild(polish);
}

const menu = document.querySelector('.menu-toggle');
const nav = document.querySelector('.site-nav');
if (menu && nav) {
  menu.addEventListener('click', () => {
    const open = menu.getAttribute('aria-expanded') === 'true';
    menu.setAttribute('aria-expanded', String(!open));
    nav.classList.toggle('is-open', !open);
    document.body.classList.toggle('menu-open', !open);
  });
  nav.querySelectorAll('a').forEach(a => a.addEventListener('click', () => {
    menu.setAttribute('aria-expanded', 'false');
    nav.classList.remove('is-open');
    document.body.classList.remove('menu-open');
  }));
}

document.querySelectorAll('[data-year]').forEach(el => el.textContent = new Date().getFullYear());
const path = location.pathname.replace(/index\.html$/, '');
document.querySelectorAll('.site-nav a').forEach(a => {
  const target = new URL(a.href, location.origin).pathname.replace(/index\.html$/, '');
  if (target !== '/' && path.startsWith(target)) a.setAttribute('aria-current', 'page');
});

document.querySelectorAll('.site-footer').forEach(footer => {
  const links = footer.querySelector('.footer-links');
  if (links && !links.querySelector('a[href="/founders/"]')) {
    const founders = document.createElement('a');
    founders.href = '/founders/';
    founders.textContent = 'Основатели';
    const privacy = links.querySelector('a[href="/privacy/"]');
    links.insertBefore(founders, privacy || null);
  }

  if (!footer.querySelector('.back-to-top')) {
    const top = document.createElement('button');
    top.type = 'button';
    top.className = 'back-to-top';
    top.setAttribute('aria-label', 'Наверх');
    top.setAttribute('title', 'Наверх');
    top.addEventListener('click', () => window.scrollTo({ top: 0, behavior: 'smooth' }));
    footer.appendChild(top);
  }
});
})();
