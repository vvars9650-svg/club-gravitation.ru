(function(){
  // Apps Script POST остаётся no-cors. Некоторые мобильные браузеры могут отклонить сам fetch
  // уже после того, как сервер успешно принял данные. Поэтому транспортную ошибку не считаем
  // финальным результатом: всегда проверяем сохранение по ID через отдельный JSONP status-запрос.
  if(!window.__gravitationSubmissionGuard){
    window.__gravitationSubmissionGuard=true;
    const nativeFetch=window.fetch.bind(window);
    const appsScriptRe=/^https:\/\/script\.google\.com\/macros\/s\//i;

    window.fetch=async function(input,init={}){
      const url=typeof input==='string'?input:(input&&input.url)||'';
      const method=String(init.method||'GET').toUpperCase();
      const body=init.body;
      const guarded=appsScriptRe.test(url)&&method==='POST'&&body instanceof URLSearchParams&&body.has('participant_id');
      if(!guarded)return nativeFetch(input,init);

      const participantId=String(body.get('participant_id')||'').trim();
      let response=null;
      let transportError=null;

      try{
        response=await nativeFetch(input,init);
      }catch(error){
        // На Android/некоторых WebView no-cors POST к Apps Script может упасть на клиенте
        // после успешной серверной записи. Проверка по ID ниже является источником истины.
        transportError=error;
      }

      const confirmation=await waitForConfirmation(url,participantId);
      if(confirmation.ok)return response;

      const error=new Error(
        confirmation.error||
        (transportError&&transportError.message)||
        'Сервер не подтвердил сохранение заявки.'
      );
      error.stage=confirmation.stage||'подтверждение записи';
      error.submissionId=participantId;
      error.transportError=transportError||null;
      throw error;
    };

    async function waitForConfirmation(endpoint,id){
      let last=null;
      for(let attempt=0;attempt<18;attempt++){
        if(attempt>0)await new Promise(resolve=>setTimeout(resolve,attempt<6?650:1100));
        try{
          last=await statusJsonp(endpoint,id);
        }catch(error){
          last={ok:false,found:false,pending:true,error:String(error&&error.message||error)};
          continue;
        }
        if(last&&last.ok)return last;
        if(last&&last.found&&!last.pending)return last;
      }
      return {
        ok:false,
        found:false,
        pending:false,
        id,
        stage:'подтверждение записи',
        error:'Не удалось подтвердить сохранение заявки. Данные формы сохранены в браузере. Повторная отправка с тем же номером не создаст дубль.'
      };
    }

    function statusJsonp(endpoint,id){
      return new Promise((resolve,reject)=>{
        const callback=`gravitationSubmission_${Date.now()}_${Math.random().toString(36).slice(2)}`;
        const script=document.createElement('script');
        let finished=false;
        const timer=setTimeout(()=>finish(()=>reject(new Error('Сервис подтверждения не ответил.'))),6500);
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
  }

  const shell=document.querySelector('.wizard-shell');
  if(!shell)return;

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
