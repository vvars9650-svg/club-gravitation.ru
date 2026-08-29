const CONFIG={endpoint:"https://script.google.com/macros/s/AKfycbz3LNz4si1i2wueB1I1T5AleCOaaQ-HEgBWS1Injh_mCjFmkAQqKyCqvDH3LrgzBoI/exec"};
const YUFO_CITIES=["Абинск","Адыгейск","Азов","Аксай","Алупка","Алушта","Анапа","Апшеронск","Армавир","Армянск","Астрахань","Ахтубинск","Батайск","Бахчисарай","Белая Калитва","Белогорск","Белореченск","Волгоград","Волгодонск","Волжский","Геленджик","Городовиковск","Горячий Ключ","Гуково","Гулькевичи","Джанкой","Донецк","Дубовка","Евпатория","Ейск","Жирновск","Зверево","Зерноград","Знаменск","Инкерман","Калач-на-Дону","Каменск-Шахтинский","Камызяк","Камышин","Керчь","Константиновск","Кореновск","Котельниково","Котово","Краснодар","Красноперекопск","Краснослободск","Красный Сулин","Кропоткин","Крымск","Курганинск","Лабинск","Лагань","Ленинск","Майкоп","Миллерово","Михайловка","Морозовск","Нариманов","Николаевск","Новоаннинский","Новокубанск","Новороссийск","Новочеркасск","Новошахтинск","Палласовка","Петров Вал","Приморско-Ахтарск","Пролетарск","Ростов-на-Дону","Саки","Сальск","Севастополь","Семикаракорск","Серафимович","Симферополь","Славянск-на-Кубани","Сочи","Старый Крым","Судак","Суровикино","Таганрог","Темрюк","Тимашёвск","Тихорецк","Туапсе","Урюпинск","Усть-Лабинск","Феодосия","Фролово","Хадыженск","Харабали","Цимлянск","Шахты","Щёлкино","Элиста","Ялта"];
const DRAFT_KEY="gravitation_application_draft_v3";
const MAX_PHOTO_BYTES=10*1024*1024;

if(!document.querySelector('link[href="wizard.css"]')){
  const wizardStyles=document.createElement("link");
  wizardStyles.rel="stylesheet";
  wizardStyles.href="wizard.css";
  document.head.appendChild(wizardStyles);
}

const body=document.body;
const menuToggle=document.querySelector(".menu-toggle");
const nav=document.querySelector(".nav");
const yearEl=document.querySelector("#year");
const originalForm=document.querySelector("#application-form");
if(yearEl)yearEl.textContent=new Date().getFullYear();

menuToggle?.addEventListener("click",()=>{
  const open=body.classList.toggle("menu-open");
  menuToggle.setAttribute("aria-expanded",String(open));
});
nav?.querySelectorAll("a").forEach(link=>link.addEventListener("click",()=>{
  body.classList.remove("menu-open");
  menuToggle?.setAttribute("aria-expanded","false");
}));

if(originalForm)setupApplicationWizard(originalForm);

function setupApplicationWizard(form){
  const ageOptions=Array.from({length:28},(_,i)=>i+25).map(v=>`<option value="${v}">${v}</option>`).join("");
  const cityOptions=YUFO_CITIES.map(v=>`<option value="${v}">${v}</option>`).join("");

  const shell=document.createElement("div");
  shell.className="wizard-shell";
  form.parentNode.insertBefore(shell,form);
  shell.appendChild(form);
  form.classList.add("application-form--wizard");
  form.noValidate=true;

  shell.insertAdjacentHTML("afterbegin",`
    <div class="wizard-progress" aria-hidden="true"><span id="wizard-progress-bar"></span></div>
    <div class="wizard-mobile-step" id="wizard-mobile-step">Шаг 1 из 6 · Контакты</div>
    <nav class="wizard-tabs" aria-label="Этапы анкеты">
      <button type="button" class="wizard-tab is-active" data-step-target="0"><span>1.</span> Контакты</button>
      <button type="button" class="wizard-tab" data-step-target="1"><span>2.</span> Фото</button>
      <button type="button" class="wizard-tab" data-step-target="2"><span>3.</span> О вас</button>
      <button type="button" class="wizard-tab" data-step-target="3"><span>4.</span> Знакомства</button>
      <button type="button" class="wizard-tab" data-step-target="4"><span>5.</span> Формат</button>
      <button type="button" class="wizard-tab" data-step-target="5"><span>6.</span> Проверка</button>
    </nav>
  `);

  form.innerHTML=`
    <section class="wizard-step is-active" data-step="0">
      <p class="wizard-kicker">1. Контактная информация</p>
      <h3 class="wizard-title">Начнём с простого</h3>
      <div class="form-grid">
        <label><span>Имя и фамилия *</span><input name="name" autocomplete="name" required></label>
        <label><span>Возраст *</span><select name="age" required><option value="">Выбрать возраст</option>${ageOptions}</select></label>
        <label><span>Пол *</span><select name="gender" required><option value="">Выбрать</option><option>Мужчина</option><option>Женщина</option><option>Предпочитаю обсудить лично</option></select></label>
        <label><span>Город *</span><select name="city" required><option value="">Выбрать город</option>${cityOptions}</select></label>
        <label class="city-visit-field is-hidden"><span>Сможете посещать встречи в Краснодаре? *</span><select name="city_visit"><option value="">Выбрать</option><option>Да, регулярно</option><option>Да, время от времени</option><option>Пока не уверен(а)</option></select></label>
        <label><span>Телефон *</span><input name="phone" type="tel" inputmode="numeric" autocomplete="tel" placeholder="+7 999 999-99-99" maxlength="16" required></label>
        <label><span>Telegram</span><input name="telegram" placeholder="@username"></label>
        <label><span>Email</span><input name="email" type="email" placeholder="name@example.ru" autocomplete="email"></label>
        <label><span>Как удобнее связаться?</span><select name="preferred_contact"><option value="">Выбрать</option><option>Telegram</option><option>Телефон</option><option>Email</option><option>WhatsApp</option></select></label>
      </div>
    </section>

    <section class="wizard-step" data-step="1">
      <p class="wizard-kicker">2. Фотография</p>
      <h3 class="wizard-title">Добавьте свою фотографию</h3>
      <p class="wizard-help">Загрузите фотографию, на которой хорошо видно вас. Она нужна только организаторам клуба и не публикуется на сайте.</p>
      <label class="photo-upload" id="photo-upload">
        <input type="file" name="photo" id="photo-input" accept="image/jpeg,image/png,image/webp,image/heic,image/heif" required>
        <span class="photo-upload__preview" id="photo-preview"><span>＋</span></span>
        <span class="photo-upload__copy"><strong>Выбрать фотографию</strong><small>JPG, PNG, WEBP. До 10 МБ; большие изображения мы уменьшим автоматически.</small><small id="photo-file-name"></small></span>
      </label>
      <p class="field-error" id="photo-error" role="alert"></p>
    </section>

    <section class="wizard-step" data-step="2">
      <p class="wizard-kicker">3. О вас</p>
      <h3 class="wizard-title">Чуть больше, чем должность и статус</h3>
      <label><span>Чем вы занимаетесь сейчас?</span><textarea name="occupation" rows="3"></textarea></label>
      <label><span>Чем наполнена ваша жизнь кроме работы?</span><textarea name="life_beyond_work" rows="3"></textarea></label>
      <label><span>Что вам интересно вне работы?</span><textarea name="interests" rows="3"></textarea></label>
      <label><span>Что вас зацепило в идее «Гравитации»?</span><textarea name="interest_reason" rows="4"></textarea></label>
      <label><span>Чего хотелось бы получить от первой встречи?</span><textarea name="expectations" rows="4"></textarea></label>
    </section>

    <section class="wizard-step" data-step="3">
      <p class="wizard-kicker">4. Знакомства</p>
      <h3 class="wizard-title">Какие связи вам сейчас важны</h3>
      <label><span>Как бы вы описали свой текущий контекст отношений?</span><select name="relationship_context"><option value="">Можно не отвечать</option><option>Свободен / свободна</option><option>В отношениях</option><option>Женат / замужем</option><option>В процессе изменений</option><option>Предпочитаю обсудить лично</option></select></label>
      <fieldset class="choice-group"><legend>Какие знакомства вам сейчас интересны?</legend>
        <label class="choice-card"><input type="checkbox" name="connection_goal" value="Романтические отношения"><span>Романтические отношения</span></label>
        <label class="choice-card"><input type="checkbox" name="connection_goal" value="Новые друзья"><span>Новые друзья</span></label>
        <label class="choice-card"><input type="checkbox" name="connection_goal" value="Близкие по духу люди"><span>Близкие по духу люди</span></label>
        <label class="choice-card"><input type="checkbox" name="connection_goal" value="Партнёрство / бизнес"><span>Партнёрство / бизнес</span></label>
        <label class="choice-card"><input type="checkbox" name="connection_goal" value="Творческие и совместные проекты"><span>Творческие и совместные проекты</span></label>
        <label class="choice-card"><input type="checkbox" name="connection_goal" value="Новый круг общения и впечатления"><span>Новый круг общения и впечатления</span></label>
        <label class="choice-card"><input type="checkbox" name="connection_goal" value="Интересные люди без заданной цели"><span>Интересные люди без заданной цели</span></label>
      </fieldset>
      <label><span>Что вы особенно цените в людях?</span><textarea name="values_people" rows="3"></textarea></label>
      <label><span>Что обычно мешает вам знакомиться с новыми людьми?</span><textarea name="meeting_barriers" rows="3"></textarea></label>
      <div class="form-grid">
        <label><span>Комфорт в новой компании</span><select name="social_comfort"><option value="">Выбрать</option><option>1 — мне сложно</option><option>2</option><option>3 — нормально</option><option>4</option><option>5 — чувствую себя легко</option></select></label>
        <label><span>Легко ли первым начать разговор?</span><select name="initiative"><option value="">Выбрать</option><option>1 — почти никогда</option><option>2</option><option>3 — зависит от ситуации</option><option>4</option><option>5 — легко</option></select></label>
      </div>
      <label><span>Какой способ знакомства для вас наиболее естественный?</span><select name="introduction_scenario"><option value="">Выбрать</option><option>Через общее дело или занятие</option><option>Через живой разговор</option><option>Через игру или активность</option><option>Когда знакомят друзья</option><option>Когда первый шаг делает другой человек</option><option>Зависит от человека и ситуации</option></select></label>
    </section>

    <section class="wizard-step" data-step="4">
      <p class="wizard-kicker">5. Формат встреч</p>
      <h3 class="wizard-title">Что создаёт хороший вечер именно для вас</h3>
      <label><span>Как для вас выглядит действительно удачный вечер в таком клубе?</span><textarea name="successful_evening" rows="3"></textarea></label>
      <label><span>Что должно произойти, чтобы захотелось прийти снова?</span><textarea name="return_reason" rows="3"></textarea></label>
      <label><span>Какое поведение других участников для вас неприемлемо?</span><textarea name="unacceptable_behavior" rows="3"></textarea></label>
      <fieldset class="choice-group"><legend>В какие дни вам обычно удобнее участвовать?</legend>
        <label class="choice-card"><input type="checkbox" name="convenient_days" value="Будни"><span>Будни</span></label>
        <label class="choice-card"><input type="checkbox" name="convenient_days" value="Пятница"><span>Пятница</span></label>
        <label class="choice-card"><input type="checkbox" name="convenient_days" value="Суббота"><span>Суббота</span></label>
        <label class="choice-card"><input type="checkbox" name="convenient_days" value="Воскресенье"><span>Воскресенье</span></label>
        <label class="choice-card"><input type="checkbox" name="convenient_days" value="Зависит от мероприятия"><span>Зависит от мероприятия</span></label>
      </fieldset>
      <div class="form-grid">
        <label><span>Комфортная стоимость участия</span><select name="comfortable_price"><option value="">Пока не знаю</option><option>до 2 000 ₽</option><option>2 000–3 500 ₽</option><option>3 500–5 000 ₽</option><option>5 000 ₽ и выше</option><option>Зависит от формата</option></select></label>
        <label><span>Откуда вы узнали о нас?</span><select name="source"><option value="">Выбрать</option><option>Сайт / поиск</option><option>От знакомого / рекомендация</option><option>Telegram</option><option>Социальные сети</option><option>Сайт знакомств</option><option>Другое</option></select></label>
      </div>
    </section>

    <section class="wizard-step" data-step="5">
      <p class="wizard-kicker">6. Проверка</p>
      <h3 class="wizard-title">Посмотрите заявку перед отправкой</h3>
      <div class="review-list" id="review-list"></div>
      <div class="review-consents">
        <label class="consent"><input type="checkbox" name="personal_data_consent" value="Да" required><span>Согласен(на) на обработку персональных данных и с <a href="privacy.html?from=application" target="_blank" rel="noopener">политикой конфиденциальности</a>.</span></label>
        <label class="consent"><input type="checkbox" name="rules_consent" value="Да" required><span>Понимаю, что заявка не гарантирует участие, и обязуюсь уважать личные границы других участников.</span></label>
      </div>
      <input class="honeypot" type="text" name="website" tabindex="-1" autocomplete="off" aria-hidden="true">
      <button class="button button--primary button--submit" type="submit">Отправить заявку</button>
      <p class="form-status" id="form-status" role="status" aria-live="polite"></p>
    </section>

    <div class="wizard-actions" id="wizard-actions">
      <button type="button" class="wizard-back" id="wizard-back">← Назад</button>
      <button type="button" class="button button--primary wizard-next" id="wizard-next">Далее</button>
    </div>
  `;

  shell.insertAdjacentHTML("beforeend",`
    <div class="application-success" id="application-success" hidden>
      <div class="application-success__mark">✓</div>
      <p class="eyebrow">ГРАВИТАЦИЯ</p>
      <h3>Ваша заявка отправлена</h3>
      <p>Спасибо. Мы познакомимся с ней и свяжемся с вами после короткого просмотра.</p>
      <p class="application-success__id-label">Ваш номер участника</p>
      <strong class="application-success__id" id="application-success-id"></strong>
      <p class="application-success__note">Сохраните этот номер.</p>
    </div>
  `);

  const statusEl=form.querySelector("#form-status");
  const steps=[...form.querySelectorAll(".wizard-step")];
  const tabs=[...shell.querySelectorAll(".wizard-tab")];
  const progressBar=shell.querySelector("#wizard-progress-bar");
  const mobileStep=shell.querySelector("#wizard-mobile-step");
  const backBtn=form.querySelector("#wizard-back");
  const nextBtn=form.querySelector("#wizard-next");
  const actions=form.querySelector("#wizard-actions");
  const reviewList=form.querySelector("#review-list");
  const successBox=shell.querySelector("#application-success");
  const successId=shell.querySelector("#application-success-id");
  const phoneInput=form.querySelector('[name="phone"]');
  const emailInput=form.querySelector('[name="email"]');
  const citySelect=form.querySelector('[name="city"]');
  const cityVisitField=form.querySelector(".city-visit-field");
  const cityVisitSelect=form.querySelector('[name="city_visit"]');
  const photoInput=form.querySelector("#photo-input");
  const photoUpload=form.querySelector("#photo-upload");
  const photoPreview=form.querySelector("#photo-preview");
  const photoFileName=form.querySelector("#photo-file-name");
  const photoError=form.querySelector("#photo-error");

  let currentStep=0;
  let maxVisited=0;
  const completedSteps=new Set();
  let photoPayload=null;
  let photoPreviewUrl="";

  function setStatus(message,type=""){
    statusEl.textContent=message;
    statusEl.className=`form-status ${type?`is-${type}`:""}`;
  }

  function nationalPhoneDigits(value){
    const raw=String(value||"");
    let digits=raw.replace(/\D/g,"");
    if(raw.trim().startsWith("+7"))digits=digits.slice(1);
    else if(digits.length===11&&(digits.startsWith("7")||digits.startsWith("8")))digits=digits.slice(1);
    return digits.slice(0,10);
  }
  function formatPhone(value){
    const d=nationalPhoneDigits(value);
    if(!d)return "";
    let out="+7";
    if(d.length>0)out+=` ${d.slice(0,3)}`;
    if(d.length>3)out+=` ${d.slice(3,6)}`;
    if(d.length>6)out+=`-${d.slice(6,8)}`;
    if(d.length>8)out+=`-${d.slice(8,10)}`;
    return out;
  }
  function normalizePhone(value){
    const d=nationalPhoneDigits(value);
    return d.length===10?`+7${d}`:"";
  }
  function validatePhone(){
    const valid=nationalPhoneDigits(phoneInput.value).length===10;
    phoneInput.setCustomValidity(valid?"":"Введите номер в формате +7 999 999-99-99");
    phoneInput.classList.toggle("is-invalid",!valid);
    return valid;
  }
  function validateEmail(){
    if(!emailInput.value.trim()){
      emailInput.setCustomValidity("");
      emailInput.classList.remove("is-invalid");
      return true;
    }
    const valid=/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/u.test(emailInput.value.trim());
    emailInput.setCustomValidity(valid?"":"Введите корректный email, например name@example.ru");
    emailInput.classList.toggle("is-invalid",!valid);
    return valid;
  }
  phoneInput.addEventListener("input",()=>{phoneInput.value=formatPhone(phoneInput.value);validatePhone();saveDraft();});
  phoneInput.addEventListener("blur",validatePhone);
  emailInput.addEventListener("input",()=>{validateEmail();saveDraft();});
  emailInput.addEventListener("blur",validateEmail);

  function syncCityVisit(){
    const needsAnswer=Boolean(citySelect.value&&citySelect.value!=="Краснодар");
    cityVisitField.classList.toggle("is-hidden",!needsAnswer);
    cityVisitSelect.required=needsAnswer;
    if(!needsAnswer){
      cityVisitSelect.value="";
      cityVisitSelect.setCustomValidity("");
      cityVisitSelect.classList.remove("is-invalid");
    }
  }
  citySelect.addEventListener("change",()=>{syncCityVisit();saveDraft();});

  async function fileToBitmap(file){
    if("createImageBitmap" in window)return await createImageBitmap(file);
    return await new Promise((resolve,reject)=>{
      const img=new Image();
      const url=URL.createObjectURL(file);
      img.onload=()=>{URL.revokeObjectURL(url);resolve(img);};
      img.onerror=()=>{URL.revokeObjectURL(url);reject(new Error("decode"));};
      img.src=url;
    });
  }
  function canvasToBlob(canvas,type,quality){return new Promise(resolve=>canvas.toBlob(resolve,type,quality));}
  function blobToDataUrl(blob){
    return new Promise((resolve,reject)=>{
      const reader=new FileReader();
      reader.onload=()=>resolve(String(reader.result||""));
      reader.onerror=reject;
      reader.readAsDataURL(blob);
    });
  }
  async function preparePhoto(file){
    if(!file)throw new Error("Выберите фотографию");
    if(file.size>MAX_PHOTO_BYTES)throw new Error("Файл больше 10 МБ. Выберите фотографию меньшего размера.");
    if(!String(file.type||"").startsWith("image/"))throw new Error("Нужен файл изображения.");
    let bitmap;
    try{bitmap=await fileToBitmap(file);}
    catch(e){throw new Error("Этот формат фотографии не поддерживается браузером. Выберите JPG, PNG или WEBP.");}
    const width=bitmap.width||bitmap.naturalWidth;
    const height=bitmap.height||bitmap.naturalHeight;
    const maxSide=1600;
    const scale=Math.min(1,maxSide/Math.max(width,height));
    const canvas=document.createElement("canvas");
    canvas.width=Math.max(1,Math.round(width*scale));
    canvas.height=Math.max(1,Math.round(height*scale));
    const ctx=canvas.getContext("2d",{alpha:false});
    ctx.fillStyle="#fff";
    ctx.fillRect(0,0,canvas.width,canvas.height);
    ctx.drawImage(bitmap,0,0,canvas.width,canvas.height);
    if(bitmap.close)bitmap.close();
    const blob=await canvasToBlob(canvas,"image/jpeg",.84);
    if(!blob)throw new Error("Не удалось подготовить фотографию.");
    const dataUrl=await blobToDataUrl(blob);
    const base64=dataUrl.split(",")[1]||"";
    const cleanStem=(file.name||"photo").replace(/\.[^.]+$/,"").replace(/[^\p{L}\p{N}_-]+/gu,"-").slice(0,70)||"photo";
    return {data:base64,mime:"image/jpeg",name:`${cleanStem}.jpg`,size:blob.size,preview:dataUrl};
  }
  photoInput.addEventListener("change",async()=>{
    photoError.textContent="";
    photoUpload.classList.remove("is-invalid");
    const file=photoInput.files?.[0];
    if(!file){photoPayload=null;return;}
    photoFileName.textContent="Подготавливаем изображение…";
    try{
      photoPayload=await preparePhoto(file);
      photoPreviewUrl=photoPayload.preview;
      photoPreview.innerHTML=`<img src="${photoPreviewUrl}" alt="Предпросмотр фотографии">`;
      photoFileName.textContent=`${file.name} · ${Math.max(1,Math.round(photoPayload.size/1024))} КБ после оптимизации`;
      completedSteps.delete(1);
    }catch(err){
      photoPayload=null;
      photoInput.value="";
      photoPreview.innerHTML="<span>＋</span>";
      photoFileName.textContent="";
      photoError.textContent=err.message||"Не удалось обработать фотографию.";
      photoUpload.classList.add("is-invalid");
    }
    saveDraft();
  });

  function fieldNames(){
    return [...new Set([...form.elements].map(el=>el.name).filter(Boolean).filter(name=>name!=="photo"&&name!=="website"))];
  }
  function serializeFields(){
    const fd=new FormData(form);
    const out={};
    fieldNames().forEach(name=>{
      const els=[...form.querySelectorAll(`[name="${CSS.escape(name)}"]`)];
      if(els.length>1&&els.every(el=>el.type==="checkbox"))out[name]=fd.getAll(name).map(String);
      else if(els[0]?.type==="checkbox")out[name]=els[0].checked?String(els[0].value||"Да"):"";
      else out[name]=String(fd.get(name)??"");
    });
    return out;
  }
  function saveDraft(){
    try{
      localStorage.setItem(DRAFT_KEY,JSON.stringify({saved_at:Date.now(),current_step:currentStep,max_visited:maxVisited,fields:serializeFields()}));
    }catch(e){}
  }
  function restoreDraft(){
    try{
      const saved=JSON.parse(localStorage.getItem(DRAFT_KEY)||"null");
      if(!saved||Date.now()-Number(saved.saved_at||0)>2*86400000){localStorage.removeItem(DRAFT_KEY);return;}
      Object.entries(saved.fields||{}).forEach(([name,value])=>{
        const els=[...form.querySelectorAll(`[name="${CSS.escape(name)}"]`)];
        if(!els.length)return;
        if(els.length>1&&els.every(el=>el.type==="checkbox")){
          const values=Array.isArray(value)?value:[value];
          els.forEach(el=>el.checked=values.includes(el.value));
        }else if(els[0].type==="checkbox")els[0].checked=Boolean(value);
        else els[0].value=String(value??"");
      });
      if(phoneInput.value)phoneInput.value=formatPhone(phoneInput.value);
      currentStep=Math.min(Number(saved.current_step||0),1);
      maxVisited=Math.max(currentStep,Math.min(Number(saved.max_visited||0),1));
    }catch(e){localStorage.removeItem(DRAFT_KEY);}
  }
  form.addEventListener("input",event=>{if(![photoInput,phoneInput,emailInput].includes(event.target))saveDraft();});
  form.addEventListener("change",event=>{if(event.target!==photoInput)saveDraft();});

  function markInvalid(el){
    el.classList.add("is-invalid");
    el.addEventListener("input",()=>el.classList.remove("is-invalid"),{once:true});
    el.addEventListener("change",()=>el.classList.remove("is-invalid"),{once:true});
  }
  function validateRequiredInStep(stepIndex){
    const step=steps[stepIndex];
    if(!step)return true;
    let firstInvalid=null;
    [...step.querySelectorAll("[required]")].forEach(el=>{
      if(el===photoInput)return;
      if(!el.checkValidity()){markInvalid(el);if(!firstInvalid)firstInvalid=el;}
    });
    if(stepIndex===0){
      if(!validatePhone()&&!firstInvalid)firstInvalid=phoneInput;
      if(!validateEmail()&&!firstInvalid)firstInvalid=emailInput;
    }
    if(stepIndex===1&&!photoPayload){
      photoUpload.classList.add("is-invalid");
      photoError.textContent="Добавьте фотографию, чтобы продолжить.";
      firstInvalid=firstInvalid||photoInput;
    }
    if(firstInvalid){
      if(firstInvalid!==photoInput)firstInvalid.reportValidity?.();
      (firstInvalid.closest("label,fieldset")||firstInvalid).scrollIntoView({behavior:"smooth",block:"center"});
      return false;
    }
    return true;
  }
  function validateAll(){
    for(let i=0;i<steps.length-1;i++){
      if(!validateRequiredInStep(i)){showStep(i);return false;}
    }
    const invalid=[...steps[5].querySelectorAll("[required]")].find(el=>!el.checkValidity());
    if(invalid){markInvalid(invalid);invalid.reportValidity();return false;}
    return true;
  }

  const STEP_TITLES=["Контакты","Фото","О вас","Знакомства","Формат","Проверка"];
  function showStep(index,opts={}){
    currentStep=Math.max(0,Math.min(index,steps.length-1));
    maxVisited=Math.max(maxVisited,currentStep);
    steps.forEach((step,i)=>step.classList.toggle("is-active",i===currentStep));
    tabs.forEach((tab,i)=>{
      tab.classList.toggle("is-active",i===currentStep);
      tab.classList.toggle("is-complete",completedSteps.has(i));
      tab.disabled=i>maxVisited;
    });
    progressBar.style.width=`${((currentStep+1)/steps.length)*100}%`;
    mobileStep.textContent=`Шаг ${currentStep+1} из ${steps.length} · ${STEP_TITLES[currentStep]}`;
    backBtn.hidden=currentStep===0;
    nextBtn.hidden=currentStep===steps.length-1;
    nextBtn.textContent=currentStep===steps.length-2?"Проверить заявку":"Далее";
    actions.hidden=currentStep===steps.length-1;
    if(currentStep===5)renderReview();
    tabs[currentStep]?.scrollIntoView({behavior:"smooth",inline:"center",block:"nearest"});
    saveDraft();
    if(opts.scroll)shell.scrollIntoView({behavior:"smooth",block:"start"});
  }
  nextBtn.addEventListener("click",()=>{
    if(!validateRequiredInStep(currentStep))return;
    completedSteps.add(currentStep);
    showStep(currentStep+1,{scroll:true});
  });
  backBtn.addEventListener("click",()=>showStep(currentStep-1,{scroll:true}));
  tabs.forEach((tab,i)=>tab.addEventListener("click",()=>{if(i<=maxVisited)showStep(i,{scroll:true});}));

  const REVIEW_GROUPS=[
    {title:"Контактная информация",step:0,items:[["Имя и фамилия","name"],["Возраст","age"],["Пол","gender"],["Город","city"],["Посещение Краснодара","city_visit"],["Телефон","phone"],["Telegram","telegram"],["Email","email"],["Связаться через","preferred_contact"]]},
    {title:"Фотография",step:1,photo:true},
    {title:"О вас",step:2,items:[["Чем занимаетесь","occupation"],["Жизнь кроме работы","life_beyond_work"],["Интересы","interests"],["Что зацепило","interest_reason"],["Ожидания от первой встречи","expectations"]]},
    {title:"Знакомства",step:3,items:[["Контекст отношений","relationship_context"],["Интересующие знакомства","connection_goal"],["Что цените в людях","values_people"],["Что мешает знакомиться","meeting_barriers"],["Комфорт в новой компании","social_comfort"],["Инициативность","initiative"],["Естественный способ знакомства","introduction_scenario"]]},
    {title:"Формат встреч",step:4,items:[["Удачный вечер","successful_evening"],["Что заставит вернуться","return_reason"],["Неприемлемое поведение","unacceptable_behavior"],["Удобные дни","convenient_days"],["Комфортная стоимость","comfortable_price"],["Источник","source"]]}
  ];
  function displayValue(value){if(Array.isArray(value))return value.length?value.join(", "):"—";const text=String(value||"").trim();return text||"—";}
  function renderReview(){
    const data=serializeFields();
    reviewList.innerHTML=REVIEW_GROUPS.map(group=>{
      let content;
      if(group.photo)content=`<div class="review-photo">${photoPreviewUrl?`<img src="${photoPreviewUrl}" alt="">`:""}<span>${photoPayload?"Фотография добавлена":"Фотография не добавлена"}</span></div>`;
      else content=`<dl>${group.items.filter(([_,key])=>!(key==="city_visit"&&data.city==="Краснодар")).map(([label,key])=>`<dt>${label}</dt><dd>${displayValue(data[key])}</dd>`).join("")}</dl>`;
      return `<article class="review-block"><div class="review-block__head"><strong>${group.title}</strong><button type="button" class="review-edit" data-review-step="${group.step}">Изменить</button></div>${content}</article>`;
    }).join("");
    reviewList.querySelectorAll("[data-review-step]").forEach(btn=>btn.addEventListener("click",()=>showStep(Number(btn.dataset.reviewStep),{scroll:true})));
  }

  function getUtm(){
    const p=new URLSearchParams(location.search);
    return{utm_source:p.get("utm_source")||"",utm_medium:p.get("utm_medium")||"",utm_campaign:p.get("utm_campaign")||"",utm_content:p.get("utm_content")||"",utm_term:p.get("utm_term")||""};
  }
  function moscowParts(date=new Date()){
    const parts=new Intl.DateTimeFormat("en-GB",{timeZone:"Europe/Moscow",year:"2-digit",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",second:"2-digit",hour12:false}).formatToParts(date);
    return Object.fromEntries(parts.filter(p=>p.type!=="literal").map(p=>[p.type,p.value]));
  }
  function generateParticipantId(){
    const p=moscowParts();
    const random=String(Math.floor(Math.random()*100)).padStart(2,"0");
    return `GR-${p.year}${p.month}${p.day}-${p.hour}${p.minute}${p.second}-${random}`;
  }

  form.querySelectorAll('a[href^="privacy.html"]').forEach(link=>link.addEventListener("click",saveDraft));

  form.addEventListener("submit",async event=>{
    event.preventDefault();
    setStatus("");
    if(!validateAll())return;
    if(!CONFIG.endpoint){setStatus("Сервис заявок временно недоступен. Попробуйте немного позже.","error");return;}
    if(!photoPayload){showStep(1,{scroll:true});photoError.textContent="Добавьте фотографию, чтобы отправить заявку.";return;}
    const data=serializeFields();
    data.phone=normalizePhone(data.phone);
    data.city_visit=data.city==="Краснодар"?"Краснодар":data.city_visit;
    data.participant_id=generateParticipantId();
    data.photo_data=photoPayload.data;
    data.photo_name=photoPayload.name;
    data.photo_type=photoPayload.mime;
    Object.assign(data,getUtm(),{page_url:location.href,referrer:document.referrer||"",user_agent:navigator.userAgent,submitted_at_client:new Date().toISOString()});
    Object.keys(data).forEach(key=>{if(Array.isArray(data[key]))data[key]=data[key].join(" | ");});
    if(data.website)return;
    const submitBtn=form.querySelector('button[type="submit"]');
    submitBtn.disabled=true;
    submitBtn.textContent="Отправляем…";
    try{
      const payload=new URLSearchParams(data);
      await fetch(CONFIG.endpoint,{method:"POST",mode:"no-cors",headers:{"Content-Type":"application/x-www-form-urlencoded;charset=UTF-8"},body:payload});
      localStorage.removeItem(DRAFT_KEY);
      form.hidden=true;
      shell.querySelector(".wizard-tabs").hidden=true;
      shell.querySelector(".wizard-mobile-step").hidden=true;
      shell.querySelector(".wizard-progress").hidden=true;
      successId.textContent=data.participant_id;
      successBox.hidden=false;
      successBox.scrollIntoView({behavior:"smooth",block:"center"});
    }catch(error){
      console.error(error);
      saveDraft();
      setStatus("Не удалось отправить заявку. Проверьте интернет и попробуйте ещё раз.","error");
    }finally{
      submitBtn.disabled=false;
      submitBtn.textContent="Отправить заявку";
    }
  });

  restoreDraft();
  syncCityVisit();
  showStep(currentStep);
}
