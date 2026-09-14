'use strict';
const assert=require('node:assert/strict');
const {handler}=require('../api/application');
const payload={full_name:'TEST User',age:'30',gender:'Мужчина',city:'Краснодар',visit_krasnodar:'',phone:'8 (999) 000-00-00',email:'user@example.test',preferred_contact:'по email',profile_or_messenger_url:'',public_profile_url:'https://example.test',occupation:'Инженер',life_outside_work:'Спорт',what_interested:'',what_participant_brings:'',what_friends_value:'',desired_connections:['Новые друзья'],desired_connections_other:'',values_in_people:'',barriers_to_meeting:'',acquaintance_methods:['Через живой разговор'],acquaintance_methods_other:'',return_reason:'',source:'Сайт / поиск',policy_acknowledged:true,personal_data_consent:true,form_version:'FORM-2.2',consent_version:'CONSENT-PD-2.1',policy_version:'PPD-2.1'};
const store={rows:new Map(),async get(k){return this.rows.get(k)},async put(k,v){this.rows.set(k,v)}};
const event=(p=payload,key='key-1')=>({httpMethod:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':key},body:JSON.stringify(p)});
(async()=>{
  let r=await handler(event(),{store,mode:'TEST'});assert.equal(r.statusCode,201);assert.equal(store.rows.get('key-1').data.phone,'+79990000000');
  r=await handler(event(),{store,mode:'TEST'});assert.equal(r.statusCode,200);
  for(const [changes,key] of [[{policy_acknowledged:false},'key-2'],[{personal_data_consent:false},'key-3'],[{city:'Сочи',visit_krasnodar:''},'key-4'],[{desired_connections:'Новые друзья'},'key-5'],[{acquaintance_methods:['Другое'],acquaintance_methods_other:''},'key-6'],[{telegram:'legacy'},'key-7']]){
    r=await handler(event({...payload,...changes},key),{store,mode:'TEST'});assert.equal(r.statusCode,422,key);
  }
  r=await handler(event(),{store,mode:'PRODUCTION'});assert.equal(r.statusCode,503);
  console.log('application API tests passed');
})().catch(e=>{console.error(e);process.exitCode=1;});
