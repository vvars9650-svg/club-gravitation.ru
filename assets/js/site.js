(() => {
'use strict';

const cssLayers = ['/assets/css/polish.css', '/assets/css/tz-20260831.css', '/assets/css/story.css'];
cssLayers.forEach(href => {
  if (!document.querySelector(`link[href="${href}"]`)) {
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = href;
    document.head.appendChild(link);
  }
});

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
document.querySelectorAll('.brand__tag').forEach(el => { el.textContent = 'КЛУБ ВСТРЕЧ · КРАСНОДАР'; });
document.querySelectorAll('.home-scroll').forEach(el => el.remove());
const path = location.pathname.replace(/index\.html$/, '');
document.querySelectorAll('.site-nav a').forEach(a => {
  const target = new URL(a.href, location.origin).pathname.replace(/index\.html$/, '');
  if (target !== '/' && path.startsWith(target)) a.setAttribute('aria-current', 'page');
});

document.querySelectorAll('.site-footer').forEach(footer => {
  const links = footer.querySelector('.footer-links');
  if (links) {
    const founders = links.querySelector('a[href="/founders/"]') || document.createElement('a');
    founders.href = '/founders/';
    founders.textContent = 'Основатели';
    if (!founders.parentElement) links.appendChild(founders);
    const privacy = links.querySelector('a[href="/privacy/"]');
    if (privacy) privacy.textContent = 'Конфиденциальность';
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

  if (!footer.querySelector('.seller-details')) {
    const seller = document.createElement('div');
    seller.className = 'seller-details';
    seller.innerHTML = 'Исполнитель: Арсентьев Владислав Владимирович · плательщик НПД · ИНН: 236903136086<br><a href="tel:+79898080104">+7 989 808-01-04</a> · <a href="mailto:arsvvlad@yandex.ru">arsvvlad@yandex.ru</a>';
    footer.appendChild(seller);
  }
  let legalLinks = footer.querySelector('.footer-legal-links');
  if (!legalLinks) {
    legalLinks = document.createElement('div');
    legalLinks.className = 'footer-legal-links';
    legalLinks.setAttribute('aria-label', 'Документы');
    footer.appendChild(legalLinks);
  }
  [
    {href: '/privacy/', label: 'Конфиденциальность'},
    {href: '/offer/', label: 'Оферта'},
    {href: '/terms/', label: 'Участие и возврат'},
  ].forEach(({href, label}) => {
    const link = footer.querySelector(`a[href="${href}"]`) || document.createElement('a');
    link.href = href;
    link.textContent = label;
    legalLinks.appendChild(link);
  });
  legalLinks.querySelectorAll('a').forEach(link => {
    if (links && links.contains(link)) links.removeChild(link);
  });
});

if (!document.querySelector('.site-footer')) {
  const footer = document.createElement('footer');
  footer.className = 'site-footer seller-footer';
  footer.innerHTML = '<a class="footer-brand" href="/"><img src="/assets/brand/logo-mark.svg" alt=""><span>ГРАВИТАЦИЯ</span></a><p>КЛУБ ВСТРЕЧ · КРАСНОДАР</p><div class="footer-links"><a href="/about/">О клубе</a><a href="/events/">Мероприятия</a><a href="/founders/">Основатели</a><a href="/privacy/">Конфиденциальность</a></div><div class="footer-legal-links" aria-label="Документы"><a href="/offer/">Оферта</a><a href="/terms/">Участие и возврат</a></div><div class="seller-details">Исполнитель: Арсентьев Владислав Владимирович · плательщик НПД · ИНН: 236903136086<br><a href="tel:+79898080104">+7 989 808-01-04</a> · <a href="mailto:arsvvlad@yandex.ru">arsvvlad@yandex.ru</a></div><small>© <span data-year></span> Гравитация</small>';
  footer.querySelectorAll('[data-year]').forEach(el => el.textContent = new Date().getFullYear());
  const fallbackPrivacy = footer.querySelector('.footer-links a[href="/privacy/"]');
  const fallbackLegal = footer.querySelector('.footer-legal-links');
  if (fallbackPrivacy && fallbackLegal) fallbackLegal.prepend(fallbackPrivacy);
  document.body.appendChild(footer);
}
})();
