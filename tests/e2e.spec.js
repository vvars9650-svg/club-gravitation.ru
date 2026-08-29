const { test, expect } = require('@playwright/test');

const SITE_URL = 'https://club-gravitation.ru/';
const SITE_ORIGIN = new URL(SITE_URL).origin;
const PNG_1X1 = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9ZQmcAAAAASUVORK5CYII=',
  'base64'
);

test.setTimeout(300000);
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
      if (ready && ready.ok === true && ready.marker === 'E2E-2') return frame;
    } catch (error) {
      lastError = error;
    }
    await page.waitForTimeout(4000);
    await page.reload({ waitUntil: 'domcontentloaded' });
  }
  throw lastError || new Error('Apps Script E2E helper was not deployed in time');
}

async function submitServerTest(frame, payload) {
  return frame.evaluate(data => new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('e2eSubmitApplication timeout')), 45000);
    google.script.run
      .withSuccessHandler(value => { clearTimeout(timer); resolve(value); })
      .withFailureHandler(error => { clearTimeout(timer); reject(new Error(error?.message || String(error))); })
      .e2eSubmitApplication(data);
  }), payload);
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

async function exerciseDesktopWizard(frame) {
  const form = frame.locator('#application-form');
  await expect(form).toBeVisible();
  const name = `E2E CI Desktop ${Date.now()}`;

  await frame.locator('[name="name"]').fill(name);
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

  return {
    name,
    age: '31',
    gender: 'Мужчина',
    city: 'Краснодар',
    phone: '+79991234567',
    email: 'e2e-ci@example.com',
    page_url: 'https://club-gravitation.ru/desktop-e2e',
    user_agent: 'Desktop',
    submitted_at_client: new Date().toISOString()
  };
}

async function fullDataCycle(frame, payload) {
  const saved = await submitServerTest(frame, payload);
  expect(saved).toMatchObject({ ok: true });
  expect(saved.id).toMatch(/^GR-/);

  const verification = await verifyAndCleanup(frame, saved.id);
  expect(verification).toMatchObject({
    ok: true,
    participant: true,
    raw: true,
    photo: true,
    photoLink: true,
    cleaned: true
  });
  return saved.id;
}

async function exerciseRealMobileForm(page) {
  const form = page.locator('#application-v2');
  await expect(form).toBeVisible({ timeout: 20000 });
  const name = `E2E CI Android ${Date.now()}`;

  await page.locator('[name="name"]').fill(name);
  await page.locator('[name="age"]').selectOption('31');
  await page.locator('[name="gender"]').selectOption({ label: 'Мужчина' });
  await page.locator('[name="city"]').selectOption({ label: 'Краснодар' });
  await page.locator('[name="phone"]').fill('+7 999 123-45-67');
  await page.locator('[name="email"]').fill('e2e-ci@example.com');

  await page.locator('#v2-next').click();
  await expect(page.locator('.v2-step[data-step="1"]')).toHaveClass(/is-active/);

  await page.locator('#v2-photo').setInputFiles({
    name: 'e2e-photo.png',
    mimeType: 'image/png',
    buffer: PNG_1X1
  });
  await expect(page.locator('#v2-photo-preview img')).toBeVisible({ timeout: 15000 });
  await expect(page.locator('#v2-photo-name')).toContainText('e2e-photo.png');

  for (const step of [2, 3, 4, 5]) {
    await page.locator('#v2-next').click();
    await expect(page.locator(`.v2-step[data-step="${step}"]`)).toHaveClass(/is-active/);
  }

  await expect(page.locator('#v2-next')).toBeHidden();
  await expect(page.getByText('ДАЛЕЕ', { exact: true })).toHaveCount(0);
  await page.locator('[name="personal_data_consent"]').check();
  await page.locator('[name="rules_consent"]').check();
  await page.locator('#v2-submit').click();

  await expect(page.locator('#v2-success')).toBeVisible({ timeout: 90000 });
  const id = (await page.locator('#v2-success-id').textContent() || '').trim();
  expect(id).toMatch(/^GR-/);
  expect(new URL(page.url()).origin).toBe(SITE_ORIGIN);
  await expect(page.getByText('Не удалось открыть файл.')).toHaveCount(0);

  return { id, name };
}

async function verifyAndCleanupRealSubmission(browser, id) {
  const context = await browser.newContext({ viewport: { width: 1365, height: 900 } });
  const page = await context.newPage();
  await page.goto(SITE_URL, { waitUntil: 'domcontentloaded' });
  await page.locator('#apply').scrollIntoViewIfNeeded();
  const frame = await waitForServerReady(page);
  const verification = await verifyAndCleanup(frame, id);
  await context.close();

  expect(verification).toMatchObject({
    ok: true,
    participant: true,
    raw: true,
    photo: true,
    photoLink: true,
    cleaned: true
  });
}

test('desktop: embedded form UI and real Sheets/Drive cycle', async ({ browser }) => {
  const context = await browser.newContext({ viewport: { width: 1365, height: 900 } });
  const page = await context.newPage();

  await page.goto(SITE_URL, { waitUntil: 'domcontentloaded' });
  await expect(page.locator('#main-nav')).toBeVisible();
  await page.locator('#apply').scrollIntoViewIfNeeded();
  await expect(page.locator('#application-frame')).toBeVisible();

  const frame = await waitForServerReady(page);
  const payload = await exerciseDesktopWizard(frame);
  await fullDataCycle(frame, payload);

  await context.close();
});

test('android: real club-domain form submits photo to Sheets/Drive', async ({ browser }) => {
  const context = await browser.newContext({
    viewport: { width: 360, height: 800 },
    isMobile: true,
    hasTouch: true,
    userAgent: 'Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Mobile Safari/537.36'
  });
  const page = await context.newPage();

  await page.goto(`${SITE_URL}?utm_source=e2e&utm_medium=android`, { waitUntil: 'domcontentloaded' });
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
  const target = new URL(href);
  expect(target.origin).toBe(SITE_ORIGIN);
  expect(target.pathname).toBe('/apply.html');
  expect(target.searchParams.get('utm_source')).toBe('e2e');
  expect(target.searchParams.get('utm_medium')).toBe('android');

  await mobileLink.click();
  await page.waitForURL(url => url.origin === SITE_ORIGIN && url.pathname === '/apply.html', { timeout: 20000 });
  expect(new URL(page.url()).origin).toBe(SITE_ORIGIN);
  await expect(page.locator('#application-v2')).toBeVisible();

  const { id } = await exerciseRealMobileForm(page);
  await context.close();

  await verifyAndCleanupRealSubmission(browser, id);
});
