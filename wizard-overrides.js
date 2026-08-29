(function(){
  const shell=document.querySelector('.wizard-shell');
  if(!shell)return;

  const labels=['Контактная информация','Фотография','О вас','Знакомства','Формат встреч','Проверка'];
  shell.querySelectorAll('.wizard-tab').forEach((tab,index)=>{
    if(labels[index])tab.textContent=labels[index];
  });
  shell.querySelectorAll('.wizard-step').forEach((step,index)=>{
    const heading=step.querySelector('.wizard-kicker');
    if(heading&&labels[index])heading.textContent=labels[index];
    step.querySelector('.wizard-title')?.remove();
    step.querySelector('.wizard-help')?.remove();
  });

  const upload=shell.querySelector('#photo-upload');
  const input=shell.querySelector('#photo-input');
  const copy=upload?.querySelector('.photo-upload__copy strong');
  if(copy)copy.textContent='Выбрать или перетащить фотографию';

  if(upload&&input){
    ['dragenter','dragover'].forEach(type=>upload.addEventListener(type,event=>{
      event.preventDefault();
      event.stopPropagation();
      if(event.dataTransfer)event.dataTransfer.dropEffect='copy';
      upload.classList.add('is-dragover');
    }));
    ['dragleave','dragend'].forEach(type=>upload.addEventListener(type,event=>{
      event.preventDefault();
      event.stopPropagation();
      upload.classList.remove('is-dragover');
    }));
    upload.addEventListener('drop',event=>{
      event.preventDefault();
      event.stopPropagation();
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
