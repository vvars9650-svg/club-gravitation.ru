(function(){
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
  shell.querySelectorAll('.wizard-tab').forEach((tab,index)=>{
    if(labels[index])tab.textContent=labels[index];
  });
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
      }catch(error){
        input.click();
      }
    });
  }
})();
