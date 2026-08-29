(() => {
  'use strict';

  const MOBILE_QUERY = '(max-width: 980px)';
  const body = document.body;
  const menuToggle = document.querySelector('.menu-toggle');
  const nav = document.querySelector('.nav');
  const year = document.getElementById('year');
  const applicationFrame = document.getElementById('application-frame');

  // Hard mobile overrides. The old transform-only menu could leak individual
  // links into the header on Android when the dynamic browser viewport changed.
  const style = document.createElement('style');
  style.textContent = `
    @media (max-width:980px){
      .site-header{isolation:isolate;}
      .site-header .nav{
        position:fixed!important;
        inset:0!important;
        z-index:1!important;
        display:flex!important;
        flex-direction:column!important;
        align-items:center!important;
        justify-content:center!important;
        gap:22px!important;
        padding:96px 24px 36px!important;
        background:rgba(245,240,232,.985)!important;
        transform:none!important;
        opacity:0!important;
        visibility:hidden!important;
        pointer-events:none!important;
        overflow-y:auto!important;
        font-size:18px!important;
        transition:opacity .22s ease,visibility .22s ease!important;
      }
      body.menu-open .site-header .nav{
        opacity:1!important;
        visibility:visible!important;
        pointer-events:auto!important;
      }
      .site-header .nav a{display:block!important;opacity:1!important;}
      .site-header .nav__cta{margin-top:8px!important;padding:11px 20px!important;}
      .menu-toggle{z-index:3!important;}
      .application-frame-wrap.is-mobile-link{
        min-height:0!important;
        padding:0!important;
        border:0!important;
        background:transparent!important;
        box-shadow:none!important;
      }
      .application-frame-wrap.is-mobile-link .application-frame{display:none!important;}
      .mobile-apply-card{
        display:flex;
        flex-direction:column;
        gap:14px;
        padding:26px 22px;
        border:1px solid rgba(25,24,22,.14);
        border-radius:22px;
        background:rgba(255,255,255,.72);
        box-shadow:0 18px 48px rgba(55,43,31,.10);
      }
      .mobile-apply-card p{margin:0;color:#514a44;font-size:14px;line-height:1.6;}
      .mobile-apply-card .button{width:100%;min-height:54px;}
    }
  `;
  document.head.appendChild(style);

  if (year) year.textContent = new Date().getFullYear();

  function closeMenu() {
    body.classList.remove('menu-open');
    menuToggle?.setAttribute('aria-expanded', 'false');
  }

  menuToggle?.addEventListener('click', () => {
    const open = !body.classList.contains('menu-open');
    body.classList.toggle('menu-open', open);
    menuToggle.setAttribute('aria-expanded', String(open));
  });

  nav?.querySelectorAll('a').forEach(link => link.addEventListener('click', closeMenu));
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') closeMenu();
  });

  if (applicationFrame) {
    const base = applicationFrame.dataset.src || applicationFrame.src;
    const url = new URL(base);
    const current = new URLSearchParams(window.location.search);
    ['utm_source','utm_medium','utm_campaign','utm_content','utm_term'].forEach(key => {
      const value = current.get(key);
      if (value) url.searchParams.set(key, value);
    });
    url.searchParams.set('parent_url', window.location.href);

    if (window.matchMedia(MOBILE_QUERY).matches) {
      // Android Chrome is unreliable with the Apps Script sandbox nested in a
      // cross-origin iframe. Open the exact same branded form as a top-level
      // page instead. No Google Forms UI is involved.
      const wrap = applicationFrame.closest('.application-frame-wrap');
      if (wrap) {
        wrap.classList.add('is-mobile-link');
        applicationFrame.removeAttribute('src');
        applicationFrame.hidden = true;
        const card = document.createElement('div');
        card.className = 'mobile-apply-card';
        card.innerHTML = '<p>Анкета откроется отдельной защищённой страницей клуба. После отправки вы сразу увидите номер участника.</p>';
        const link = document.createElement('a');
        link.className = 'button button--primary';
        link.href = url.toString();
        link.textContent = 'Открыть анкету';
        card.appendChild(link);
        wrap.appendChild(card);
      }
    } else {
      applicationFrame.src = url.toString();
    }
  }
})();
