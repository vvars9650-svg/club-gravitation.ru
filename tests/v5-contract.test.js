'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs');
const apply=fs.readFileSync('apply/index.html','utf8'),api=fs.readFileSync('api/application.js','utf8'),js=fs.readFileSync('assets/js/apply.js','utf8'),all=`${apply}\n${api}\n${js}`;
const screens=['Согласие','Контакты','О вас','Знакомства','Формат','Проверка'];
const fields=['full_name','age','gender','city','visit_krasnodar','phone','telegram','email','preferred_contact','public_profile_url','occupation','life_outside_work','interests','what_interested','event_expectations','desired_connections','values_in_people','barriers_to_meeting','social_comfort','initiative','acquaintance_scenario','successful_evening','return_reason','unacceptable_behavior','convenient_days','source'];
assert.equal((apply.match(/data-step="/g)||[]).length,6);
screens.forEach(x=>assert.ok(apply.includes(`>${x}<`),x));
fields.forEach(x=>{assert.ok(apply.includes(`name="${x}"`),x);assert.ok(api.includes(`'${x}'`),`API ${x}`)});
assert.equal(all.includes('comfortable_price'),false);
assert.match(apply,/Ссылка на профиль или мессенджер \(необязательно\)/);
assert.match(apply,/Ссылка на вашу страницу или сайт \(необязательно\)/);
assert.match(apply,/Не указывайте сведения специальных категорий персональных данных\./);
assert.match(apply,/href="\/privacy\/"[\s\S]*href="\/consent-pd\//);
assert.match(apply,/name="personal_data_consent"/);
for(const x of ['relationship_context','rules_consent','script.google.com','no-cors','photo_data','base64'])assert.equal(all.toLowerCase().includes(x),false,x);
assert.ok(api.includes('production_submission_disabled'));
console.log('V5 static contract tests passed');

