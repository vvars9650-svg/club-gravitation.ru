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
  const natural = await hero.evaluate(img => ({ w: img.naturalWidth, h: img.naturalHeight, src: img.currentSrc }));
  expect(natural.w).toBeGreaterThanOrEqual(1600);
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

  const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAQAAABFaP0WAAAADElEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=', 'base64');
  await page.locator('#photo').setInputFiles({ name: 'qa-photo.png', mimeType: 'image/png', buffer: png });
  await expect(page.locator('#photo-preview img')).toBeVisible({ timeout: 10000 });
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
