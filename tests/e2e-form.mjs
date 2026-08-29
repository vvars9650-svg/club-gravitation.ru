import { chromium, devices } from 'playwright';
import fs from 'node:fs';

const SITE = process.env.SITE_URL || 'https://club-gravitation.ru/';
const runTag = process.env.GITHUB_RUN_ID || String(Date.now());
const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAD0lEQVR42mP8z8AARAwMDAAANgEDasKb6QAAAABJRU5ErkJggg==', 'base64');

async function fillAndSubmit(scope, label) {
  await scope.locator('input[name="name"]').fill(`E2E ${label} ${runTag}`);
  await scope.locator('select[name="age"]').selectOption('33');
  await scope.locator('select[name="gender"]').selectOption({ label: 'Мужчина' });
  await scope.locator('select[name="city"]').selectOption({ label: 'Краснодар' });
  await scope.locator('input[name="phone"]').fill('+7 999 111-22-33');
  await scope.locator('input[name="email"]').fill(`e2e-${label.toLowerCase()}-${runTag}@example.com`);

  await scope.locator('.step[data-step="0"] [data-next]').click();
  await scope.locator('#photo').setInputFiles({ name: `e2e-${label}.png`, mimeType: 'image/png', buffer: png });
  await scope.locator('#photo-preview img').waitFor({ state: 'visible' });
  await scope.locator('.step[data-step="1"] [data-next]').click();
  await scope.locator('.step[data-step="2"] [data-next]').click();
  await scope.locator('.step[data-step="3"] [data-next]').click();
  await scope.locator('.step[data-step="4"] [data-next]').click();

  const finalStep = scope.locator('.step[data-step="5"]');
  await finalStep.waitFor({ state: 'visible' });
  if (await finalStep.locator('[data-next]').count()) {
    throw new Error(`${label}: final step unexpectedly contains a Next button`);
  }

  await finalStep.locator('input[name="personal_data_consent"]').check();
  await finalStep.locator('input[name="rules_consent"]').check();
  await finalStep.locator('#submit').click();

  const success = scope.locator('#success');
  await success.waitFor({ state: 'visible', timeout: 60000 });
  const id = (await scope.locator('#success-id').textContent())?.trim();
  if (!id || !/^GR-/.test(id)) throw new Error(`${label}: no participant ID after successful submit`);
  return id;
}

const browser = await chromium.launch();
const result = {};
try {
  // Desktop: exercise the exact iframe path used on the live site.
  const desktop = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  await desktop.goto(`${SITE}?e2e=${runTag}`, { waitUntil: 'domcontentloaded', timeout: 60000 });
  const frame = desktop.frameLocator('#application-frame');
  await frame.locator('#application-form').waitFor({ state: 'visible', timeout: 60000 });
  result.desktop = await fillAndSubmit(frame, 'DESKTOP');
  await desktop.close();

  // Android-like Chromium: verify closed/open navigation and the direct-form fallback.
  const mobile = await browser.newContext({ ...devices['Pixel 7'] });
  const page = await mobile.newPage();
  await page.goto(`${SITE}?e2e=${runTag}`, { waitUntil: 'domcontentloaded', timeout: 60000 });
  const faqLink = page.locator('.nav a[href="#faq"]');
  if (await faqLink.isVisible()) throw new Error('MOBILE: navigation link leaks into closed header');
  await page.locator('.menu-toggle').click();
  await faqLink.waitFor({ state: 'visible' });
  await page.locator('.menu-toggle').click();
  await faqLink.waitFor({ state: 'hidden' });

  await page.locator('#apply').scrollIntoViewIfNeeded();
  const mobileCard = page.locator('.mobile-apply-card');
  await mobileCard.waitFor({ state: 'visible' });
  if (await page.locator('#application-frame').isVisible()) throw new Error('MOBILE: iframe should not be visible');
  await mobileCard.locator('a').click();
  await page.locator('#application-form').waitFor({ state: 'visible', timeout: 60000 });
  result.mobile = await fillAndSubmit(page, 'MOBILE');
  await mobile.close();

  fs.writeFileSync('e2e-output.json', JSON.stringify(result, null, 2));
  console.log(`E2E_DESKTOP_ID=${result.desktop}`);
  console.log(`E2E_MOBILE_ID=${result.mobile}`);
} finally {
  await browser.close();
}
