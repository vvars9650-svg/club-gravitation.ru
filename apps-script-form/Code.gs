/**
 * ГРАВИТАЦИЯ — отдельное веб-приложение анкеты.
 * Архитектура: HtmlService + google.script.run. Без CORS, JSONP и внешнего POST.
 */
const APP_VERSION = 'FORM-1';
const SPREADSHEET_ID = '1pt69LEjrPiCPTF6ZzR_Lc6k-uXjW6qyXURBNqT_EsTw';
const PARTICIPANTS_SHEET = 'Участники';
const WEB_RAW_SHEET = 'Сайт — RAW';
const LOG_SHEET = 'Сайт — Логи';
const PHOTO_FOLDER_ID = '1jIObgJ6szGwEGHRjUGC_D7qHbAyLIfFV';

const YUFO_CITIES = ["Абинск","Адыгейск","Азов","Аксай","Алупка","Алушта","Анапа","Апшеронск","Армавир","Армянск","Астрахань","Ахтубинск","Батайск","Бахчисарай","Белая Калитва","Белогорск","Белореченск","Волгоград","Волгодонск","Волжский","Геленджик","Городовиковск","Горячий Ключ","Гуково","Гулькевичи","Джанкой","Донецк","Дубовка","Евпатория","Ейск","Жирновск","Зверево","Зерноград","Знаменск","Инкерман","Калач-на-Дону","Каменск-Шахтинский","Камызяк","Камышин","Керчь","Константиновск","Кореновск","Котельниково","Котово","Краснодар","Красноперекопск","Краснослободск","Красный Сулин","Кропоткин","Крымск","Курганинск","Лабинск","Лагань","Ленинск","Майкоп","Миллерово","Михайловка","Морозовск","Нариманов","Николаевск","Новоаннинский","Новокубанск","Новороссийск","Новочеркасск","Новошахтинск","Палласовка","Петров Вал","Приморско-Ахтарск","Пролетарск","Ростов-на-Дону","Саки","Сальск","Севастополь","Семикаракорск","Серафимович","Симферополь","Славянск-на-Кубани","Сочи","Старый Крым","Судак","Суровикино","Таганрог","Темрюк","Тимашёвск","Тихорецк","Туапсе","Урюпинск","Усть-Лабинск","Феодосия","Фролово","Хадыженск","Харабали","Цимлянск","Шахты","Щёлкино","Элиста","Ялта"];

const PARTICIPANT_HEADERS = ['ID','Статус','Приоритет','Ответственный','Следующий шаг','Дата следующего контакта','Дата интервью','Решение','Комментарий','Ближайшее мероприятие','Количество посещений','Последнее участие','Дата заявки','Имя и фамилия','Возраст','Пол','Город','Посещение Краснодара','Телефон','Telegram','ВКонтакте','Instagram','Email','Как удобнее связаться?','Фото','Чем занимается','Жизнь кроме работы','Интересы','Контекст отношений','Какие знакомства интересны','Что ценит в людях','Что мешает знакомиться','Источник','Что заинтересовало','Ожидания от мероприятия','Удачный вечер','Что заставит вернуться','Комфорт в новой компании','Инициативность','Сценарий знакомства','Неприемлемое поведение','Удобные дни','Комфортная цена','Согласие на связь','Согласие ПДн','Правила участия','Канал заявки','UTM Source','UTM Medium','UTM Campaign','UTM Content','UTM Term','Referrer'];
const RAW_HEADERS = ['Дата сервера','ID','Имя и фамилия','Возраст','Пол','Город','Посещение Краснодара','Телефон','Telegram','Email','Как удобнее связаться','Фото URL','Чем занимается','Жизнь кроме работы','Интересы','Контекст отношений','Какие знакомства интересны','Что ценит в людях','Что мешает знакомиться','Что заинтересовало','Ожидания','Удачный вечер','Что заставит вернуться','Комфорт в новой компании','Инициативность','Сценарий знакомства','Неприемлемое поведение','Удобные дни','Комфортная цена','Источник','Согласие ПДн','Правила участия','Страница','UTM Source','UTM Medium','UTM Campaign','UTM Content','UTM Term','Referrer','User Agent','Дата клиента'];
const LOG_HEADERS = ['Дата','Статус','Этап','ID заявки','Имя','Ошибка','Версия','Источник'];

function doGet() {
  const template = HtmlService.createTemplateFromFile('Index');
  template.citiesJson = JSON.stringify(YUFO_CITIES).replace(/</g, '\\u003c');
  template.appVersion = APP_VERSION;
  return template.evaluate()
    .setTitle('Гравитация — анкета участника')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1, viewport-fit=cover')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

function include_(filename) {
  return HtmlService.createHtmlOutputFromFile(filename).getContent();
}

/**
 * Вызывается только из HtmlService через google.script.run.
 * При передаче <form> Google сам преобразует input[type=file] в Blob.
 */
function saveApplication(form) {
  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  let stage = 'получение анкеты';
  let id = '';
  let photoFile = null;
  try {
    if (!form || form.website) return {ok: true, ignored: true};

    stage = 'проверка данных';
    const name = requiredText_(form.name, 'Имя и фамилия');
    const age = validateAge_(form.age);
    const gender = requiredText_(form.gender, 'Пол');
    const city = validateCity_(form.city);
    const cityVisit = city === 'Краснодар' ? 'Краснодар' : requiredText_(form.city_visit, 'Посещение Краснодара');
    const phone = normalizePhone_(form.phone);
    const email = validateEmail_(form.email);
    if (!form.personal_data_consent) throw new Error('Необходимо согласие на обработку персональных данных');
    if (!form.rules_consent) throw new Error('Необходимо согласие с правилами участия');
    validatePhotoBlob_(form.photo);

    id = makeId_();
    const now = new Date();

    stage = 'открытие базы';
    const ss = SpreadsheetApp.openById(SPREADSHEET_ID);
    const participants = ensureParticipants_(ss);
    const raw = ensureRaw_(ss);
    ensureLog_(ss);

    stage = 'сохранение фотографии';
    photoFile = savePhotoBlob_(form.photo, id, name);
    const photoUrl = photoFile.getUrl();

    const connectionGoal = multiValue_(form.connection_goal);
    const convenientDays = multiValue_(form.convenient_days);
    const source = text_(form.source) || 'Сайт / анкета';
    const pageUrl = text_(form.page_url) || 'Apps Script form';

    stage = 'запись участника';
    const row = Object.fromEntries(PARTICIPANT_HEADERS.map(h => [h, '']));
    Object.assign(row, {
      'ID': id,
      'Статус': 'Новая заявка',
      'Дата заявки': now,
      'Имя и фамилия': name,
      'Возраст': age,
      'Пол': gender,
      'Город': city,
      'Посещение Краснодара': cityVisit,
      'Телефон': phone,
      'Telegram': text_(form.telegram),
      'Email': email,
      'Как удобнее связаться?': text_(form.preferred_contact),
      'Чем занимается': text_(form.occupation),
      'Жизнь кроме работы': text_(form.life_beyond_work),
      'Интересы': text_(form.interests),
      'Контекст отношений': text_(form.relationship_context),
      'Какие знакомства интересны': connectionGoal,
      'Что ценит в людях': text_(form.values_people),
      'Что мешает знакомиться': text_(form.meeting_barriers),
      'Источник': source,
      'Что заинтересовало': text_(form.interest_reason),
      'Ожидания от мероприятия': text_(form.expectations),
      'Удачный вечер': text_(form.successful_evening),
      'Что заставит вернуться': text_(form.return_reason),
      'Комфорт в новой компании': text_(form.social_comfort),
      'Инициативность': text_(form.initiative),
      'Сценарий знакомства': text_(form.introduction_scenario),
      'Неприемлемое поведение': text_(form.unacceptable_behavior),
      'Удобные дни': convenientDays,
      'Комфортная цена': text_(form.comfortable_price),
      'Согласие на связь': 'Да',
      'Согласие ПДн': 'Да',
      'Правила участия': 'Да',
      'Канал заявки': 'Сайт',
      'UTM Source': text_(form.utm_source),
      'UTM Medium': text_(form.utm_medium),
      'UTM Campaign': text_(form.utm_campaign),
      'UTM Content': text_(form.utm_content),
      'UTM Term': text_(form.utm_term),
      'Referrer': text_(form.referrer)
    });

    const participantRow = participants.getLastRow() + 1;
    participants.getRange(participantRow, 1, 1, PARTICIPANT_HEADERS.length)
      .setValues([PARTICIPANT_HEADERS.map(h => row[h] ?? '')]);
    participants.getRange(participantRow, 1).setNumberFormat('@').setValue(id);
    participants.getRange(participantRow, 19).setNumberFormat('@').setValue(phone);
    const photoColumn = PARTICIPANT_HEADERS.indexOf('Фото') + 1;
    participants.getRange(participantRow, photoColumn).setRichTextValue(
      SpreadsheetApp.newRichTextValue().setText('Открыть фото').setLinkUrl(photoUrl).build()
    );

    stage = 'запись RAW';
    const rawValues = [
      now,id,name,age,gender,city,cityVisit,phone,text_(form.telegram),email,text_(form.preferred_contact),photoUrl,
      text_(form.occupation),text_(form.life_beyond_work),text_(form.interests),text_(form.relationship_context),connectionGoal,
      text_(form.values_people),text_(form.meeting_barriers),text_(form.interest_reason),text_(form.expectations),
      text_(form.successful_evening),text_(form.return_reason),text_(form.social_comfort),text_(form.initiative),
      text_(form.introduction_scenario),text_(form.unacceptable_behavior),convenientDays,text_(form.comfortable_price),source,
      'Да','Да',pageUrl,text_(form.utm_source),text_(form.utm_medium),text_(form.utm_campaign),text_(form.utm_content),
      text_(form.utm_term),text_(form.referrer),text_(form.user_agent),text_(form.submitted_at_client)
    ];
    const rawRow = raw.getLastRow() + 1;
    raw.getRange(rawRow, 1, 1, RAW_HEADERS.length).setValues([rawValues]);
    raw.getRange(rawRow, 2).setNumberFormat('@').setValue(id);
    raw.getRange(rawRow, 8).setNumberFormat('@').setValue(phone);

    logEvent_('OK', 'готово', id, name, '', pageUrl);
    return {ok: true, id: id, version: APP_VERSION};
  } catch (err) {
    const message = String(err && err.message ? err.message : err);
    try { logEvent_('ERROR', stage, id, form && form.name ? String(form.name) : '', message, 'Apps Script form'); } catch (_) {}
    if (photoFile && id) {
      try { photoFile.setTrashed(true); } catch (_) {}
    }
    throw new Error(message);
  } finally {
    try { lock.releaseLock(); } catch (_) {}
  }
}

function validatePhotoBlob_(blob) {
  if (!blob || typeof blob.getBytes !== 'function') throw new Error('Фотография обязательна');
  const bytes = blob.getBytes();
  if (!bytes || !bytes.length) throw new Error('Фотография обязательна');
  if (bytes.length > 10 * 1024 * 1024) throw new Error('Фотография должна быть не больше 10 МБ');
  const mime = String(blob.getContentType() || '').toLowerCase();
  if (!/^image\/(jpeg|png|webp)$/.test(mime)) throw new Error('Поддерживаются JPG, PNG и WEBP');
}

function savePhotoBlob_(blob, id, name) {
  validatePhotoBlob_(blob);
  const mime = String(blob.getContentType()).toLowerCase();
  const ext = mime.includes('png') ? 'png' : mime.includes('webp') ? 'webp' : 'jpg';
  blob.setName(`${id}_${sanitizeFileName_(name)}.${ext}`);
  return DriveApp.getFolderById(PHOTO_FOLDER_ID).createFile(blob);
}

function ensureParticipants_(ss) {
  let sheet = ss.getSheetByName(PARTICIPANTS_SHEET);
  if (!sheet) sheet = ss.insertSheet(PARTICIPANTS_SHEET);
  ensureColumns_(sheet, PARTICIPANT_HEADERS.length);
  const current = sheet.getRange(1,1,1,PARTICIPANT_HEADERS.length).getValues()[0];
  PARTICIPANT_HEADERS.forEach((header, idx) => {
    if (current[idx] !== header) sheet.getRange(1, idx + 1).setValue(header);
  });
  sheet.setFrozenRows(1);
  return sheet;
}

function ensureRaw_(ss) {
  let sheet = ss.getSheetByName(WEB_RAW_SHEET);
  if (!sheet) sheet = ss.insertSheet(WEB_RAW_SHEET);
  ensureColumns_(sheet, RAW_HEADERS.length);
  const current = sheet.getRange(1,1,1,RAW_HEADERS.length).getValues()[0];
  if (current.join('|') !== RAW_HEADERS.join('|')) sheet.getRange(1,1,1,RAW_HEADERS.length).setValues([RAW_HEADERS]);
  sheet.setFrozenRows(1);
  return sheet;
}

function ensureLog_(ss) {
  let sheet = ss.getSheetByName(LOG_SHEET);
  if (!sheet) sheet = ss.insertSheet(LOG_SHEET);
  ensureColumns_(sheet, LOG_HEADERS.length);
  const current = sheet.getRange(1,1,1,LOG_HEADERS.length).getValues()[0];
  if (current.join('|') !== LOG_HEADERS.join('|')) sheet.getRange(1,1,1,LOG_HEADERS.length).setValues([LOG_HEADERS]);
  sheet.setFrozenRows(1);
  return sheet;
}

function logEvent_(status, stage, id, name, error, source) {
  const ss = SpreadsheetApp.openById(SPREADSHEET_ID);
  ensureLog_(ss).appendRow([new Date(), status, stage, id || '', name || '', error || '', APP_VERSION, source || '']);
}

function ensureColumns_(sheet, count) {
  if (sheet.getMaxColumns() < count) sheet.insertColumnsAfter(sheet.getMaxColumns(), count - sheet.getMaxColumns());
}

function validateAge_(value) {
  const age = Number(value);
  if (!Number.isInteger(age) || age < 25 || age > 52) throw new Error('Возраст должен быть от 25 до 52');
  return age;
}

function validateCity_(value) {
  const city = text_(value);
  if (!YUFO_CITIES.includes(city)) throw new Error('Выберите город из списка ЮФО');
  return city;
}

function normalizePhone_(value) {
  let digits = text_(value).replace(/\D/g, '');
  if (digits.length === 11 && (digits.startsWith('7') || digits.startsWith('8'))) digits = digits.slice(1);
  if (digits.length !== 10) throw new Error('Телефон должен быть в формате +7 и 10 цифр');
  return '+7' + digits;
}

function validateEmail_(value) {
  const email = text_(value);
  if (!email) return '';
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/u.test(email)) throw new Error('Некорректный email');
  return email;
}

function requiredText_(value, label) {
  const result = text_(value);
  if (!result) throw new Error(`Заполните поле «${label}»`);
  return result;
}

function text_(value) {
  if (Array.isArray(value)) return value.map(v => String(v || '').trim()).filter(Boolean).join(', ');
  return String(value == null ? '' : value).trim();
}

function multiValue_(value) {
  return text_(value);
}

function makeId_() {
  return 'GR-' + Utilities.formatDate(new Date(), 'Europe/Moscow', 'yyMMdd-HHmmss') + '-' + String(Math.floor(Math.random() * 100)).padStart(2, '0');
}

function sanitizeFileName_(value) {
  return text_(value).replace(/[^0-9A-Za-zА-Яа-яЁё_-]+/g, '-').replace(/-+/g, '-').replace(/^-|-$/g, '').slice(0,70) || 'participant';
}
