'use strict';
const LEGAL_VERSIONS={privacy:'PPD-2.1',consent:'CONSENT-PD-2.1'};
const FORM_VERSION='FORM-2.2';
const FORM_FIELDS=['full_name','age','gender','city','visit_krasnodar','phone','email','preferred_contact','profile_or_messenger_url','public_profile_url','occupation','life_outside_work','what_interested','what_participant_brings','what_friends_value','desired_connections','desired_connections_other','values_in_people','barriers_to_meeting','acquaintance_methods','acquaintance_methods_other','return_reason','source'];
const REMOVED_FIELDS=['telegram','interests','event_expectations','social_comfort','initiative','acquaintance_scenario','successful_evening','unacceptable_behavior','convenient_days','comfortable_price'];
const DESIRED=['Романтические отношения','Новые друзья','Близкие по духу люди','Партнёрство / бизнес','Творческие и совместные проекты','Новый круг общения и впечатления','Интересные люди без заданной цели','Весело провести время','Другое'];
const METHODS=['Через общее дело или занятие','Через живой разговор','Через игру или активность','Когда знакомят друзья','Когда первый шаг делает другой человек','Зависит от человека и ситуации','Другое'];
const SOURCES=['Сайт / поиск','От знакомого / рекомендация','Мессенджер','Социальные сети','Сайт знакомств','Другое'];
function reply(statusCode,body){return {statusCode,headers:{'content-type':'application/json; charset=utf-8'},body:JSON.stringify(body)};}
function parse(event){if(event?.httpMethod!=='POST')throw Error('method_not_allowed');if(!String(event.headers?.['content-type']||event.headers?.['Content-Type']||'').toLowerCase().startsWith('application/json'))throw Error('unsupported_media_type');return typeof event.body==='string'?JSON.parse(event.body):event.body;}
function phone(value){const raw=String(value||'').trim();if(!raw||/[^\d+\s()-]/u.test(raw)||(raw.includes('+')&&!/^\+\d/u.test(raw))||(raw.startsWith('+')&&!raw.startsWith('+7'))||(raw.match(/\+/gu)||[]).length>1)return null;let digits=raw.replace(/\D/gu,'');if(digits.length===11){if(!/^[78]/u.test(digits))return null;digits=digits.slice(1);}return /^\d{10}$/u.test(digits)?'+7'+digits:null;}
function validMulti(value,allowed){return Array.isArray(value)&&value.length>0&&new Set(value).size===value.length&&value.every(item=>allowed.includes(item));}
function validUrl(value){if(!value)return true;try{return /^https?:$/u.test(new URL(value).protocol);}catch{return false;}}
function validate(d){
  if(!d||typeof d!=='object'||Array.isArray(d))return'invalid_json';
  if(d.form_version!==FORM_VERSION)return'invalid_form_version';
  if(d.policy_acknowledged!==true)return'policy_acknowledgement_required';
  if(d.personal_data_consent!==true)return'consent_required';
  if(d.consent_version!==LEGAL_VERSIONS.consent||d.policy_version!==LEGAL_VERSIONS.privacy)return'invalid_legal_versions';
  if(d.website)return'bot_detected';
  if(REMOVED_FIELDS.some(field=>Object.hasOwn(d,field)))return'legacy_form_fields_not_allowed';
  for(const key of ['full_name','age','gender','city','phone','email','occupation','life_outside_work','source'])if(!String(d[key]||'').trim())return'missing_'+key;
  if(!Number.isInteger(+d.age)||+d.age<25||+d.age>52)return'invalid_age';
  if(!['Мужчина','Женщина'].includes(d.gender))return'invalid_gender';
  if(!phone(d.phone))return'invalid_phone';
  if(!/^[^\s@]+@[^\s@]+\.[^\s@]+$/u.test(d.email))return'invalid_email';
  const visits=['Да, регулярно','Да, время от времени','Пока не уверен(а)'];
  if(d.city!=='Краснодар'&&!visits.includes(d.visit_krasnodar))return d.visit_krasnodar?'invalid_visit_krasnodar':'missing_visit_krasnodar';
  if(d.city==='Краснодар'&&d.visit_krasnodar)return'invalid_visit_krasnodar';
  if(!['','по телефону','по email','через профиль или мессенджер по указанной ссылке'].includes(d.preferred_contact||''))return'invalid_preferred_contact';
  if(!validUrl(d.profile_or_messenger_url))return'invalid_profile_or_messenger_url';
  if(!validUrl(d.public_profile_url))return'invalid_public_profile_url';
  if(!validMulti(d.desired_connections,DESIRED))return'invalid_desired_connections';
  if(!validMulti(d.acquaintance_methods,METHODS))return'invalid_acquaintance_methods';
  if(d.desired_connections.includes('Другое')&&!String(d.desired_connections_other||'').trim())return'missing_desired_connections_other';
  if(!d.desired_connections.includes('Другое')&&String(d.desired_connections_other||'').trim())return'unexpected_desired_connections_other';
  if(d.acquaintance_methods.includes('Другое')&&!String(d.acquaintance_methods_other||'').trim())return'missing_acquaintance_methods_other';
  if(!d.acquaintance_methods.includes('Другое')&&String(d.acquaintance_methods_other||'').trim())return'unexpected_acquaintance_methods_other';
  if(!SOURCES.includes(d.source))return'invalid_source';
  return null;
}
async function handler(event,{store,mode=process.env.APPLICATION_MODE}={}){if(mode!=='TEST')return reply(503,{error:'production_submission_disabled'});let data;try{data=parse(event);}catch(e){return reply(e.message==='method_not_allowed'?405:415,{error:e.message});}const error=validate(data);if(error)return reply(422,{error});const key=event.headers?.['idempotency-key']||event.headers?.['Idempotency-Key'];if(!key)return reply(400,{error:'idempotency_key_required'});if(!store?.get||!store?.put)return reply(503,{error:'test_store_unavailable'});const old=await store.get(key);if(old)return reply(200,{application_id:old.application_id,idempotent:true});data={...data,phone:phone(data.phone)};const record={application_id:'TEST-'+crypto.randomUUID(),idempotency_key:key,data,received_at:new Date().toISOString()};await store.put(key,record);return reply(201,{application_id:record.application_id,idempotent:false});}
module.exports={handler,validate,phone,LEGAL_VERSIONS,FORM_VERSION,FORM_FIELDS};
