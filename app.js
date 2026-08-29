const CONFIG={endpoint:"https://script.google.com/macros/s/AKfycbz3LNz4si1i2wueB1I1T5AleCOaaQ-HEgBWS1Injh_mCjFmkAQqKyCqvDH3LrgzBoI/exec",fallbackForm:"https://docs.google.com/forms/d/e/1FAIpQLSe1cUBb3b0mZYz290N9ppx0CVbWQCqySiwrjBg2HCc9Y5tMmQ/viewform"};
const YUFO_CITIES=["Абинск","Адыгейск","Азов","Аксай","Алупка","Алушта","Анапа","Апшеронск","Армавир","Армянск","Астрахань","Ахтубинск","Батайск","Бахчисарай","Белая Калитва","Белогорск","Белореченск","Волгоград","Волгодонск","Волжский","Геленджик","Городовиковск","Горячий Ключ","Гуково","Гулькевичи","Джанкой","Донецк","Дубовка","Евпатория","Ейск","Жирновск","Зверево","Зерноград","Знаменск","Калач-на-Дону","Каменск-Шахтинский","Камызяк","Камышин","Керчь","Константиновск","Кореновск","Котельниково","Котово","Краснодар","Красноперекопск","Краснослободск","Красный Сулин","Кропоткин","Крымск","Курганинск","Лабинск","Лагань","Ленинск","Майкоп","Миллерово","Михайловка","Морозовск","Нариманов","Николаевск","Новоаннинский","Новокубанск","Новороссийск","Новочеркасск","Новошахтинск","Палласовка","Петров Вал","Приморско-Ахтарск","Пролетарск","Ростов-на-Дону","Саки","Сальск","Севастополь","Семикаракорск","Серафимович","Симферополь","Славянск-на-Кубани","Сочи","Старый Крым","Судак","Суровикино","Таганрог","Темрюк","Тимашёвск","Тихорецк","Туапсе","Урюпинск","Усть-Лабинск","Феодосия","Фролово","Хадыженск","Харабали","Цимлянск","Шахты","Щёлкино","Элиста","Ялта"];
const DRAFT_KEY="gravitation_application_draft_v2";

const mobileNavStyle=document.createElement("style");
mobileNavStyle.textContent=`
@media(max-width:980px){
  .site-header .brand{position:relative;z-index:3}
  .menu-toggle{z-index:3}
  .nav{z-index:2;height:100dvh;min-height:100svh;inset:0;padding:82px 20px 28px;justify-content:flex-start;gap:4px;overflow-y:auto;overscroll-behavior:contain;font-size:14px}
  .nav a{width:min(100%,360px);padding:11px 16px;text-align:center;line-height:1.3;opacity:.86}
  .nav__cta{margin-top:8px;padding:12px 18px!important}
}
@media(max-width:640px){
  .nav{padding:74px 16px 22px;gap:2px;font-size:13px}
  .nav a{padding:10px 14px}
}
`;
document.head.appendChild(mobileNavStyle);

const body=document.body,menuToggle=document.querySelector(".menu-toggle"),nav=document.querySelector(".nav"),form=document.querySelector("#application-form"),statusEl=document.querySelector("#form-status");
const yearEl=document.querySelector("#year");if(yearEl)yearEl.textContent=new Date().getFullYear();
menuToggle?.addEventListener("click",()=>{const open=body.classList.toggle("menu-open");menuToggle.setAttribute("aria-expanded",String(open));});
nav?.querySelectorAll("a").forEach(link=>link.addEventListener("click",()=>{body.classList.remove("menu-open");menuToggle?.setAttribute("aria-expanded","false");}));

function replaceWithSelect(input,values,placeholder){
  if(!input)return null;
  const select=document.createElement("select");
  [...input.attributes].forEach(attr=>{if(!["type","min","max","inputmode"].includes(attr.name))select.setAttribute(attr.name,attr.value);});
  select.innerHTML=`<option value="">${placeholder}</option>`+values.map(value=>`<option value="${value}">${value}</option>`).join("");
  input.replaceWith(select);
  return select;
}

const ageSelect=replaceWithSelect(form?.querySelector('[name="age"]'),Array.from({length:28},(_,i)=>String(i+25)),"Выбрать возраст");
const citySelect=replaceWithSelect(form?.querySelector('[name="city"]'),YUFO_CITIES,"Выбрать город");
const phoneInput=form?.querySelector('[name="phone"]');
const emailInput=form?.querySelector('[name="email"]');
if(phoneInput){phoneInput.placeholder="+7 (999) 999-99-99";phoneInput.autocomplete="tel";phoneInput.inputMode="numeric";phoneInput.maxLength=18;}
if(emailInput){emailInput.placeholder="name@example.ru";emailInput.autocomplete="email";}

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
  if(d.length>0)out+=` (${d.slice(0,3)}`;
  if(d.length>=3)out+=")";
  if(d.length>3)out+=` ${d.slice(3,6)}`;
  if(d.length>6)out+=`-${d.slice(6,8)}`;
  if(d.length>8)out+=`-${d.slice(8,10)}`;
  return out;
}
function normalizePhone(value){const d=nationalPhoneDigits(value);return d.length===10?`+7${d}`:"";}
function validatePhone(){
  if(!phoneInput)return true;
  const valid=nationalPhoneDigits(phoneInput.value).length===10;
  phoneInput.setCustomValidity(valid?"":"Введите номер в формате +7 (999) 999-99-99");
  return valid;
}
function validateEmail(){
  if(!emailInput||!emailInput.value.trim()){emailInput?.setCustomValidity("");return true;}
  const valid=/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/u.test(emailInput.value.trim());
  emailInput.setCustomValidity(valid?"":"Введите корректный email, например name@example.ru");
  return valid;
}
phoneInput?.addEventListener("input",()=>{phoneInput.value=formatPhone(phoneInput.value);validatePhone();saveDraft();});
phoneInput?.addEventListener("blur",validatePhone);
emailInput?.addEventListener("input",()=>{validateEmail();saveDraft();});
emailInput?.addEventListener("blur",validateEmail);

function getUtm(){const p=new URLSearchParams(location.search);return{utm_source:p.get("utm_source")||"",utm_medium:p.get("utm_medium")||"",utm_campaign:p.get("utm_campaign")||"",utm_content:p.get("utm_content")||"",utm_term:p.get("utm_term")||""};}
function setStatus(message,type=""){if(!statusEl)return;statusEl.textContent=message;statusEl.className=`form-status ${type?`is-${type}`:""}`;}
function draftData(){
  if(!form)return null;
  const data={saved_at:Date.now(),fields:{}};
  form.querySelectorAll("input,select,textarea").forEach(el=>{
    if(!el.name||el.name==="website")return;
    data.fields[el.name]=el.type==="checkbox"?el.checked:el.value;
  });
  return data;
}
function saveDraft(){const data=draftData();if(data)localStorage.setItem(DRAFT_KEY,JSON.stringify(data));}
function restoreDraft(){
  if(!form)return;
  try{
    const saved=JSON.parse(localStorage.getItem(DRAFT_KEY)||"null");
    if(!saved||Date.now()-Number(saved.saved_at||0)>86400000){localStorage.removeItem(DRAFT_KEY);return;}
    Object.entries(saved.fields||{}).forEach(([name,value])=>{
      const el=form.elements.namedItem(name);if(!el)return;
      if(el.type==="checkbox")el.checked=Boolean(value);else el.value=String(value??"");
    });
    if(phoneInput?.value)phoneInput.value=formatPhone(phoneInput.value);
  }catch(e){localStorage.removeItem(DRAFT_KEY);}
}
form?.addEventListener("input",event=>{if(event.target!==phoneInput&&event.target!==emailInput)saveDraft();});
form?.addEventListener("change",saveDraft);
restoreDraft();

const privacyLink=form?.querySelector('a[href="privacy.html"]');
if(privacyLink){
  privacyLink.href="privacy.html?from=application";
  privacyLink.target="_blank";
  privacyLink.rel="noopener";
  privacyLink.addEventListener("click",saveDraft);
}

form?.addEventListener("submit",async event=>{
  event.preventDefault();setStatus("");
  const phoneOk=validatePhone(),emailOk=validateEmail();
  if(!phoneOk||!emailOk||!form.reportValidity())return;
  const data=Object.fromEntries(new FormData(form).entries());
  data.phone=normalizePhone(data.phone);
  if(data.website){setStatus("Спасибо. Заявка принята.","success");form.reset();localStorage.removeItem(DRAFT_KEY);return;}
  Object.assign(data,getUtm(),{page_url:location.href,referrer:document.referrer||"",user_agent:navigator.userAgent,submitted_at_client:new Date().toISOString()});
  const btn=form.querySelector('button[type="submit"]');btn.disabled=true;btn.textContent="Отправляем…";
  if(!CONFIG.endpoint){localStorage.setItem("gravitation_pending_application",JSON.stringify(data));saveDraft();setStatus("Канал сайта в Google Sheets ещё не опубликован. Открываю резервную анкету.","success");setTimeout(()=>window.open(CONFIG.fallbackForm,"_blank","noopener"),700);btn.disabled=false;btn.textContent="Отправить заявку";return;}
  try{
    const payload=new URLSearchParams(data);
    await fetch(CONFIG.endpoint,{method:"POST",mode:"no-cors",headers:{"Content-Type":"application/x-www-form-urlencoded;charset=UTF-8"},body:payload});
    form.reset();localStorage.removeItem(DRAFT_KEY);localStorage.removeItem("gravitation_pending_application");setStatus("Заявка отправлена. Мы свяжемся с тобой после короткого просмотра анкеты.","success");
  }catch(error){console.error(error);localStorage.setItem("gravitation_pending_application",JSON.stringify(data));saveDraft();setStatus("Не удалось отправить заявку. Данные сохранены в этом браузере.","error");}
  finally{btn.disabled=false;btn.textContent="Отправить заявку";}
});
