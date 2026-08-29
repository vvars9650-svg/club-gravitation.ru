(()=>{
  const nativeFetch=window.fetch.bind(window);
  const APPS_SCRIPT_RE=/^https:\/\/script\.google\.com\/macros\/s\//i;

  window.fetch=async function(input,init={}){
    const url=typeof input==='string'?input:(input&&input.url)||'';
    const method=String(init.method||'GET').toUpperCase();
    const body=init.body;
    const isApplicationPost=APPS_SCRIPT_RE.test(url)&&method==='POST'&&body instanceof URLSearchParams&&body.has('participant_id');

    if(!isApplicationPost)return nativeFetch(input,init);

    const participantId=String(body.get('participant_id')||'').trim();
    const response=await nativeFetch(input,init);
    const confirmation=await waitForSubmissionConfirmation(url,participantId);

    if(!confirmation.ok){
      const error=new Error(confirmation.error||'Сервер не подтвердил сохранение заявки.');
      error.stage=confirmation.stage||'';
      error.submissionId=participantId;
      throw error;
    }
    return response;
  };

  async function waitForSubmissionConfirmation(endpoint,id){
    let last={ok:false,found:false,pending:true,id};
    for(let attempt=0;attempt<15;attempt++){
      if(attempt>0)await delay(attempt<5?650:1100);
      try{
        last=await getStatusJsonp(endpoint,id);
      }catch(error){
        last={ok:false,found:false,pending:true,id,error:String(error&&error.message||error)};
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
      error:'Не удалось подтвердить сохранение заявки. Данные формы сохранены в браузере. Попробуйте отправить заявку ещё раз: повтор с тем же номером не создаст дубль.'
    };
  }

  function getStatusJsonp(endpoint,id){
    return new Promise((resolve,reject)=>{
      const callback=`gravitationSubmission_${Date.now()}_${Math.random().toString(36).slice(2)}`;
      const script=document.createElement('script');
      let finished=false;
      const timeout=setTimeout(()=>finish(()=>reject(new Error('Сервис подтверждения не ответил.'))),6500);

      window[callback]=data=>finish(()=>resolve(data||{}));
      script.onerror=()=>finish(()=>reject(new Error('Не удалось проверить статус заявки.')));

      const separator=endpoint.includes('?')?'&':'?';
      script.src=`${endpoint}${separator}action=status&id=${encodeURIComponent(id)}&callback=${encodeURIComponent(callback)}&_=${Date.now()}`;
      script.async=true;
      document.head.appendChild(script);

      function finish(done){
        if(finished)return;
        finished=true;
        clearTimeout(timeout);
        try{delete window[callback];}catch(e){window[callback]=undefined;}
        script.remove();
        done();
      }
    });
  }

  function delay(ms){return new Promise(resolve=>setTimeout(resolve,ms));}
})();
