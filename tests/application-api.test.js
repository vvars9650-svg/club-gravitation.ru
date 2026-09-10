'use strict';
const assert=require('node:assert/strict');
const {handler,FORM_FIELDS}=require('../api/application');
const payload={full_name:'TEST User',age:'30',gender:'Мужчина',city:'Краснодар',visit_krasnodar:'',phone:'+79990000000',telegram:'',email:'',preferred_contact:'',public_profile_url:'https://example.test',occupation:'',life_outside_work:'',interests:'',what_interested:'',event_expectations:'',desired_connections:['Новые друзья'],values_in_people:'',barriers_to_meeting:'',social_comfort:'',initiative:'',acquaintance_scenario:'',successful_evening:'',return_reason:'',unacceptable_behavior:'',convenient_days:['Суббота'],source:'',personal_data_consent:true,form_version:'FORM-2.1',consent_version:'CONSENT-PD-2.0',policy_version:'PPD-2.0'};
assert.equal(FORM_FIELDS.length,26);
const event=(body=payload,key='key-1')=>({httpMethod:'POST',headers:{'content-type':'application/json','idempotency-key':key},body:JSON.stringify(body)});
const records=new Map(),store={get:k=>records.get(k),put:(k,v)=>records.set(k,v)};
(async()=>{let r=await handler(event(),{store,mode:'TEST'});assert.equal(r.statusCode,201);r=await handler(event(),{store,mode:'TEST'});assert.equal(r.statusCode,200);r=await handler(event({...payload,personal_data_consent:false},'key-2'),{store,mode:'TEST'});assert.equal(r.statusCode,422);r=await handler(event({...payload,city:'Сочи',visit_krasnodar:''},'key-3'),{store,mode:'TEST'});assert.equal(r.statusCode,422);r=await handler(event({...payload,desired_connections:'Новые друзья'},'key-4'),{store,mode:'TEST'});assert.equal(r.statusCode,422);r=await handler(event(),{store,mode:'PRODUCTION'});assert.equal(r.statusCode,503);console.log('application API tests passed');})().catch(e=>{console.error(e);process.exitCode=1;});

