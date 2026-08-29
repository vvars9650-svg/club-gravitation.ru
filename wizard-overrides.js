(function(){
  const DRAFT_KEY='gravitation_application_draft_v3';

  // Надёжная отправка заявки без fetch/no-cors.
  // POST уходит через скрытую форму в iframe, затем сайт получает подтверждение
  // от Apps Script через отдельный iframe + postMessage.
  if(!window.__gravitationSubmissionGuard){
    window.__gravitationSubmissionGuard=true;
    const nativeFetch=window.fetch.bind(window);
    const appsScriptRe=/^https:\/\/script\.google\.com\/macros\/s\//i;
    const messageType='gravitation-submission-status';

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
      const token=`gr_${Date.now()}_${Math.random().toString(36).slice(2)}`;
      submitViaIframe(endpoint,params,token);

      let last=null;
      for(let attempt=0;attempt<18;attempt++){
        if(attempt>0)await delay(attempt<7?650:1000);
        try{last=await statusBridge(endpoint,participantId,token,5500);}catch(error){continue;}
        if(last&&last.ok)return {ok:true,status:204,type:'confirmed'};
        if(last&&last.found&&!last.pending){
          showPreciseError(last.error||'Сервер не сохранил заявку. Попробуйте ещё раз.');
          const error=new Error(last.error||'Submission failed');
          error.stage=last.stage||'сохранение заявки';
          throw error;
        }
      }

      const message='Заявка могла быть отправлена, но сайт не получил подтверждение. Не отправляйте её повторно сразу. Подождите минуту и обновите страницу.';
      showPreciseError(message);
      throw new Error('Submission confirmation timeout');
    }

    function submitViaIframe(endpoint,params,token){
      const frameName=`gravitation_post_${token}`;
      const iframe=document.createElement('iframe');
      iframe.name=frameName;
      iframe.hidden=true;
      iframe.setAttribute('aria-hidden','true');

      const postForm=document.createElement('form');
      postForm.method='POST';
      postForm.action=endpoint;
      postForm.target=frameName;
      postForm.hidden=true;
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
      setTimeout(()=>iframe.remove(),45000);
    }

    function statusBridge(endpoint,id,token,timeoutMs){
      return new Promise((resolve,reject)=>{
        const iframe=document.createElement('iframe');
        iframe.hidden=true;
        iframe.setAttribute('aria-hidden','true');
        let finished=false;
        const timer=setTimeout(()=>finish(()=>reject(new Error('Сервис подтверждения не ответил.'))),timeoutMs);

        function onMessage(event){
          const data=event.data;
          if(!data||data.type!==messageType||data.token!==token||data.id!==id)return;
          finish(()=>resolve(data));
        }
        function finish(done){
          if(finished)return;
          finished=true;
          clearTimeout(timer);
          window.removeEventListener('message',onMessage);
          iframe.remove();
          done();
        }

        window.addEventListener('message',onMessage);
        const separator=endpoint.includes('?')?'&':'?';
        iframe.src=`${endpoint}${separator}action=bridge&id=${encodeURIComponent(id)}&token=${encodeURIComponent(token)}&_=${Date.now()}`;
        document.body.appendChild(iframe);
      });
    }

    function showPreciseError(message){
      setTimeout(()=>{
        const status=document.querySelector('#form-status');
        if(!status)return;
        status.textContent=message;
        status.className='form-status is-error';
      },60);
    }

    function delay(ms){return new Promise(resolve=>setTimeout(resolve,ms));}
  }

  const shell=document.querySelector('.wizard-shell');
  if(!shell)return;
  const form=shell.querySelector('#application-form');

  // После полной перезагрузки начинаем новую анкету. Возврат из политики остаётся
  // безопасным: она открывается в отдельной вкладке, исходная форма не перезагружается.
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

  // Навигация: первый шаг — только «Далее». Последний — только «Назад» + «Отправить заявку».
  const actions=shell.querySelector('#wizard-actions');
  const back=shell.querySelector('#wizard-back');
  const next=shell.querySelector('#wizard-next');
  const steps=[...shell.querySelectorAll('.wizard-step')];
  function syncWizardActions(){
    const current=steps.findIndex(step=>step.classList.contains('is-active'));
    if(current<0||!actions||!back||!next)return;
    actions.hidden=false;
    back.hidden=current===0;
    next.hidden=current===steps.length-1;
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
