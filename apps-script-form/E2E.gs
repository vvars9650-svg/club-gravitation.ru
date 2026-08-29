function e2eReady() {
  return {ok: true, marker: 'E2E-2'};
}

/**
 * Headless Chromium can hang while Apps Script serializes a synthetic File
 * inside a DOM <form>. Real Chrome submission is still handled by
 * saveApplication(form). For CI we generate a real PNG Blob on the server and
 * feed it into the exact same saveApplication() function, so Sheets/Drive and
 * success handling are exercised deterministically.
 */
function e2eSubmitApplication(payload) {
  const data = payload || {};
  const name = text_(data.name);
  if (!name.startsWith('E2E CI ')) throw new Error('E2E: invalid test name');

  const pngBase64 = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9ZQmcAAAAASUVORK5CYII=';
  const photo = Utilities.newBlob(Utilities.base64Decode(pngBase64), 'image/png', 'e2e-ci.png');

  const form = {
    website: '',
    name,
    age: text_(data.age) || '31',
    gender: text_(data.gender) || 'Мужчина',
    city: text_(data.city) || 'Краснодар',
    city_visit: text_(data.city_visit),
    phone: text_(data.phone) || '+79991234567',
    telegram: text_(data.telegram),
    email: text_(data.email) || 'e2e-ci@example.com',
    preferred_contact: text_(data.preferred_contact),
    occupation: text_(data.occupation),
    life_beyond_work: text_(data.life_beyond_work),
    interests: text_(data.interests),
    relationship_context: text_(data.relationship_context),
    connection_goal: data.connection_goal || '',
    values_people: text_(data.values_people),
    meeting_barriers: text_(data.meeting_barriers),
    interest_reason: text_(data.interest_reason),
    expectations: text_(data.expectations),
    successful_evening: text_(data.successful_evening),
    return_reason: text_(data.return_reason),
    social_comfort: text_(data.social_comfort),
    initiative: text_(data.initiative),
    introduction_scenario: text_(data.introduction_scenario),
    unacceptable_behavior: text_(data.unacceptable_behavior),
    convenient_days: data.convenient_days || '',
    comfortable_price: text_(data.comfortable_price),
    source: 'GitHub Actions E2E',
    personal_data_consent: 'Да',
    rules_consent: 'Да',
    page_url: text_(data.page_url) || 'GitHub Actions E2E',
    utm_source: 'github-actions',
    utm_medium: 'e2e',
    utm_campaign: 'form-regression',
    utm_content: text_(data.utm_content),
    utm_term: '',
    referrer: text_(data.referrer),
    user_agent: text_(data.user_agent) || 'Playwright E2E',
    submitted_at_client: text_(data.submitted_at_client) || new Date().toISOString(),
    photo
  };

  return saveApplication(form);
}

function e2eVerifyCleanup(id) {
  const safeId = text_(id);
  if (!safeId) throw new Error('E2E: empty id');

  const ss = SpreadsheetApp.openById(SPREADSHEET_ID);
  const participants = ss.getSheetByName(PARTICIPANTS_SHEET);
  const raw = ss.getSheetByName(WEB_RAW_SHEET);
  if (!participants || !raw) throw new Error('E2E: required sheets are missing');

  const participantRow = findE2ERowById_(participants, safeId, 1);
  const rawRow = findE2ERowById_(raw, safeId, 2);

  const participantNameCol = PARTICIPANT_HEADERS.indexOf('Имя и фамилия') + 1;
  const rawNameCol = RAW_HEADERS.indexOf('Имя и фамилия') + 1;
  const participantName = participantRow ? text_(participants.getRange(participantRow, participantNameCol).getValue()) : '';
  const rawName = rawRow ? text_(raw.getRange(rawRow, rawNameCol).getValue()) : '';
  const safeTestName = participantName || rawName;

  if (!safeTestName.startsWith('E2E CI ')) {
    throw new Error('E2E: cleanup refused for a non-test application');
  }

  const participantOk = Boolean(participantRow);
  const rawOk = Boolean(rawRow);

  const folder = DriveApp.getFolderById(PHOTO_FOLDER_ID);
  let photoFile = null;
  const files = folder.getFiles();
  while (files.hasNext()) {
    const candidate = files.next();
    if (candidate.getName().startsWith(safeId + '_')) {
      photoFile = candidate;
      break;
    }
  }

  const photoOk = Boolean(photoFile && photoFile.getSize() > 0 && !photoFile.isTrashed());
  let photoLinkOk = false;
  if (participantRow && photoFile) {
    const photoCol = PARTICIPANT_HEADERS.indexOf('Фото') + 1;
    const rich = participants.getRange(participantRow, photoCol).getRichTextValue();
    const link = rich ? rich.getLinkUrl() : '';
    photoLinkOk = Boolean(link && link.includes(photoFile.getId()));
  }

  if (photoFile) photoFile.setTrashed(true);
  if (rawRow) raw.deleteRow(rawRow);
  if (participantRow) participants.deleteRow(participantRow);
  SpreadsheetApp.flush();

  const participantClean = !findE2ERowById_(participants, safeId, 1);
  const rawClean = !findE2ERowById_(raw, safeId, 2);
  const photoClean = !photoFile || photoFile.isTrashed();
  const cleaned = participantClean && rawClean && photoClean;
  const ok = participantOk && rawOk && photoOk && photoLinkOk && cleaned;

  try {
    logEvent_(ok ? 'E2E_OK' : 'E2E_FAIL', 'verify+cleanup', safeId, safeTestName, ok ? '' : 'verification failed', 'GitHub Actions');
  } catch (_) {}

  return {
    ok,
    id: safeId,
    participant: participantOk,
    raw: rawOk,
    photo: photoOk,
    photoLink: photoLinkOk,
    cleaned
  };
}

function findE2ERowById_(sheet, id, column) {
  const lastRow = sheet.getLastRow();
  if (lastRow < 2) return 0;
  const match = sheet.getRange(2, column, lastRow - 1, 1)
    .createTextFinder(id)
    .matchEntireCell(true)
    .findNext();
  return match ? match.getRow() : 0;
}
