'use strict';
const card = document.querySelector('.card');
const slides = [...document.querySelectorAll('.slide')];
const counter = document.querySelector('.counter');
const forward = document.querySelector('.forward');
const previous = document.querySelector('.previous');
const dots = [...document.querySelectorAll('.dots li')];
const note = document.querySelector('#preview-note');
let current = 1;

function showScreen(number) {
  if (number < 1 || number > slides.length) return;
  current = number;
  card.dataset.current = String(current);
  card.setAttribute('aria-label', `Визитка Лары Аджайя, экран ${current} из 5`);
  for (const slide of slides) slide.hidden = Number(slide.dataset.screen) !== current;
  counter.textContent = `${current} / 5`;
  counter.setAttribute('aria-label', `Экран ${current} из 5`);
  dots.forEach((item, index) => {
    item.querySelector('.dot').classList.toggle('active', index + 1 === current);
    if (index + 1 === current) item.setAttribute('aria-current', 'step');
    else item.removeAttribute('aria-current');
  });
  previous.hidden = current === 1;
  previous.setAttribute('aria-label', `Предыдущий экран: ${current - 1} из 5`);
  forward.hidden = current === slides.length;
  forward.setAttribute('aria-label', `Следующий экран: ${current + 1} из 5`);
  note.textContent = `Экран ${current} из 5.`;
}

forward.addEventListener('click', () => showScreen(current + 1));
previous.addEventListener('click', () => showScreen(current - 1));
for (const button of document.querySelectorAll('[data-go]')) {
  button.addEventListener('click', () => showScreen(Number(button.dataset.go)));
}
card.addEventListener('keydown', (event) => {
  if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
  event.preventDefault();
  showScreen(current + (event.key === 'ArrowRight' ? 1 : -1));
});

let touchStart = null;
card.addEventListener('pointerdown', (event) => {
  if (event.pointerType !== 'touch' || event.target.closest('button, a')) return;
  touchStart = {x:event.clientX, y:event.clientY, id:event.pointerId};
  card.setPointerCapture(event.pointerId);
});
card.addEventListener('pointerup', (event) => {
  if (!touchStart || touchStart.id !== event.pointerId) return;
  const dx = event.clientX - touchStart.x;
  const dy = event.clientY - touchStart.y;
  touchStart = null;
  if (Math.abs(dx) >= 45 && Math.abs(dx) > Math.abs(dy) * 1.4) showScreen(current + (dx < 0 ? 1 : -1));
});
card.addEventListener('pointercancel', () => { touchStart = null; });
showScreen(1);
