const { test, expect } = require('@playwright/test');

const BASE = (process.env.BASE_URL || 'https://club-gravitation.ru').replace(/\/$/, '');

async function open(page, path) {
  const response = await page.goto(`${BASE}${path}`, { waitUntil: 'domcontentloaded', timeout: 45000 });
  expect(response, `No response for ${path}`).toBeTruthy();
  expect(response.status(), `HTTP status for ${path}`).toBeLessThan(400);
  await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {});
}

async function expectNoHorizontalOverflow(page, label) {
  const metrics = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
    bodyWidth: document.body.scrollWidth
  }));
  expect(metrics.scrollWidth, `${label}: document overflow`).toBeLessThanOrEqual(metrics.clientWidth + 1);
  expect(metrics.bodyWidth, `${label}: body overflow`).toBeLessThanOrEqual(metrics.clientWidth + 1);
}

const pages = [
  ['/', /ЗДЕСЬ ЧЕЛОВЕК/],
  ['/about/', /НЕ ИСКАТЬ ЧЕЛОВЕКА/],
  ['/events/', /ПЕРВЫЕ ВСТРЕЧИ/],
  ['/founders/', /ЗА ГРАВИТАЦИЕЙ/],
  ['/apply/', /ПОДАТЬ/],
  ['/privacy/', /Политика конфиденциальности/]
];

for (const [path, text] of pages) {
  test(`desktop renders ${path}`, async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await open(page, path);
    await expect(page.locator('body')).toContainText(text);
    await expectNoHorizontalOverflow(page, `desktop ${path}`);
  });

  test(`mobile renders ${path}`, async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await open(page, path);
    await expect(page.locator('body')).toContainText(text);
    await expectNoHorizontalOverflow(page, `mobile ${path}`);
  });
}

test('desktop hero uses high-resolution artwork and favicon', async ({ page }) => {
  await page.setViewportSize({ width: 1600, height: 900 });
  await open(page, '/');
  const hero = page.locator('.home-hero__image');
  await expect(hero).toBeVisible();
  await expect.poll(async () => hero.evaluate(img => img.complete ? img.naturalWidth : 0), { timeout: 15000 }).toBeGreaterThanOrEqual(1600);
  const natural = await hero.evaluate(img => ({ w: img.naturalWidth, h: img.naturalHeight, src: img.currentSrc }));
  expect(natural.h).toBeGreaterThanOrEqual(900);
  expect(natural.src).toContain('hero-1672.webp');
  await expect(page.locator('link[rel="icon"]')).toHaveAttribute('href', '/favicon.svg');
});

test('mobile menu opens and exposes all routes', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await open(page, '/');
  const toggle = page.locator('.menu-toggle');
  await expect(toggle).toBeVisible();
  await toggle.click();
  await expect(toggle).toHaveAttribute('aria-expanded', 'true');
  await expect(page.locator('.site-nav')).toHaveClass(/is-open/);
  await expect(page.locator('.site-nav a[href="/about/"]')).toBeVisible();
  await expect(page.locator('.site-nav a[href="/events/"]')).toBeVisible();
  await expect(page.locator('.site-nav a[href="/founders/"]')).toBeVisible();
  await expect(page.locator('.site-nav a[href="/apply/"]')).toBeVisible();
});

test('application validation, photo processing and review work without backend submission', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await open(page, '/apply/');

  await page.locator('#form-next').click();
  await expect(page.locator('input[name="name"]')).toHaveClass(/is-invalid/);

  await page.locator('input[name="name"]').fill('QA Проверка Интерфейса');
  await page.locator('select[name="age"]').selectOption('35');
  await page.locator('select[name="gender"]').selectOption({ label: 'Мужчина' });
  await page.locator('select[name="city"]').selectOption({ label: 'Краснодар' });
  await page.locator('input[name="phone"]').fill('9991234567');
  await expect(page.locator('input[name="phone"]')).toHaveValue('+7 999 123-45-67');

  await page.locator('input[name="email"]').fill('bad@');
  await page.locator('#form-next').click();
  await expect(page.locator('input[name="email"]')).toHaveClass(/is-invalid/);
  await page.locator('input[name="email"]').fill('qa-interface@example.com');
  await page.locator('#form-next').click();
  await expect(page.locator('.form-step[data-step="1"]')).toHaveClass(/is-active/);

  const png = Buffer.from('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', 'base64');
  await page.locator('#photo').setInputFiles({ name: 'qa-photo.png', mimeType: 'image/png', buffer: png });
  await expect(page.locator('#photo-preview img')).toBeVisible({ timeout: 10000 });
  await page.waitForTimeout(1200);
  await expect(page.locator('#photo-error')).toHaveText('');
  await page.locator('#form-next').click();
  await expect(page.locator('.form-step[data-step="2"]')).toHaveClass(/is-active/);

  await page.locator('#form-next').click();
  await expect(page.locator('.form-step[data-step="3"]')).toHaveClass(/is-active/);
  await page.locator('#form-next').click();
  await expect(page.locator('.form-step[data-step="4"]')).toHaveClass(/is-active/);
  await page.locator('#form-next').click();
  await expect(page.locator('.form-step[data-step="5"]')).toHaveClass(/is-active/);
  await expect(page.locator('.review-card')).toHaveCount(5);

  await page.locator('#form-submit').click();
  await expect(page.locator('#form-status')).toContainText('Подтвердите оба согласия');
});

test('application mobile layout stays inside viewport', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await open(page, '/apply/');
  await expect(page.locator('.mobile-step')).toBeVisible();
  await expect(page.locator('.form-tabs')).toBeHidden();
  await expectNoHorizontalOverflow(page, 'mobile apply 360');
});
