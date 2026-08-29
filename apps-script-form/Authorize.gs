/**
 * One-time authorization probe for CI/CD and manual diagnostics.
 * Touch 2026-08-29: trigger clasp pipeline after base64 secret setup.
 */
function authorizeFormApp_() {
  const ss = SpreadsheetApp.openById(SPREADSHEET_ID);
  const folder = DriveApp.getFolderById(PHOTO_FOLDER_ID);
  const testFile = folder.createFile(Utilities.newBlob('permission test','text/plain','__gravitation_form_permission_test.txt'));
  const testFileId = testFile.getId();
  testFile.setTrashed(true);
  ensureLog_(ss);
  logEvent_('OK','authorizeFormApp','','','Права на Sheets и Drive подтверждены','editor');
  return {spreadsheet:ss.getName(),folder:folder.getName(),testFileId:testFileId,version:APP_VERSION};
}
