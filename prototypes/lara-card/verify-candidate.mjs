// Local candidate verification. Never changes the accepted manifest or a server.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
import {execFileSync} from 'node:child_process';
const root = path.dirname(fileURLToPath(import.meta.url));
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const expected = JSON.parse(fs.readFileSync(path.join(root, 'candidate-manifest.json')));
for (const [file, hash] of Object.entries(expected.sources)) {
  assert.equal(sha(fs.readFileSync(path.join(root,file))),hash,`Source mismatch: ${file}`);
}
const html = fs.readFileSync(path.join(root,'index.html'),'utf8');
for (const [screen, hash] of Object.entries(expected.slideHashes)) {
  const section = html.match(new RegExp(`<section[^>]+data-screen="${screen}"[\\s\\S]*?<\\/section>`))[0];
  assert.equal(sha(section),hash,`Slide ${screen} changed`);
}
assert.match(html,/href="tel:\+79154234712"/);
assert.ok(!html.includes('интересных') && !html.includes('Давай узнаем'));
const listeners = {};
const node = () => ({hidden:false,dataset:{},classList:{toggle(){}},setAttribute(){},removeAttribute(){},querySelector:()=>node(),addEventListener(){}});
const card = node(); card.addEventListener = (name,fn) => { listeners[name]=fn; }; card.setPointerCapture=()=>{};
const slides = Array.from({length:5},(_,i)=>({...node(),dataset:{screen:String(i+1)}}));
const forward=node(),previous=node();
forward.addEventListener=(_,fn)=>{listeners.forward=fn;}; previous.addEventListener=(_,fn)=>{listeners.previous=fn;};
const dots=Array.from({length:5},node);
const buttons=dots.map((_,i)=>({...node(),dataset:{go:String(i+1)},addEventListener(_,fn){listeners[`dot${i+1}`]=fn;}}));
const selectors={'.card':card,'.counter':node(),'.forward':forward,'.previous':previous,'#preview-note':node()};
const document={querySelector:s=>selectors[s],querySelectorAll:s=>s==='.slide'?slides:s==='.dots li'?dots:buttons};
vm.runInNewContext(fs.readFileSync(path.join(root,'script.js'),'utf8'),{document});
const screen=n=>{assert.equal(card.dataset.current,String(n)); assert.deepEqual(slides.map(s=>s.hidden),slides.map((_,i)=>i+1!==n));};
screen(1);
for(let i=2;i<=5;i++){listeners.forward();screen(i);} listeners.forward();screen(5);
for(let i=4;i>=1;i--){listeners.previous();screen(i);} listeners.previous();screen(1);
for(let i=1;i<=5;i++){listeners[`dot${i}`]();screen(i);}
listeners.dot1();
for(let i=2;i<=5;i++){listeners.keydown({key:'ArrowRight',preventDefault(){}});screen(i);}
for(let i=4;i>=1;i--){listeners.keydown({key:'ArrowLeft',preventDefault(){}});screen(i);}
const swipe=(x,y)=>{listeners.pointerdown({pointerType:'touch',pointerId:1,clientX:200,clientY:200,target:{closest:()=>null}});listeners.pointerup({pointerId:1,clientX:200+x,clientY:200+y});};
for(let i=2;i<=5;i++){swipe(-80,5);screen(i);}
for(let i=4;i>=1;i--){swipe(80,5);screen(i);}
swipe(-20,0);screen(1);swipe(-80,100);screen(1);
execFileSync(process.execPath,[path.join(root,'build.mjs')],{stdio:'inherit'});
const args=[path.join(root,'prepare-test-release.mjs'),'--base',expected.base,'--release',expected.candidate,'--output','public-dist/candidate'];
execFileSync(process.execPath,args,{stdio:'pipe'});
const output=path.join(root,'public-dist/candidate/card/lara/index.html');
assert.equal(sha(fs.readFileSync(output)),expected.fileSha256);
execFileSync(process.execPath,args,{stdio:'pipe'});
assert.equal(sha(fs.readFileSync(output)),expected.fileSha256);
console.log('PASS: source/slide hashes, tel, buttons, dots, keyboard, simulated touch pointer events, deterministic standalone build.');
