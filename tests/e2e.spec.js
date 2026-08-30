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
  test(`desktop visual ${path}`, async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await open(page, path);
    await expect(page.locator('body')).toContainText(text);
    await expectNoHorizontalOverflow(page, `desktop ${path}`);
  });

  test(`mobile visual ${path}`, async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await open(page, path);
    await expect(page.locator('body')).toContainText(text);
    await expectNoHorizontalOverflow(page, `mobile ${path}`);
  });
}

test('homepage uses approved sharp artwork', async ({ page }) => {
  await page.setViewportSize({ width: 1600, height: 900 });
  await open(page, '/');
  const hero = page.locator('.home-hero__image');
  await expect(hero).toBeVisible();
  const natural = await hero.evaluate(img => ({ w: img.naturalWidth, h: img.naturalHeight, src: img.currentSrc }));
  expect(natural.w).toBe(1672);
  expect(natural.h).toBe(941);
  expect(natural.src).toContain('glavnaya.webp');
});

test('desktop navigation buttons have outlines and CTA has gold fill', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await open(page, '/about/');
  const ordinary = page.locator('.site-nav a[href="/events/"]');
  const cta = page.locator('.site-nav__cta');
  const ordinaryStyle = await ordinary.evaluate(el => getComputedStyle(el));
  const ctaStyle = await cta.evaluate(el => getComputedStyle(el));
  expect(parseFloat(ordinaryStyle.borderTopWidth)).toBeGreaterThan(0);
  expect(ordinaryStyle.borderTopStyle).toBe('solid');
  expect(parseFloat(ctaStyle.borderTopWidth)).toBeGreaterThan(0);
  expect(ctaStyle.backgroundImage).not.toBe('none');
});

test('footer navigation is prominent and back-to-top works', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await open(page, '/about/');
  await expect(page.locator('.footer-links a[href="/founders/"]')).toBeVisible();
  await expect(page.locator('.back-to-top')).toBeVisible();
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await page.locator('.back-to-top').click();
  await page.waitForTimeout(900);
  const y = await page.evaluate(() => window.scrollY);
  expect(y).toBeLessThan(100);
});

test('mobile privacy heading stays inside viewport', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await open(page, '/privacy/');
  const box = await page.locator('.legal h1').boundingBox();
  expect(box).toBeTruthy();
  expect(box.x).toBeGreaterThanOrEqual(0);
  expect(box.x + box.width).toBeLessThanOrEqual(360);
  await expect(page.locator('.legal-brand-lockup')).toBeVisible();
  await expectNoHorizontalOverflow(page, 'mobile privacy 360');
});

test('mobile menu still exposes all main routes', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await open(page, '/');
  const toggle = page.locator('.menu-toggle');
  await expect(toggle).toBeVisible();
  await toggle.click();
  await expect(page.locator('.site-nav')).toHaveClass(/is-open/);
  await expect(page.locator('.site-nav a[href="/about/"]')).toBeVisible();
  await expect(page.locator('.site-nav a[href="/events/"]')).toBeVisible();
  await expect(page.locator('.site-nav a[href="/founders/"]')).toBeVisible();
  await expect(page.locator('.site-nav a[href="/apply/"]')).toBeVisible();
});
