const { test, expect } = require('@playwright/test');

const SITE_URL = 'https://club-gravitation.ru/';
const PNG_1X1 = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9ZQmcAAAAASUVORK5CYII=',
  'base64'
);

test.setTimeout(240000);
test.describe.configure({ mode: 'serial' });

async function findFormFrame(page, timeout = 20000) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    for (const frame of page.frames()) {
      try {
        if (await frame.locator('#application-form').count()) return frame;
      } catch (_) {}
    }
    await page.waitForTimeout(500);
  }
  throw new Error('Apps Script application form frame was not found');
}

async function serverReady(frame) {
  return frame.evaluate(() => new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('e2eReady timeout')), 12000);
    google.script.run
      .withSuccessHandler(value => { clearTimeout(timer); resolve(value); })
      .withFailureHandler(error => { clearTimeout(timer); reject(new Error(error?.message || String(error))); })
      .e2eReady();
  }));
}

async function waitForServerReady(page) {
  let lastError = null;
  for (let attempt = 1; attempt <= 30; attempt += 1) {
    try {
      const frame = await findFormFrame(page, 12000);
      const ready = await serverReady(frame);
      if (ready && ready.ok === true && ready.marker === 'E2E-1') return frame;
    } catch (error) {
      lastError = error;
    }
    await page.waitForTimeout(4000);
    await page.reload({ waitUntil: 'domcontentloaded' });
  }
  throw lastError || new Error('Apps Script E2E helper was not deployed in time');
}

async function verifyAndCleanup(frame, id) {
  return frame.evaluate(applicationId => new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('e2eVerifyCleanup timeout')), 30000);
    google.script.run
      .withSuccessHandler(value => { clearTimeout(timer); resolve(value); })
      .withFailureHandler(error => { clearTimeout(timer); reject(new Error(error?.message || String(error))); })
      .e2eVerifyCleanup(applicationId);
  }), id);
}

async function fillAndSubmit(frame, label) {
  const form = frame.locator('#application-form');
  await expect(form).toBeVisible();

  await frame.locator('[name="name"]').fill(`E2E CI ${label} ${Date.now()}`);
  await frame.locator('[name="age"]').selectOption('31');
  await frame.locator('[name="gender"]').selectOption({ label: 'Мужчина' });
  await frame.locator('[name="city"]').selectOption({ label: 'Краснодар' });
  await frame.locator('[name="phone"]').fill('+7 999 123-45-67');
  await frame.locator('[name="email"]').fill('e2e-ci@example.com');

  await frame.locator('.step[data-step="0"] [data-next]').click();
  await expect(frame.locator('.step[data-step="1"]')).toHaveClass(/is-active/);

  await frame.locator('#photo').setInputFiles({
    name: 'e2e-photo.png',
    mimeType: 'image/png',
    buffer: PNG_1X1
  });
  await expect(frame.locator('#photo-preview img')).toBeVisible();
  await expect(frame.locator('#photo-name')).toContainText('e2e-photo.png');

  await frame.locator('.step[data-step="1"] [data-next]').click();
  await frame.locator('.step[data-step="2"] [data-next]').click();
  await frame.locator('.step[data-step="3"] [data-next]').click();
  await frame.locator('.step[data-step="4"] [data-next]').click();

  const finalStep = frame.locator('.step[data-step="5"]');
  await expect(finalStep).toHaveClass(/is-active/);
  await expect(finalStep.locator('[data-next]')).toHaveCount(0);
  await expect(finalStep.getByText('ДАЛЕЕ', { exact: true })).toHaveCount(0);

  await finalStep.locator('[name="personal_data_consent"]').check();
  await finalStep.locator('[name="rules_consent"]').check();
  await finalStep.locator('#submit').click();

  await expect(frame.locator('#success')).toBeVisible({ timeout: 45000 });
  const id = (await frame.locator('#success-id').textContent() || '').trim();
  expect(id).toMatch(/^GR-/);
  return id;
}

async function assertVerification(result) {
  expect(result).toMatchObject({
    ok: true,
    participant: true,
    raw: true,
    photo: true,
    photoLink: true,
    cleaned: true
  });
}

test('desktop: embedded form writes Sheets and Drive and confirms success', async ({ browser }) => {
  const context = await browser.newContext({ viewport: { width: 1365, height: 900 } });
  const page = await context.newPage();

  await page.goto(SITE_URL, { waitUntil: 'domcontentloaded' });
  await expect(page.locator('#main-nav')).toBeVisible();
  await page.locator('#apply').scrollIntoViewIfNeeded();
  await expect(page.locator('#application-frame')).toBeVisible();

  const frame = await waitForServerReady(page);
  const id = await fillAndSubmit(frame, 'Desktop');
  const verification = await verifyAndCleanup(frame, id);
  await assertVerification(verification);

  await context.close();
});

test('android: menu is stable and application opens top-level without Drive error', async ({ browser }) => {
  const context = await browser.newContext({
    viewport: { width: 360, height: 800 },
    isMobile: true,
    hasTouch: true,
    userAgent: 'Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Mobile Safari/537.36'
  });
  const page = await context.newPage();

  await page.goto(SITE_URL, { waitUntil: 'domcontentloaded' });
  await expect(page.locator('#main-nav')).toBeHidden();
  await expect(page.locator('.menu-toggle')).toBeVisible();

  await page.locator('.menu-toggle').click();
  await expect(page.locator('#main-nav')).toBeVisible();
  for (const link of await page.locator('#main-nav a').all()) await expect(link).toBeVisible();
  const navBox = await page.locator('#main-nav').boundingBox();
  expect(navBox.width).toBeLessThanOrEqual(361);
  await page.locator('.menu-toggle').click();
  await expect(page.locator('#main-nav')).toBeHidden();

  const noHorizontalOverflow = await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1);
  expect(noHorizontalOverflow).toBeTruthy();

  await page.locator('#apply').scrollIntoViewIfNeeded();
  await expect(page.locator('#application-frame')).toHaveCount(0);
  await expect(page.locator('.mobile-apply-card')).toBeVisible();
  await expect(page.getByText('Не удалось открыть файл.')).toHaveCount(0);

  const mobileLink = page.locator('[data-mobile-apply-link]');
  await expect(mobileLink).toBeVisible();
  const href = await mobileLink.getAttribute('href');
  expect(href).toContain('script.google.com/macros/s/');

  await mobileLink.click();
  await page.waitForLoadState('domcontentloaded');

  const frame = await waitForServerReady(page);
  const id = await fillAndSubmit(frame, 'Android');
  const verification = await verifyAndCleanup(frame, id);
  await assertVerification(verification);

  await context.close();
});
