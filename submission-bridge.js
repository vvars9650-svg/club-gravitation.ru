(()=>{
  const nativeFetch=window.fetch.bind(window);
  const APPS_SCRIPT_RE=/^https:\/\/script\.google\.com\/macros\/s\//i;
  const MESSAGE_TYPE='gravitation-submission-status';

  window.fetch=function(input,init={}){
    const url=typeof input==='string'?input:(input&&input.url)||'';
    const method=String(init.method||'GET').toUpperCase();
    const body=init.body;
    const isApplicationPost=APPS_SCRIPT_RE.test(url)&&method==='POST'&&body instanceof URLSearchParams&&body.has('participant_id');
    if(!isApplicationPost)return nativeFetch(input,init);
    return submitAndConfirm(url,body);
  };

  async function submitAndConfirm(endpoint,params){
    const id=String(params.get('participant_id')||'').trim();
    const token=`gr_${Date.now()}_${Math.random().toString(36).slice(2)}`;
    submitViaIframe(endpoint,params,token);

    let result=null;
    for(let attempt=0;attempt<16;attempt++){
      if(attempt>0)await delay(attempt<6?600:1000);
      try{result=await checkStatus(endpoint,id,token,5500);}catch(error){continue;}
      if(result&&result.ok)return new Response('',{status:204,statusText:'Confirmed'});
      if(result&&result.found&&!result.pending){
        surfaceError(result.error||'Сервер не сохранил заявку. Попробуйте ещё раз.');
        throw new Error(result.error||'Submission failed');
      }
    }
    surfaceError('Заявка могла быть отправлена, но сайт не получил подтверждение. Не отправляйте её повторно сразу. Обновите страницу через минуту или свяжитесь с организаторами.');
    throw new Error('Submission confirmation timeout');
  }

  function submitViaIframe(endpoint,params,token){
    const frameName=`gravitation_post_${token}`;
    const iframe=document.createElement('iframe');
    iframe.name=frameName;
    iframe.hidden=true;
    iframe.setAttribute('aria-hidden','true');

    const form=document.createElement('form');
    form.method='POST';
    form.action=endpoint;
    form.target=frameName;
    form.hidden=true;
    form.acceptCharset='UTF-8';

    for(const [name,value] of params.entries()){
      const input=document.createElement('input');
      input.type='hidden';
      input.name=name;
      input.value=value;
      form.appendChild(input);
    }
    const transport=document.createElement('input');
    transport.type='hidden';
    transport.name='transport';
    transport.value='iframe';
    form.appendChild(transport);

    document.body.append(iframe,form);
    form.submit();
    form.remove();
    setTimeout(()=>iframe.remove(),45000);
  }

  function checkStatus(endpoint,id,token,timeoutMs){
    return new Promise((resolve,reject)=>{
      const iframe=document.createElement('iframe');
      iframe.hidden=true;
      iframe.setAttribute('aria-hidden','true');
      let done=false;
      const timer=setTimeout(()=>finish(()=>reject(new Error('Confirmation timeout'))),timeoutMs);

      function onMessage(event){
        const data=event.data;
        if(!data||data.type!==MESSAGE_TYPE||data.token!==token||data.id!==id)return;
        finish(()=>resolve(data));
      }
      function finish(callback){
        if(done)return;
        done=true;
        clearTimeout(timer);
        window.removeEventListener('message',onMessage);
        iframe.remove();
        callback();
      }

      window.addEventListener('message',onMessage);
      const sep=endpoint.includes('?')?'&':'?';
      iframe.src=`${endpoint}${sep}action=bridge&id=${encodeURIComponent(id)}&token=${encodeURIComponent(token)}&_=${Date.now()}`;
      document.body.appendChild(iframe);
    });
  }

  function surfaceError(message){
    setTimeout(()=>{
      const status=document.querySelector('#form-status');
      if(!status)return;
      status.textContent=message;
      status.className='form-status is-error';
    },30);
  }

  function delay(ms){return new Promise(resolve=>setTimeout(resolve,ms));}
})();
