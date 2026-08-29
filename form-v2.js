(() => {
  'use strict';

  const ENDPOINT = 'https://script.google.com/macros/s/AKfycbz3LNz4si1i2wueB1I1T5AleCOaaQ-HEgBWS1Injh_mCjFmkAQqKyCqvDH3LrgzBoI/exec';
  const RESPONSE_TYPE = 'gravitation-v2-submit';
  const MAX_FILE_BYTES = 10 * 1024 * 1024;
  const STEPS = ['Контактная информация','Фотография','О вас','Знакомства','Формат встреч','Проверка'];
  const YUFO_CITIES = ["Абинск","Адыгейск","Азов","Аксай","Алупка","Алушта","Анапа","Апшеронск","Армавир","Армянск","Астрахань","Ахтубинск","Батайск","Бахчисарай","Белая Калитва","Белогорск","Белореченск","Волгоград","Волгодонск","Волжский","Геленджик","Городовиковск","Горячий Ключ","Гуково","Гулькевичи","Джанкой","Донецк","Дубовка","Евпатория","Ейск","Жирновск","Зверево","Зерноград","Знаменск","Инкерман","Калач-на-Дону","Каменск-Шахтинский","Камызяк","Камышин","Керчь","Константиновск","Кореновск","Котельниково","Котово","Краснодар","Красноперекопск","Краснослободск","Красный Сулин","Кропоткин","Крымск","Курганинск","Лабинск","Лагань","Ленинск","Майкоп","Миллерово","Михайловка","Морозовск","Нариманов","Николаевск","Новоаннинский","Новокубанск","Новороссийск","Новочеркасск","Новошахтинск","Палласовка","Петров Вал","Приморско-Ахтарск","Пролетарск","Ростов-на-Дону","Саки","Сальск","Севастополь","Семикаракорск","Серафимович","Симферополь","Славянск-на-Кубани","Сочи","Старый Крым","Судак","Суровикино","Таганрог","Темрюк","Тимашёвск","Тихорецк","Туапсе","Урюпинск","Усть-Лабинск","Феодосия","Фролово","Хадыженск","Харабали","Цимлянск","Шахты","Щёлкино","Элиста","Ялта"];

  const form = document.querySelector('#application-v2');
  if (!form) return;

  const steps = [...form.querySelectorAll('.v2-step')];
  const tabs = [...document.querySelectorAll('.v2-tab')];
  const progress = document.querySelector('#v2-progress-bar');
  const mobileStep = document.querySelector('#v2-mobile-step');
  const back = document.querySelector('#v2-back');
  const next = document.querySelector('#v2-next');
  const review = document.querySelector('#v2-review');
  const status = document.querySelector('#v2-status');
  const submit = document.querySelector('#v2-submit');
  const success = document.querySelector('#v2-success');
  const successId = document.querySelector('#v2-success-id');
  const age = form.elements.age;
  const city = form.elements.city;
  const cityVisitWrap = form.querySelector('.v2-city-visit');
  const cityVisit = form.elements.city_visit;
  const phone = form.elements.phone;
  const email = form.elements.email;
  const photoInput = document.querySelector('#v2-photo');
  const dropzone = document.querySelector('#v2-dropzone');
  const photoPreview = document.querySelector('#v2-photo-preview');
  const photoName = document.querySelector('#v2-photo-name');
  const photoError = document.querySelector('#v2-photo-error');

  let currentStep = 0;
  let maxReached = 0;
  let photoPayload = null;
  let activeSubmission = null;

  fillSelects();
  bindNavigation();
  bindContactValidation();
  bindPhoto();
  bindSubmission();
  renderStep(0);

  function fillSelects() {
    for (let value = 25; value <= 52; value += 1) {
      const option = document.createElement('option');
      option.value = String(value);
      option.textContent = String(value);
      age.appendChild(option);
    }
    YUFO_CITIES.forEach(value => {
      const option = document.createElement('option');
      option.value = value;
      option.textContent = value;
      city.appendChild(option);
    });
  }

  function bindNavigation() {
    next.addEventListener('click', () => {
      if (!validateStep(currentStep)) return;
      if (currentStep < steps.length - 1) goTo(currentStep + 1);
    });
    back.addEventListener('click', () => {
      if (currentStep > 0) goTo(currentStep - 1);
    });
    tabs.forEach((tab, index) => tab.addEventListener('click', () => {
      if (index <= maxReached) goTo(index);
    }));
  }

  function goTo(index) {
    currentStep = Math.max(0, Math.min(index, steps.length - 1));
    maxReached = Math.max(maxReached, currentStep);
    if (currentStep === steps.length - 1) buildReview();
    renderStep(currentStep);
    document.querySelector('.v2-card')?.scrollIntoView({behavior:'smooth', block:'start'});
  }

  function renderStep(index) {
    steps.forEach((step, i) => step.classList.toggle('is-active', i === index));
    tabs.forEach((tab, i) => {
      tab.classList.toggle('is-active', i === index);
      tab.classList.toggle('is-done', i < index || i < maxReached);
      tab.disabled = i > maxReached;
    });
    progress.style.width = `${((index + 1) / steps.length) * 100}%`;
    mobileStep.textContent = STEPS[index];

    // Важное правило V2: кнопки существуют в одном месте и управляются только здесь.
    back.style.display = index === 0 ? 'none' : 'inline-flex';
    next.style.display = index === steps.length - 1 ? 'none' : 'inline-flex';
  }

  function bindContactValidation() {
    city.addEventListener('change', syncCityVisit);
    syncCityVisit();

    phone.addEventListener('focus', () => {
      if (!phone.value) phone.value = '+7 ';
    });
    phone.addEventListener('input', () => {
      phone.value = formatPhone(phone.value);
      phone.classList.remove('is-invalid');
    });
    email.addEventListener('input', () => email.classList.remove('is-invalid'));
    form.querySelectorAll('input,select,textarea').forEach(el => {
      el.addEventListener('change', () => el.classList.remove('is-invalid'));
    });
  }

  function syncCityVisit() {
    const needsVisit = Boolean(city.value && city.value !== 'Краснодар');
    cityVisitWrap.hidden = !needsVisit;
    cityVisit.required = needsVisit;
    if (!needsVisit) cityVisit.value = '';
  }

  function formatPhone(value) {
    let digits = String(value || '').replace(/\D/g, '');
    if (digits[0] === '7' || digits[0] === '8') digits = digits.slice(1);
    digits = digits.slice(0, 10);
    let out = '+7';
    if (digits.length) out += ' ' + digits.slice(0, 3);
    if (digits.length > 3) out += ' ' + digits.slice(3, 6);
    if (digits.length > 6) out += '-' + digits.slice(6, 8);
    if (digits.length > 8) out += '-' + digits.slice(8, 10);
    return out;
  }

  function normalizedPhone() {
    let digits = String(phone.value || '').replace(/\D/g, '');
    if (digits.length === 11 && (digits[0] === '7' || digits[0] === '8')) digits = digits.slice(1);
    return digits.length === 10 ? '+7' + digits : '';
  }

  function bindPhoto() {
    photoInput.addEventListener('change', () => {
      const file = photoInput.files && photoInput.files[0];
      if (file) processPhoto(file);
    });

    const stop = event => { event.preventDefault(); event.stopPropagation(); };
    ['dragenter','dragover'].forEach(type => dropzone.addEventListener(type, event => {
      stop(event); dropzone.classList.add('is-dragover');
      if (event.dataTransfer) event.dataTransfer.dropEffect = 'copy';
    }));
    ['dragleave','dragend'].forEach(type => dropzone.addEventListener(type, event => {
      stop(event); dropzone.classList.remove('is-dragover');
    }));
    dropzone.addEventListener('drop', event => {
      stop(event); dropzone.classList.remove('is-dragover');
      const file = [...(event.dataTransfer?.files || [])].find(item => /^image\/(jpeg|png|webp)$/i.test(item.type));
      if (!file) {
        showPhotoError('Перетащите изображение JPG, PNG или WEBP.');
        return;
      }
      processPhoto(file);
    });
  }

  async function processPhoto(file) {
    photoPayload = null;
    photoError.textContent = '';
    if (!/^image\/(jpeg|png|webp)$/i.test(file.type)) return showPhotoError('Поддерживаются JPG, PNG и WEBP.');
    if (file.size > MAX_FILE_BYTES) return showPhotoError('Файл больше 10 МБ. Выберите фотографию поменьше.');

    try {
      const source = await fileToDataUrl(file);
      const image = await loadImage(source);
      const maxSide = 1600;
      const scale = Math.min(1, maxSide / Math.max(image.naturalWidth || image.width, image.naturalHeight || image.height));
      const width = Math.max(1, Math.round((image.naturalWidth || image.width) * scale));
      const height = Math.max(1, Math.round((image.naturalHeight || image.height) * scale));
      const canvas = document.createElement('canvas');
      canvas.width = width; canvas.height = height;
      canvas.getContext('2d', {alpha:false}).drawImage(image, 0, 0, width, height);
      const blob = await canvasToBlob(canvas, 'image/jpeg', .84);
      const encoded = await fileToDataUrl(blob);
      photoPayload = {
        data: encoded.split(',')[1],
        type: 'image/jpeg',
        name: String(file.name || 'photo.jpg').replace(/\.[^.]+$/, '') + '.jpg'
      };
      photoPreview.innerHTML = `<img src="${encoded}" alt="Предпросмотр фотографии">`;
      photoName.textContent = file.name;
      dropzone.classList.remove('is-invalid');
    } catch (error) {
      console.error(error);
      showPhotoError('Не удалось обработать фотографию. Попробуйте другой файл.');
    }
  }

  function showPhotoError(message) {
    photoError.textContent = message;
    dropzone.classList.add('is-invalid');
  }

  function validateStep(index) {
    clearStatus();
    let firstInvalid = null;

    if (index === 0) {
      ['name','age','gender','city'].forEach(name => {
        const el = form.elements[name];
        if (!String(el.value || '').trim()) markInvalid(el);
      });
      if (city.value && city.value !== 'Краснодар' && !cityVisit.value) markInvalid(cityVisit);
      if (!normalizedPhone()) markInvalid(phone);
      if (email.value && !/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/u.test(email.value.trim())) markInvalid(email);
      firstInvalid = steps[index].querySelector('.is-invalid');
    }

    if (index === 1 && !photoPayload) {
      showPhotoError('Фотография обязательна.');
      firstInvalid = dropzone;
    }

    if (firstInvalid) {
      firstInvalid.scrollIntoView({behavior:'smooth', block:'center'});
      firstInvalid.focus?.();
      return false;
    }
    return true;
  }

  function markInvalid(el) {
    if (el) el.classList.add('is-invalid');
  }

  function buildReview() {
    const values = collectValues();
    const cards = [
      ['Контактная информация',0,[['Имя и фамилия',values.name],['Возраст',values.age],['Пол',values.gender],['Город',values.city],['Посещение Краснодара',values.city_visit],['Телефон',values.phone],['Telegram',values.telegram],['Email',values.email],['Как связаться',values.preferred_contact]]],
      ['Фотография',1,[['Фото',photoPayload ? 'Загружено' : '—']]],
      ['О вас',2,[['Чем занимаетесь',values.occupation],['Жизнь кроме работы',values.life_beyond_work],['Интересы',values.interests],['Что зацепило',values.interest_reason],['Ожидания от первой встречи',values.expectations]]],
      ['Знакомства',3,[['Контекст отношений',values.relationship_context],['Интересующие знакомства',values.connection_goal],['Что цените в людях',values.values_people],['Что мешает знакомиться',values.meeting_barriers],['Комфорт в новой компании',values.social_comfort],['Инициативность',values.initiative],['Естественный способ знакомства',values.introduction_scenario]]],
      ['Формат встреч',4,[['Удачный вечер',values.successful_evening],['Что заставит вернуться',values.return_reason],['Неприемлемое поведение',values.unacceptable_behavior],['Удобные дни',values.convenient_days],['Комфортная стоимость',values.comfortable_price],['Источник',values.source]]]
    ];

    review.innerHTML = cards.map(([title,step,pairs]) => `
      <article class="v2-review-card">
        <div class="v2-review-head"><strong>${escapeHtml(title)}</strong><button type="button" data-edit-step="${step}">Изменить</button></div>
        <dl class="v2-review-grid">${pairs.map(([label,value]) => `<dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value || '—')}</dd>`).join('')}</dl>
      </article>`).join('');

    review.querySelectorAll('[data-edit-step]').forEach(button => button.addEventListener('click', () => goTo(Number(button.dataset.editStep))));
  }

  function collectValues() {
    const data = {};
    [...form.elements].forEach(el => {
      if (!el.name || el.name === 'photo') return;
      if (el.type === 'checkbox') {
        if (!el.checked) return;
        data[el.name] = data[el.name] ? `${data[el.name]}, ${el.value}` : el.value;
      } else if (el.type !== 'file') {
        data[el.name] = String(el.value || '').trim();
      }
    });
    data.phone = normalizedPhone() || String(phone.value || '').trim();
    if (data.city === 'Краснодар') data.city_visit = 'Краснодар';
    return data;
  }

  function bindSubmission() {
    form.addEventListener('submit', async event => {
      event.preventDefault();
      if (activeSubmission) return;
      if (!validateBeforeSubmit()) return;

      const values = collectValues();
      const participantId = makeParticipantId();
      const token = `v2_${Date.now()}_${Math.random().toString(36).slice(2)}`;
      activeSubmission = {participantId, token};
      submit.disabled = true;
      submit.textContent = 'ОТПРАВЛЯЕМ…';
      clearStatus();

      const params = new URLSearchParams();
      Object.entries(values).forEach(([key,value]) => params.set(key, value));
      params.set('participant_id', participantId);
      params.set('photo_data', photoPayload.data);
      params.set('photo_type', photoPayload.type);
      params.set('photo_name', photoPayload.name);
      params.set('response_mode', 'postmessage');
      params.set('response_token', token);
      params.set('page_url', location.href);
      params.set('referrer', document.referrer || '');
      params.set('user_agent', navigator.userAgent || '');
      params.set('submitted_at_client', new Date().toISOString());
      const query = new URLSearchParams(location.search);
      ['utm_source','utm_medium','utm_campaign','utm_content','utm_term'].forEach(key => params.set(key, query.get(key) || ''));

      const timer = setTimeout(() => finishWithError('Сервер не ответил вовремя. Не отправляйте заявку повторно сразу.'), 60000);

      const onMessage = event => {
        const data = event.data;
        if (!data || data.type !== RESPONSE_TYPE || data.token !== token) return;
        window.removeEventListener('message', onMessage);
        clearTimeout(timer);
        if (data.ok && data.id === participantId) finishWithSuccess(data.id);
        else finishWithError(data.error || 'Не удалось сохранить заявку. Попробуйте ещё раз.');
      };
      window.addEventListener('message', onMessage);
      postToIframe(params);
    });
  }

  function validateBeforeSubmit() {
    if (!validateStep(0)) { goTo(0); return false; }
    if (!photoPayload) { goTo(1); showPhotoError('Фотография обязательна.'); return false; }
    const consent = form.elements.personal_data_consent;
    const rules = form.elements.rules_consent;
    if (!consent.checked || !rules.checked) {
      if (!consent.checked) consent.classList.add('is-invalid');
      if (!rules.checked) rules.classList.add('is-invalid');
      status.textContent = 'Подтвердите оба согласия перед отправкой.';
      return false;
    }
    return true;
  }

  function postToIframe(params) {
    const postForm = document.createElement('form');
    postForm.method = 'POST';
    postForm.action = ENDPOINT;
    postForm.target = 'gravitation-v2-submit-frame';
    postForm.acceptCharset = 'UTF-8';
    postForm.style.display = 'none';
    for (const [name, value] of params.entries()) {
      const input = document.createElement('input');
      input.type = 'hidden'; input.name = name; input.value = value;
      postForm.appendChild(input);
    }
    document.body.appendChild(postForm);
    postForm.submit();
    postForm.remove();
  }

  function finishWithSuccess(id) {
    activeSubmission = null;
    form.hidden = true;
    document.querySelector('.v2-tabs').hidden = true;
    document.querySelector('.v2-mobile-step').hidden = true;
    progress.style.width = '100%';
    successId.textContent = id;
    success.hidden = false;
    success.scrollIntoView({behavior:'smooth', block:'center'});
  }

  function finishWithError(message) {
    activeSubmission = null;
    submit.disabled = false;
    submit.textContent = 'ОТПРАВИТЬ ЗАЯВКУ';
    status.textContent = message;
  }

  function clearStatus() {
    status.textContent = '';
    form.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid'));
  }

  function makeParticipantId() {
    const d = new Date();
    const p = n => String(n).padStart(2,'0');
    return `GR-${String(d.getFullYear()).slice(-2)}${p(d.getMonth()+1)}${p(d.getDate())}-${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}-${p(Math.floor(Math.random()*100))}`;
  }

  function fileToDataUrl(file) {
    return new Promise((resolve,reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = () => reject(reader.error || new Error('File read failed'));
      reader.readAsDataURL(file);
    });
  }

  function loadImage(src) {
    return new Promise((resolve,reject) => {
      const image = new Image();
      image.onload = () => resolve(image);
      image.onerror = () => reject(new Error('Image decode failed'));
      image.src = src;
    });
  }

  function canvasToBlob(canvas,type,quality) {
    return new Promise((resolve,reject) => canvas.toBlob(blob => blob ? resolve(blob) : reject(new Error('Image conversion failed')), type, quality));
  }

  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
  }
})();
