/**
 * ГРАВИТАЦИЯ — приём пошаговой анкеты сайта в Google Sheets + Google Drive.
 * После изменения этого файла: Apps Script → Развернуть → Управление развертываниями → Изменить → Новая версия.
 */
const APP_VERSION=6;
const SPREADSHEET_ID='1pt69LEjrPiCPTF6ZzR_Lc6k-uXjW6qyXURBNqT_EsTw';
const PARTICIPANTS_SHEET='Участники';
const WEB_RAW_SHEET='Сайт — RAW';
const LOG_SHEET='Сайт — Логи';
const PHOTO_FOLDER_ID='1jIObgJ6szGwEGHRjUGC_D7qHbAyLIfFV';
const YUFO_CITIES=["Абинск","Адыгейск","Азов","Аксай","Алупка","Алушта","Анапа","Апшеронск","Армавир","Армянск","Астрахань","Ахтубинск","Батайск","Бахчисарай","Белая Калитва","Белогорск","Белореченск","Волгоград","Волгодонск","Волжский","Геленджик","Городовиковск","Горячий Ключ","Гуково","Гулькевичи","Джанкой","Донецк","Дубовка","Евпатория","Ейск","Жирновск","Зверево","Зерноград","Знаменск","Инкерман","Калач-на-Дону","Каменск-Шахтинский","Камызяк","Камышин","Керчь","Константиновск","Кореновск","Котельниково","Котово","Краснодар","Красноперекопск","Краснослободск","Красный Сулин","Кропоткин","Крымск","Курганинск","Лабинск","Лагань","Ленинск","Майкоп","Миллерово","Михайловка","Морозовск","Нариманов","Николаевск","Новоаннинский","Новокубанск","Новороссийск","Новочеркасск","Новошахтинск","Палласовка","Петров Вал","Приморско-Ахтарск","Пролетарск","Ростов-на-Дону","Саки","Сальск","Севастополь","Семикаракорск","Серафимович","Симферополь","Славянск-на-Кубани","Сочи","Старый Крым","Судак","Суровикино","Таганрог","Темрюк","Тимашёвск","Тихорецк","Туапсе","Урюпинск","Усть-Лабинск","Феодосия","Фролово","Хадыженск","Харабали","Цимлянск","Шахты","Щёлкино","Элиста","Ялта"];

const PARTICIPANT_HEADERS=['ID','Статус','Приоритет','Ответственный','Следующий шаг','Дата следующего контакта','Дата интервью','Решение','Комментарий','Ближайшее мероприятие','Количество посещений','Последнее участие','Дата заявки','Имя и фамилия','Возраст','Пол','Город','Посещение Краснодара','Телефон','Telegram','ВКонтакте','Instagram','Email','Как удобнее связаться?','Фото','Чем занимается','Жизнь кроме работы','Интересы','Контекст отношений','Какие знакомства интересны','Что ценит в людях','Что мешает знакомиться','Источник','Что заинтересовало','Ожидания от мероприятия','Удачный вечер','Что заставит вернуться','Комфорт в новой компании','Инициативность','Сценарий знакомства','Неприемлемое поведение','Удобные дни','Комфортная цена','Согласие на связь','Согласие ПДн','Правила участия','Канал заявки','UTM Source','UTM Medium','UTM Campaign','UTM Content','UTM Term','Referrer'];
const RAW_HEADERS=['Дата сервера','ID','Имя и фамилия','Возраст','Пол','Город','Посещение Краснодара','Телефон','Telegram','Email','Как удобнее связаться','Фото URL','Чем занимается','Жизнь кроме работы','Интересы','Контекст отношений','Какие знакомства интересны','Что ценит в людях','Что мешает знакомиться','Что заинтересовало','Ожидания','Удачный вечер','Что заставит вернуться','Комфорт в новой компании','Инициативность','Сценарий знакомства','Неприемлемое поведение','Удобные дни','Комфортная цена','Источник','Согласие ПДн','Правила участия','Страница','UTM Source','UTM Medium','UTM Campaign','UTM Content','UTM Term','Referrer','User Agent','Дата клиента'];
const LOG_HEADERS=['Дата','Статус','Этап','ID заявки','Имя','Ошибка','Версия','Источник'];

function doGet(e){
  const p=(e&&e.parameter)||{};
  if(p.action==='status')return respond_(submissionStatus_(p.id),p.callback);
  return respond_({ok:true,service:'club-gravitation-applications',version:APP_VERSION},p.callback);
}

/** Запустить вручную из редактора Apps Script. Проверяет права на запись в Sheets + Drive. */
function testAccess(){
  const ss=SpreadsheetApp.openById(SPREADSHEET_ID);
  const folder=DriveApp.getFolderById(PHOTO_FOLDER_ID);
  const testFile=folder.createFile(Utilities.newBlob('permission test','text/plain','__gravitation_permission_test.txt'));
  const testFileId=testFile.getId();
  testFile.setTrashed(true);
  ensureLog_(ss);
  logEvent_('OK','testAccess','','','Доступ на чтение и запись в таблицу и папку подтверждён','editor');
  return {spreadsheet:ss.getName(),folder:folder.getName(),testFileId:testFileId,driveWrite:true,version:APP_VERSION};
}

function doPost(e){
  const p=(e&&e.parameter)||{};
  let stage='получение запроса';
  let id=validateParticipantId_(p.participant_id)||makeId_();
  try{
    if(p.website)return json_({ok:true});

    stage='проверка обязательных полей';
    require_(p.name,'name');
    const age=validateAge_(p.age);
    const city=validateCity_(p.city);
    const cityVisit=city==='Краснодар'?'Краснодар':requiredText_(p.city_visit,'city_visit');
    const phone=normalizePhone_(p.phone);
    const email=validateEmail_(p.email);
    require_(p.personal_data_consent,'personal_data_consent');
    require_(p.rules_consent,'rules_consent');
    require_(p.photo_data,'photo_data');
    const now=new Date();

    stage='открытие базы';
    const ss=SpreadsheetApp.openById(SPREADSHEET_ID);
    const participants=ensureParticipants_(ss);
    const raw=ensureRaw_(ss);
    ensureLog_(ss);

    const existingRow=findParticipantRow_(participants,id);
    if(existingRow){
      logEvent_('OK','повторное подтверждение',id,p.name||'','Заявка уже была записана',p.page_url||'site');
      return json_({ok:true,id:id,duplicate:true,version:APP_VERSION});
    }

    stage='сохранение фотографии';
    const photo=savePhoto_(p,id);

    stage='запись RAW';
    const rawValues=[now,id,p.name||'',age,p.gender||'',city,cityVisit,phone,p.telegram||'',email,p.preferred_contact||'',photo.url,p.occupation||'',p.life_beyond_work||'',p.interests||'',p.relationship_context||'',p.connection_goal||'',p.values_people||'',p.meeting_barriers||'',p.interest_reason||'',p.expectations||'',p.successful_evening||'',p.return_reason||'',p.social_comfort||'',p.initiative||'',p.introduction_scenario||'',p.unacceptable_behavior||'',p.convenient_days||'',p.comfortable_price||'',p.source||'Сайт / лендинг',p.personal_data_consent||'',p.rules_consent||'',p.page_url||'',p.utm_source||'',p.utm_medium||'',p.utm_campaign||'',p.utm_content||'',p.utm_term||'',p.referrer||'',p.user_agent||'',p.submitted_at_client||''];
    const rawRow=raw.getLastRow()+1;
    raw.getRange(rawRow,1,1,RAW_HEADERS.length).setValues([rawValues]);
    raw.getRange(rawRow,2).setNumberFormat('@').setValue(id);
    raw.getRange(rawRow,8).setNumberFormat('@').setValue(phone);

    stage='запись участника';
    const row=Object.fromEntries(PARTICIPANT_HEADERS.map(h=>[h,'']));
    Object.assign(row,{'ID':id,'Статус':'Новая заявка','Дата заявки':now,'Имя и фамилия':p.name||'','Возраст':age,'Пол':p.gender||'','Город':city,'Посещение Краснодара':cityVisit,'Телефон':phone,'Telegram':p.telegram||'','Email':email,'Как удобнее связаться?':p.preferred_contact||'','Чем занимается':p.occupation||'','Жизнь кроме работы':p.life_beyond_work||'','Интересы':p.interests||'','Контекст отношений':p.relationship_context||'','Какие знакомства интересны':p.connection_goal||'','Что ценит в людях':p.values_people||'','Что мешает знакомиться':p.meeting_barriers||'','Источник':p.source||'Сайт / лендинг','Что заинтересовало':p.interest_reason||'','Ожидания от мероприятия':p.expectations||'','Удачный вечер':p.successful_evening||'','Что заставит вернуться':p.return_reason||'','Комфорт в новой компании':p.social_comfort||'','Инициативность':p.initiative||'','Сценарий знакомства':p.introduction_scenario||'','Неприемлемое поведение':p.unacceptable_behavior||'','Удобные дни':p.convenient_days||'','Комфортная цена':p.comfortable_price||'','Согласие на связь':'Да','Согласие ПДн':p.personal_data_consent||'','Правила участия':p.rules_consent||'','Канал заявки':'Сайт','UTM Source':p.utm_source||'','UTM Medium':p.utm_medium||'','UTM Campaign':p.utm_campaign||'','UTM Content':p.utm_content||'','UTM Term':p.utm_term||'','Referrer':p.referrer||''});

    const participantRow=participants.getLastRow()+1;
    participants.getRange(participantRow,1,1,PARTICIPANT_HEADERS.length).setValues([PARTICIPANT_HEADERS.map(h=>row[h]??'')]);
    participants.getRange(participantRow,1).setNumberFormat('@').setValue(id);
    participants.getRange(participantRow,19).setNumberFormat('@').setValue(phone);

    const photoColumn=PARTICIPANT_HEADERS.indexOf('Фото')+1;
    const rich=SpreadsheetApp.newRichTextValue().setText('Открыть фото').setLinkUrl(photo.url).build();
    participants.getRange(participantRow,photoColumn).setRichTextValue(rich);

    stage='готово';
    logEvent_('OK',stage,id,p.name||'','',p.page_url||'site');
    return json_({ok:true,id:id,photo:photo.url,version:APP_VERSION});
  }catch(err){
    const message=String(err&&err.message?err.message:err);
    console.error(stage+': '+message);
    try{logEvent_('ERROR',stage,id,p.name||'',message,p.page_url||'site');}catch(logErr){console.error('log error: '+logErr);}
    return json_({ok:false,error:message,stage:stage,id:id,version:APP_VERSION});
  }
}

function submissionStatus_(value){
  const id=validateParticipantId_(value);
  if(!id)return {ok:false,found:true,error:'Некорректный номер заявки',stage:'проверка статуса',version:APP_VERSION};
  const ss=SpreadsheetApp.openById(SPREADSHEET_ID);
  const participants=ss.getSheetByName(PARTICIPANTS_SHEET);
  if(participants&&findParticipantRow_(participants,id))return {ok:true,found:true,id:id,status:'saved',version:APP_VERSION};

  const logs=ss.getSheetByName(LOG_SHEET);
  if(logs&&logs.getLastRow()>1){
    const range=logs.getRange(2,4,logs.getLastRow()-1,1);
    const matches=range.createTextFinder(id).matchEntireCell(true).findAll();
    if(matches.length){
      const last=matches[matches.length-1].getRow();
      const values=logs.getRange(last,1,1,8).getDisplayValues()[0];
      if(values[1]==='ERROR')return {ok:false,found:true,id:id,error:values[5]||'Ошибка сохранения заявки',stage:values[2]||'',version:APP_VERSION};
      if(values[1]==='OK'&&values[2]==='готово')return {ok:true,found:true,id:id,status:'saved',version:APP_VERSION};
    }
  }
  return {ok:false,found:false,pending:true,id:id,version:APP_VERSION};
}

function findParticipantRow_(sheet,id){
  if(!sheet||sheet.getLastRow()<2)return 0;
  const match=sheet.getRange(2,1,sheet.getLastRow()-1,1).createTextFinder(id).matchEntireCell(true).findNext();
  return match?match.getRow():0;
}

function savePhoto_(p,id){
  const base64=String(p.photo_data||'').trim();
  if(!base64)throw new Error('Фотография обязательна');
  const bytes=Utilities.base64Decode(base64);
  if(bytes.length>8*1024*1024)throw new Error('Фотография слишком большая');
  const mime=String(p.photo_type||'image/jpeg');
  if(!/^image\/(jpeg|png|webp)$/i.test(mime))throw new Error('Неподдерживаемый формат фотографии');
  const ext=mime.toLowerCase().includes('png')?'png':mime.toLowerCase().includes('webp')?'webp':'jpg';
  const safeName=sanitizeFileName_(p.name||'participant');
  const blob=Utilities.newBlob(bytes,mime,`${id}_${safeName}.${ext}`);
  const folder=DriveApp.getFolderById(PHOTO_FOLDER_ID);
  const file=folder.createFile(blob);
  return {id:file.getId(),url:file.getUrl(),name:file.getName()};
}

function ensureParticipants_(ss){let sheet=ss.getSheetByName(PARTICIPANTS_SHEET);if(!sheet)sheet=ss.insertSheet(PARTICIPANTS_SHEET);ensureColumns_(sheet,PARTICIPANT_HEADERS.length);const current=sheet.getRange(1,1,1,PARTICIPANT_HEADERS.length).getValues()[0];PARTICIPANT_HEADERS.forEach((header,idx)=>{if(current[idx]!==header)sheet.getRange(1,idx+1).setValue(header);});sheet.setFrozenRows(1);if(sheet.getMaxRows()>1){sheet.getRange(2,1,sheet.getMaxRows()-1,1).setNumberFormat('@');sheet.getRange(2,19,sheet.getMaxRows()-1,1).setNumberFormat('@');}return sheet;}
function ensureRaw_(ss){let sheet=ss.getSheetByName(WEB_RAW_SHEET);if(!sheet)sheet=ss.insertSheet(WEB_RAW_SHEET);ensureColumns_(sheet,RAW_HEADERS.length);const current=sheet.getRange(1,1,1,RAW_HEADERS.length).getValues()[0];if(current.join('|')!==RAW_HEADERS.join('|'))sheet.getRange(1,1,1,RAW_HEADERS.length).setValues([RAW_HEADERS]);sheet.setFrozenRows(1);if(sheet.getMaxRows()>1){sheet.getRange(2,2,sheet.getMaxRows()-1,1).setNumberFormat('@');sheet.getRange(2,8,sheet.getMaxRows()-1,1).setNumberFormat('@');}return sheet;}
function ensureLog_(ss){let sheet=ss.getSheetByName(LOG_SHEET);if(!sheet)sheet=ss.insertSheet(LOG_SHEET);ensureColumns_(sheet,LOG_HEADERS.length);const current=sheet.getRange(1,1,1,LOG_HEADERS.length).getValues()[0];if(current.join('|')!==LOG_HEADERS.join('|'))sheet.getRange(1,1,1,LOG_HEADERS.length).setValues([LOG_HEADERS]);sheet.setFrozenRows(1);return sheet;}
function logEvent_(status,stage,id,name,error,source){const ss=SpreadsheetApp.openById(SPREADSHEET_ID);const sheet=ensureLog_(ss);sheet.appendRow([new Date(),status,stage,id||'',name||'',error||'',APP_VERSION,source||'']);}
function ensureColumns_(sheet,count){const current=sheet.getMaxColumns();if(current<count)sheet.insertColumnsAfter(current,count-current);}
function validateAge_(value){const age=Number(value);if(!Number.isInteger(age)||age<25||age>52)throw new Error('Возраст должен быть от 25 до 52');return age;}
function validateCity_(value){const city=String(value||'').trim();if(!YUFO_CITIES.includes(city))throw new Error('Выберите город из списка ЮФО');return city;}
function normalizePhone_(value){let digits=String(value||'').replace(/\D/g,'');if(digits.length===11&&(digits.startsWith('7')||digits.startsWith('8')))digits=digits.slice(1);if(digits.length!==10)throw new Error('Телефон должен быть в формате +7 и 10 цифр');return '+7'+digits;}
function validateEmail_(value){const email=String(value||'').trim();if(!email)return '';if(!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/u.test(email))throw new Error('Некорректный email');return email;}
function validateParticipantId_(value){const id=String(value||'').trim();return /^GR-\d{6}-\d{6}-\d{2}$/.test(id)?id:'';}
function makeId_(){return 'GR-'+Utilities.formatDate(new Date(),'Europe/Moscow','yyMMdd-HHmmss')+'-'+String(Math.floor(Math.random()*100)).padStart(2,'0');}
function sanitizeFileName_(value){return String(value||'participant').trim().replace(/[^0-9A-Za-zА-Яа-яЁё_-]+/g,'-').replace(/-+/g,'-').replace(/^-|-$/g,'').slice(0,70)||'participant';}
function requiredText_(value,name){const text=String(value||'').trim();if(!text)throw new Error('Required field: '+name);return text;}
function require_(value,name){requiredText_(value,name);}
function respond_(obj,callback){
  const cb=String(callback||'').trim();
  if(cb&&/^[A-Za-z_$][0-9A-Za-z_$]*$/.test(cb))return ContentService.createTextOutput(`${cb}(${JSON.stringify(obj)});`).setMimeType(ContentService.MimeType.JAVASCRIPT);
  return json_(obj);
}
function json_(obj){return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);}
