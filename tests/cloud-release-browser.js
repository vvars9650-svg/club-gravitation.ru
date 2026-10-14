// Actual TEST API and private photo flow; frontend bytes supplied from the RC artifact.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const HOST='https://gravitation-v5-test-frontend-b1g4bdjb.storage.yandexcloud.net';
(async()=>{
  const browser=await chromium.launch({headless:true,channel:'msedge'});
  const page=await browser.newPage();const writes=[];
  page.on('request',r=>{if(!['GET','HEAD'].includes(r.method()))writes.push(r.method()+' '+new URL(r.url()).pathname)});
  await page.route(HOST+'/**',async route=>{
    const url=new URL(route.request().url());
    await route.fulfill({response:await route.fetch({url:'http://localhost:4176'+url.pathname+url.search})});
  });
  const stamp=Date.now().toString().slice(-7);
  async function fill(){
    await page.goto(HOST+'/apply/');
    await page.locator('[name=policy_acknowledged]').check();await page.locator('[name=personal_data_consent]').check();
    await page.locator('[name=full_name]').fill('Synthetic Release Test');await page.locator('[name=age]').selectOption('30');await page.locator('[name=gender]').selectOption('Мужчина');
    await page.locator('[name=city]').fill('Крас');await page.getByRole('option',{name:'Краснодар',exact:true}).click();
    await page.locator('[name=phone]').fill('+7999'+stamp);await page.locator('[name=email]').fill('release-'+stamp+'@example.test');await page.locator('[name=profile_or_messenger_url]').fill('@synthetic_release_'+stamp);
    const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=','base64');
    await page.locator('[name=photo_upload]').setInputFiles({name:'synthetic.png',mimeType:'image/png',buffer:png});
    await page.waitForFunction(()=>document.querySelector('[name=photo_object_id]').value.startsWith('PHOTO-'),{},{timeout:45000});
    const response=page.waitForResponse(r=>r.url().endsWith('/applications')&&r.request().method()==='POST');
    await page.locator('#form-submit').click();const result=await response; const body=await result.json();
    if(![200,201].includes(result.status()))fs.writeFileSync('test-results/cloud-failed-request.json',JSON.stringify({httpMethod:'POST',path:'/applications',headers:result.request().headers(),body:result.request().postData()}));
    assert.ok([200,201].includes(result.status()),JSON.stringify(body));
    await page.waitForFunction(()=>document.querySelector('#form-status').dataset.state==='success');
    return {status:result.status(),...body};
  }
  const first=await fill();const duplicate=await fill();
  assert.equal(duplicate.application_number,first.application_number);assert.equal(duplicate.already_registered,true);
  const evidence={environment:'TEST',application_id:first.application_id,participant_id:first.participant_id,application_number:first.application_number,duplicate:true,writes};
  fs.writeFileSync('test-results/cloud-e2e.json',JSON.stringify(evidence,null,2));console.log(JSON.stringify(evidence));await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
