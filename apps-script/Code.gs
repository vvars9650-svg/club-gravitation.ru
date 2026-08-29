/**
 * ГРАВИТАЦИЯ — приём заявок сайта в Google Sheets.
 *
 * После изменения этого файла обновите код в Apps Script и создайте новую версию веб-приложения.
 */
const SPREADSHEET_ID='1pt69LEjrPiCPTF6ZzR_Lc6k-uXjW6qyXURBNqT_EsTw';
const PARTICIPANTS_SHEET='Участники';
const WEB_RAW_SHEET='Сайт — RAW';
const YUFO_CITIES=["Абинск","Адыгейск","Азов","Аксай","Алупка","Алушта","Анапа","Апшеронск","Армавир","Армянск","Астрахань","Ахтубинск","Батайск","Бахчисарай","Белая Калитва","Белогорск","Белореченск","Волгоград","Волгодонск","Волжский","Геленджик","Городовиковск","Горячий Ключ","Гуково","Гулькевичи","Джанкой","Донецк","Дубовка","Евпатория","Ейск","Жирновск","Зверево","Зерноград","Знаменск","Калач-на-Дону","Каменск-Шахтинский","Камызяк","Камышин","Керчь","Константиновск","Кореновск","Котельниково","Котово","Краснодар","Красноперекопск","Краснослободск","Красный Сулин","Кропоткин","Крымск","Курганинск","Лабинск","Лагань","Ленинск","Майкоп","Миллерово","Михайловка","Морозовск","Нариманов","Николаевск","Новоаннинский","Новокубанск","Новороссийск","Новочеркасск","Новошахтинск","Палласовка","Петров Вал","Приморско-Ахтарск","Пролетарск","Ростов-на-Дону","Саки","Сальск","Севастополь","Семикаракорск","Серафимович","Симферополь","Славянск-на-Кубани","Сочи","Старый Крым","Судак","Суровикино","Таганрог","Темрюк","Тимашёвск","Тихорецк","Туапсе","Урюпинск","Усть-Лабинск","Феодосия","Фролово","Хадыженск","Харабали","Цимлянск","Шахты","Щёлкино","Элиста","Ялта"];
const PARTICIPANT_HEADERS=['ID','Статус','Приоритет','Ответственный','Следующий шаг','Дата следующего контакта','Дата интервью','Решение','Комментарий','Ближайшее мероприятие','Количество посещений','Последнее участие','Дата заявки','Имя и фамилия','Возраст','Пол','Город','Посещение Краснодара','Телефон','Telegram','ВКонтакте','Instagram','Email','Как удобнее связаться?','Фото','Чем занимается','Жизнь кроме работы','Интересы','Контекст отношений','Какие знакомства интересны','Что ценит в людях','Что мешает знакомиться','Источник','Что заинтересовало','Ожидания от мероприятия','Удачный вечер','Что заставит вернуться','Комфорт в новой компании','Инициативность','Сценарий знакомства','Неприемлемое поведение','Удобные дни','Комфортная цена','Согласие на связь','Согласие ПДн','Правила участия','Канал заявки','UTM Source','UTM Medium','UTM Campaign','UTM Content','UTM Term','Referrer'];
const RAW_HEADERS=['Дата сервера','ID','Имя и фамилия','Возраст','Пол','Город','Телефон','Telegram','Email','Как удобнее связаться','Чем занимается','Интересы','Контекст отношений','Какие знакомства интересны','Что заинтересовало','Ожидания','Источник','Согласие ПДн','Правила участия','Страница','UTM Source','UTM Medium','UTM Campaign','UTM Content','UTM Term','Referrer','User Agent','Дата клиента'];

function doGet(){return json_({ok:true,service:'club-gravitation-applications'});}

function doPost(e){
  try{
    const p=(e&&e.parameter)||{};
    if(p.website)return json_({ok:true});

    require_(p.name,'name');
    const age=validateAge_(p.age);
    const city=validateCity_(p.city);
    const phone=normalizePhone_(p.phone);
    const email=validateEmail_(p.email);
    require_(p.personal_data_consent,'personal_data_consent');
    require_(p.rules_consent,'rules_consent');

    const ss=SpreadsheetApp.openById(SPREADSHEET_ID);
    const participants=ensureParticipants_(ss);
    const raw=ensureRaw_(ss);
    const id=makeId_();
    const now=new Date();

    const rawRow=raw.getLastRow()+1;
    raw.getRange(rawRow,1,1,RAW_HEADERS.length).setValues([[
      now,id,p.name||'',age,p.gender||'',city,phone,p.telegram||'',email,p.preferred_contact||'',
      p.occupation||'',p.interests||'',p.relationship_context||'',p.connection_goal||'',
      p.interest_reason||'',p.expectations||'',p.source||'Сайт / лендинг',
      p.personal_data_consent||'',p.rules_consent||'',p.page_url||'',p.utm_source||'',
      p.utm_medium||'',p.utm_campaign||'',p.utm_content||'',p.utm_term||'',p.referrer||'',
      p.user_agent||'',p.submitted_at_client||''
    ]]);
    raw.getRange(rawRow,7).setNumberFormat('@').setValue(phone);

    const row=Object.fromEntries(PARTICIPANT_HEADERS.map(h=>[h,'']));
    Object.assign(row,{
      'ID':id,'Статус':'Новая заявка','Дата заявки':now,'Имя и фамилия':p.name||'',
      'Возраст':age,'Пол':p.gender||'','Город':city,'Телефон':phone,'Telegram':p.telegram||'',
      'Email':email,'Как удобнее связаться?':p.preferred_contact||'','Чем занимается':p.occupation||'',
      'Интересы':p.interests||'','Контекст отношений':p.relationship_context||'',
      'Какие знакомства интересны':p.connection_goal||'','Источник':p.source||'Сайт / лендинг',
      'Что заинтересовало':p.interest_reason||'','Ожидания от мероприятия':p.expectations||'',
      'Согласие на связь':'Да','Согласие ПДн':p.personal_data_consent||'',
      'Правила участия':p.rules_consent||'','Канал заявки':'Сайт','UTM Source':p.utm_source||'',
      'UTM Medium':p.utm_medium||'','UTM Campaign':p.utm_campaign||'','UTM Content':p.utm_content||'',
      'UTM Term':p.utm_term||'','Referrer':p.referrer||''
    });
    const participantRow=participants.getLastRow()+1;
    participants.getRange(participantRow,1,1,PARTICIPANT_HEADERS.length)
      .setValues([PARTICIPANT_HEADERS.map(h=>row[h]??'')]);
    participants.getRange(participantRow,19).setNumberFormat('@').setValue(phone);

    return json_({ok:true,id});
  }catch(err){
    console.error(err);
    return json_({ok:false,error:String(err.message||err)});
  }
}

function ensureParticipants_(ss){
  let sheet=ss.getSheetByName(PARTICIPANTS_SHEET);
  if(!sheet)sheet=ss.insertSheet(PARTICIPANTS_SHEET);
  const currentLastColumn=Math.max(sheet.getLastColumn(),1);
  const currentHeaders=sheet.getRange(1,1,1,currentLastColumn).getValues()[0];
  PARTICIPANT_HEADERS.forEach((header,idx)=>{
    if(currentHeaders[idx]!==header)sheet.getRange(1,idx+1).setValue(header);
  });
  sheet.setFrozenRows(1);
  if(sheet.getMaxRows()>1)sheet.getRange(2,19,sheet.getMaxRows()-1,1).setNumberFormat('@');
  return sheet;
}

function ensureRaw_(ss){
  let sheet=ss.getSheetByName(WEB_RAW_SHEET);
  if(!sheet)sheet=ss.insertSheet(WEB_RAW_SHEET);
  const current=sheet.getRange(1,1,1,RAW_HEADERS.length).getValues()[0];
  if(current.join('|')!==RAW_HEADERS.join('|')){
    sheet.getRange(1,1,1,RAW_HEADERS.length).setValues([RAW_HEADERS]);
    sheet.setFrozenRows(1);
  }
  if(sheet.getMaxRows()>1)sheet.getRange(2,7,sheet.getMaxRows()-1,1).setNumberFormat('@');
  return sheet;
}

function validateAge_(value){
  const age=Number(value);
  if(!Number.isInteger(age)||age<25||age>52)throw new Error('Возраст должен быть от 25 до 52');
  return age;
}

function validateCity_(value){
  const city=String(value||'').trim();
  if(!YUFO_CITIES.includes(city))throw new Error('Выберите город из списка ЮФО');
  return city;
}

function normalizePhone_(value){
  let digits=String(value||'').replace(/\D/g,'');
  if(digits.length===11&&(digits.startsWith('7')||digits.startsWith('8')))digits=digits.slice(1);
  if(digits.length!==10)throw new Error('Телефон должен быть в формате +7 и 10 цифр');
  return '+7'+digits;
}

function validateEmail_(value){
  const email=String(value||'').trim();
  if(!email)return '';
  if(!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/u.test(email))throw new Error('Некорректный email');
  return email;
}

function makeId_(){return 'GR-WEB-'+Utilities.formatDate(new Date(),'Europe/Moscow','yyyyMMdd-HHmmss');}
function require_(value,name){if(!String(value||'').trim())throw new Error('Required field: '+name);}
function json_(obj){return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);}
