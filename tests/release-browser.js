const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require('playwright');
const BASE='http://localhost:4176';
const TEST='https://d5ds805l71s68liu6ge4.fovt0b64.apigw.yandexcloud.net';
const output = process.env.QA_OUTPUT || 'test-results';
fs.mkdirSync(output,{recursive:true});
(async()=>{
  const browser=await chromium.launch({headless:true, channel:'msedge'});
  const results=[];
  for(const [width,height,dpr] of [[1440,900,1],[1440,900,2],[390,844,3],[360,800,3],[768,1024,2]]) {
    const context=await browser.newContext({viewport:{width,height},deviceScaleFactor:dpr});
    const page=await context.newPage(); const errors=[];
    page.on('pageerror', e=>errors.push(e.message));
    page.on('response',r=>{if(r.status()>=400)errors.push(r.status()+' '+r.url());});
    for(const route of ['/','/about/','/events/','/first-contact/','/founders/','/privacy/','/consent-pd/','/offer/','/terms/','/apply/?test=true']) {
      await page.goto(BASE+route);
      await page.locator('img').evaluateAll(imgs=>{for(const img of imgs)img.loading='eager';});
      await page.waitForFunction(()=>[...document.images].filter(x=>!x.hidden && x.getAttribute('src')).every(x=>x.complete));
      const metrics=await page.evaluate(()=>({doc:document.documentElement.scrollWidth,body:document.body.scrollWidth,w:innerWidth,broken:[...document.images].filter(x=>!x.complete||!x.naturalWidth).length}));
      assert.ok(metrics.doc<=width+1&&metrics.body<=width+1,route+JSON.stringify(metrics));
      // Empty photo preview is intentionally hidden.
      assert.equal(await page.locator('img:not([hidden])').evaluateAll(imgs=>imgs.filter(i=>!i.complete||!i.naturalWidth).length),0,route);
      if(['/founders/','/first-contact/','/apply/?test=true'].includes(route))await page.screenshot({path:path.join(output,route.split('/')[1]+'-'+width+'-'+dpr+'.png'),fullPage:true});
    }
    assert.deepEqual(errors,[]);results.push({width,height,dpr,pages:10,status:'PASS'});await context.close();
  }
  const page=await browser.newPage();const writes=[];
  await page.route(TEST+'/**',async route=>{
    writes.push(route.request().method()+' '+new URL(route.request().url()).pathname);
    const result=await route.fetch({url:'http://127.0.0.1:4180'+new URL(route.request().url()).pathname});await route.fulfill({response:result});
  });
  await page.route('http://127.0.0.1:4180/upload/**',async route=>{writes.push('PUT synthetic-photo');await route.fulfill({response:await route.fetch()});});
  await page.goto(BASE+'/apply/?test=true');
  await page.locator('#form-submit').click();assert.equal(writes.length,0);
  await page.locator('[name=policy_acknowledged]').check();await page.locator('[name=personal_data_consent]').check();
  await page.locator('[name=full_name]').fill('Synthetic Test');await page.locator('[name=age]').selectOption('30');await page.locator('[name=gender]').selectOption('Мужчина');
  await page.locator('[name=city]').fill('Крас');await page.getByRole('option',{name:'Краснодар',exact:true}).click();
  await page.locator('[name=phone]').fill('+79990000001');await page.locator('[name=email]').fill('synthetic@example.test');await page.locator('[name=profile_or_messenger_url]').fill('@synthetic');
  const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=','base64');
  await page.locator('[name=photo_upload]').setInputFiles({name:'synthetic.png',mimeType:'image/png',buffer:png});
  await page.waitForFunction(()=>document.querySelector('[name=photo_object_id]').value.startsWith('PHOTO-'));
  await page.locator('#form-submit').click();await page.waitForFunction(()=>document.querySelector('#form-status').dataset.state==='success');
  assert.equal(writes.filter(x=>x==='POST /applications').length,1);
  assert.ok((await page.locator('#form-status').textContent()).includes('№000001'));
  results.push({localSyntheticE2E:'PASS',writes});
  await page.goto(BASE+'/apply/'); assert.equal(await page.locator('#application-v5').isVisible(),false);
  // Published visual preview: observe actual browser writes while filling and submitting.
  if(process.env.CHECK_REMOTE_PREVIEW==='true') {
    const remote=await browser.newPage();const remoteWrites=[];
    remote.on('request',r=>{if(!['GET','HEAD'].includes(r.method()))remoteWrites.push({method:r.method(),url:r.url()});});
    await remote.goto('https://vvars9650-svg.github.io/club-gravitation-visual-preview/apply/');
    await remote.locator('[name=policy_acknowledged]').check();await remote.locator('[name=personal_data_consent]').check();
    await remote.locator('[name=full_name]').fill('Synthetic Test');await remote.locator('[name=age]').selectOption('30');await remote.locator('[name=gender]').selectOption('Мужчина');
    await remote.locator('[name=city]').fill('Крас');await remote.getByRole('option',{name:'Краснодар',exact:true}).click();
    await remote.locator('[name=phone]').fill('+79990000001');await remote.locator('[name=email]').fill('synthetic@example.test');await remote.locator('[name=profile_or_messenger_url]').fill('@synthetic');
    await remote.locator('[name=photo_upload]').setInputFiles({name:'synthetic.png',mimeType:'image/png',buffer:png});
    await remote.waitForFunction(()=>document.querySelector('[name=photo_object_id]').value.startsWith('PHOTO-'));
    await remote.locator('#form-submit').click();await remote.waitForTimeout(300);assert.deepEqual(remoteWrites,[]);
    assert.equal(await remote.locator('#form-status').getAttribute('data-state'),'preview');
    results.push({publishedPreviewIsolation:'PASS',writes:remoteWrites});
  }
  fs.writeFileSync(path.join(output,'release-browser-results.json'),JSON.stringify(results,null,2));console.log(JSON.stringify(results));await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
