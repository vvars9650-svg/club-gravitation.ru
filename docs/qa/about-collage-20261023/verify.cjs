const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {execFileSync}=require('node:child_process');
fs.mkdirSync('test-results/about-collage',{recursive:true});
(async()=>{
 const browser=await chromium.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox']});
 const results=[];
 for(const [width,height,dpr] of [[1440,900,1],[1440,900,2],[1920,1080,1],[768,1024,2],[390,844,3],[360,800,3]]){
  const context=await browser.newContext({viewport:{width,height},deviceScaleFactor:dpr});
  const page=await context.newPage();const errors=[],network=[],consoleErrors=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('console',m=>{if(m.type()==='error')consoleErrors.push(m.text())});
  page.on('requestfailed',r=>network.push({url:r.url(),error:r.failure()?.errorText}));
  page.on('response',r=>{if(r.status()>=400)network.push({url:r.url(),status:r.status()})});
  await page.goto('http://localhost:4176/about/',{waitUntil:'networkidle'});
  await page.locator('img').evaluateAll(imgs=>imgs.forEach(i=>i.loading='eager'));
  await page.waitForFunction(()=>[...document.images].every(i=>i.complete&&i.naturalWidth));
  const metrics=await page.evaluate(()=>{
   const collage=document.querySelector('.about-collage');const grid=collage.getBoundingClientRect();
   const cards=[...collage.querySelectorAll('picture')].map(el=>{
    const r=el.getBoundingClientRect(),im=el.querySelector('img'),ir=im.getBoundingClientRect();
    return {x:r.x,y:r.y,width:r.width,height:r.height,scaleX:ir.width/im.naturalWidth,scaleY:ir.height/im.naturalHeight,source:im.currentSrc};
   });
   return {width:innerWidth,scrollWidth:document.documentElement.scrollWidth,grid:{x:grid.x,width:grid.width},cards,tag:document.querySelector('.brand__tag').textContent,footer:document.querySelector('.site-footer>p').textContent};
  });
  assert.equal(metrics.cards.length,8);assert.ok(metrics.scrollWidth<=width);
  assert.equal(metrics.tag,'КЛУБ ЖИВЫХ ВСТРЕЧ');assert.equal(metrics.footer,'Краснодар');
  for(const card of metrics.cards){
   assert.ok(Math.abs(card.width-metrics.cards[0].width)<0.1);
   assert.ok(Math.abs(card.height-metrics.cards[0].height)<0.1);
   assert.ok(Math.abs(card.scaleX-card.scaleY)<0.001,'Image distortion');
  }
  const cols=width<=760?2:4;
  for(let i=0;i<8;i+=cols){assert.ok(Math.abs(metrics.cards[i].x-4)<.1);assert.ok(Math.abs(metrics.cards[i+cols-1].x+metrics.cards[i+cols-1].width-(width-4))<.1)}
  // All ABOUT main blocks outside the collage retain their exact baseline markup.
  const baseline=execFileSync('git',['show','4ca9034aaff5d7548910bb6c6ca5edd824194009:about/index.html'],{encoding:'utf8'});
  assert.equal(await page.evaluate(source=>{
   const old=new DOMParser().parseFromString(source,'text/html');
   const keep=d=>[...d.querySelector('main').children].filter(el=>!el.classList.contains('story-figure--final')).map(el=>{const clone=el.cloneNode(true);clone.querySelectorAll('img').forEach(i=>i.removeAttribute('loading'));return clone.outerHTML});
   return JSON.stringify(keep(old))===JSON.stringify(keep(document));
  },baseline),true);
  assert.deepEqual(errors,[]);
  results.push({width,height,dpr,status:'PASS',metrics,errors,consoleErrors,network});
  fs.writeFileSync('test-results/about-collage/qa-results.json',JSON.stringify(results,null,2));
  await context.close();
 }
 // Check shared branding on every public route, including protected form/legal source.
 const context=await browser.newContext({viewport:{width:390,height:844}});const page=await context.newPage();
 const routes=['/','/about/','/events/','/first-contact/','/founders/','/apply/','/privacy/','/consent-pd/','/offer/','/terms/'];
 for(const route of routes){
  await page.goto('http://localhost:4176'+route,{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>document.querySelector('.site-footer>p')?.textContent==='Краснодар');
  if(await page.locator('.brand__tag').count()){assert.equal(await page.locator('.brand__tag').innerText(),'КЛУБ ЖИВЫХ ВСТРЕЧ',route);assert.equal(await page.locator('header').innerText().then(s=>/Краснодар/i.test(s)),false,route);}
  assert.equal(await page.locator('.site-footer>p').innerText(),'Краснодар',route);
 }
 await page.goto('http://localhost:4176/first-contact/');assert.match(await page.locator('main').innerText(),/Краснодар/);
 results.push({sharedBrandingRoutes:routes,status:'PASS'});
 fs.writeFileSync('test-results/about-collage/qa-results.json',JSON.stringify(results,null,2));
 console.log(JSON.stringify(results.map(({metrics,...rest})=>rest),null,2));
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
