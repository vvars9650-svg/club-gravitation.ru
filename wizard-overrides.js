(function(){
  const DRAFT_KEY='gravitation_application_draft_v3';

  // Apps Script v6 уже умеет status + JSONP. Отправляем POST через скрытый iframe,
  // а подтверждение читаем отдельным JSONP-запросом по participant_id.
  // Так мы не зависим ни от CORS, ни от fetch/no-cors, ни от postMessage bridge.
  if(!window.__gravitationSubmissionGuard){
    window.__gravitationSubmissionGuard=true;
    const nativeFetch=window.fetch.bind(window);
    const appsScriptRe=/^https:\/\/script\.google\.com\/macros\/s\//i;

    window.fetch=function(input,init={}){
      const url=typeof input==='string'?input:(input&&input.url)||'';
      const method=String(init.method||'GET').toUpperCase();
      const body=init.body;
      const guarded=appsScriptRe.test(url)&&method==='POST'&&body instanceof URLSearchParams&&body.has('participant_id');
      if(!guarded)return nativeFetch(input,init);
      return submitAndConfirm(url,body);
    };

    async function submitAndConfirm(endpoint,params){
      const participantId=String(params.get('participant_id')||'').trim();
      if(!participantId)throw new Error('Не удалось сформировать номер заявки.');

      submitViaIframe(endpoint,params,participantId);

      let last=null;
      for(let attempt=0;attempt<20;attempt++){
        if(attempt===0)await delay(850);
        else await delay(attempt<7?650:1000);

        try{
          last=await statusJsonp(endpoint,participantId,3500);
        }catch(error){
          continue;
        }

        if(last&&last.ok){
          return {ok:true,status:204,type:'confirmed'};
        }
        if(last&&last.found&&!last.pending){
          const text=last.error||'Сервер не сохранил заявку. Попробуйте ещё раз.';
          showPreciseError(text);
          const error=new Error(text);
          error.stage=last.stage||'сохранение заявки';
          throw error;
        }
      }

      const message='Заявка отправлена на сервер, но сайт не смог получить подтверждение. Не отправляйте её повторно сразу.';
      showPreciseError(message);
      throw new Error('Submission confirmation timeout');
    }

    function submitViaIframe(endpoint,params,id){
      const safe=id.replace(/[^0-9A-Za-z_-]/g,'');
      const frameName=`gravitation_post_${safe}_${Date.now()}`;
      const iframe=document.createElement('iframe');
      iframe.name=frameName;
      iframe.hidden=true;
      iframe.style.display='none';
      iframe.setAttribute('aria-hidden','true');

      const postForm=document.createElement('form');
      postForm.method='POST';
      postForm.action=endpoint;
      postForm.target=frameName;
      postForm.hidden=true;
      postForm.style.display='none';
      postForm.acceptCharset='UTF-8';

      for(const [name,value] of params.entries()){
        const field=document.createElement('input');
        field.type='hidden';
        field.name=name;
        field.value=value;
        postForm.appendChild(field);
      }

      document.body.append(iframe,postForm);
      postForm.submit();
      postForm.remove();
      setTimeout(()=>iframe.remove(),60000);
    }

    function statusJsonp(endpoint,id,timeoutMs){
      return new Promise((resolve,reject)=>{
        const callback=`gravitationStatus_${Date.now()}_${Math.random().toString(36).slice(2)}`;
        const script=document.createElement('script');
        let finished=false;
        const timer=setTimeout(()=>finish(()=>reject(new Error('Сервис подтверждения не ответил.'))),timeoutMs);

        window[callback]=data=>finish(()=>resolve(data||{}));
        script.onerror=()=>finish(()=>reject(new Error('Не удалось проверить статус заявки.')));

        const separator=endpoint.includes('?')?'&':'?';
        script.src=`${endpoint}${separator}action=status&id=${encodeURIComponent(id)}&callback=${encodeURIComponent(callback)}&_=${Date.now()}`;
        script.async=true;
        document.head.appendChild(script);

        function finish(done){
          if(finished)return;
          finished=true;
          clearTimeout(timer);
          try{delete window[callback];}catch(e){window[callback]=undefined;}
          script.remove();
          done();
        }
      });
    }

    function showPreciseError(message){
      // app.js в catch пишет своё старое сообщение, поэтому ставим наше на тик позже.
      setTimeout(()=>{
        const status=document.querySelector('#form-status');
        if(!status)return;
        status.textContent=message;
        status.className='form-status is-error';
      },100);
    }

    function delay(ms){return new Promise(resolve=>setTimeout(resolve,ms));}
  }

  const shell=document.querySelector('.wizard-shell');
  if(!shell)return;
  const form=shell.querySelector('#application-form');

  // После полного обновления страницы начинаем чистую анкету.
  // Политика открывается в новой вкладке, поэтому введённые данные в исходной вкладке не теряются.
  try{localStorage.removeItem(DRAFT_KEY);}catch(e){}
  if(form){
    form.reset();
    form.querySelectorAll('.is-invalid').forEach(el=>el.classList.remove('is-invalid'));
    const status=form.querySelector('#form-status');
    if(status){status.textContent='';status.className='form-status';}
    const preview=form.querySelector('#photo-preview');
    if(preview)preview.innerHTML='<span>＋</span>';
    const photoName=form.querySelector('#photo-file-name');
    if(photoName)photoName.textContent='';
    const photoError=form.querySelector('#photo-error');
    if(photoError)photoError.textContent='';
    const firstTab=shell.querySelector('[data-step-target="0"]');
    if(firstTab&&!firstTab.classList.contains('is-active'))firstTab.click();
  }

  const style=document.createElement('style');
  style.textContent=`
    .wizard-progress span{background:var(--red)!important}
    .wizard-title,.wizard-help,.wizard-kicker{display:none!important}
    .wizard-tab{white-space:normal!important;overflow:visible!important;text-overflow:clip!important;line-height:1.2!important;min-height:44px!important;padding:8px 6px!important}
    .wizard-tab:first-child{font-size:9px!important}
    .photo-upload.is-dragover{border-color:var(--red)!important;background:rgba(181,43,43,.055)!important;box-shadow:0 0 0 4px rgba(181,43,43,.08)!important}
    .wizard-step{padding-top:10px}
    @media(max-width:640px){.wizard-tab{min-height:42px!important}.wizard-tab:first-child{font-size:8px!important}}
  `;
  document.head.appendChild(style);

  const labels=['Контактная информация','Фотография','О вас','Знакомства','Формат встреч','Проверка'];
  shell.querySelectorAll('.wizard-tab').forEach((tab,index)=>{if(labels[index])tab.textContent=labels[index];});
  shell.querySelectorAll('.wizard-step').forEach(step=>{
    step.querySelector('.wizard-kicker')?.remove();
    step.querySelector('.wizard-title')?.remove();
    step.querySelector('.wizard-help')?.remove();
  });

  // Навигация: первый шаг — только «Далее»; последний — «Назад» + «Отправить заявку».
  const actions=shell.querySelector('#wizard-actions');
  const back=shell.querySelector('#wizard-back');
  const next=shell.querySelector('#wizard-next');
  const steps=[...shell.querySelectorAll('.wizard-step')];
  function syncWizardActions(){
    const current=steps.findIndex(step=>step.classList.contains('is-active'));
    if(current<0||!actions||!back||!next)return;
    actions.hidden=false;
    actions.style.display='flex';
    back.hidden=current===0;
    back.style.display=current===0?'none':'';
    next.hidden=current===steps.length-1;
    next.style.display=current===steps.length-1?'none':'';
  }
  const observer=new MutationObserver(syncWizardActions);
  steps.forEach(step=>observer.observe(step,{attributes:true,attributeFilter:['class']}));
  syncWizardActions();

  const upload=shell.querySelector('#photo-upload');
  const input=shell.querySelector('#photo-input');
  const copy=upload?.querySelector('.photo-upload__copy strong');
  if(copy)copy.textContent='Выбрать или перетащить фотографию';

  if(upload&&input){
    const stop=event=>{event.preventDefault();event.stopPropagation();};
    ['dragenter','dragover'].forEach(type=>upload.addEventListener(type,event=>{
      stop(event);
      if(event.dataTransfer)event.dataTransfer.dropEffect='copy';
      upload.classList.add('is-dragover');
    }));
    ['dragleave','dragend'].forEach(type=>upload.addEventListener(type,event=>{
      stop(event);
      if(type==='dragleave'&&event.relatedTarget&&upload.contains(event.relatedTarget))return;
      upload.classList.remove('is-dragover');
    }));
    upload.addEventListener('drop',event=>{
      stop(event);
      upload.classList.remove('is-dragover');
      const file=[...(event.dataTransfer?.files||[])].find(item=>String(item.type||'').startsWith('image/'));
      if(!file)return;
      try{
        const transfer=new DataTransfer();
        transfer.items.add(file);
        input.files=transfer.files;
        input.dispatchEvent(new Event('change',{bubbles:true}));
      }catch(error){input.click();}
    });
  }
})();
