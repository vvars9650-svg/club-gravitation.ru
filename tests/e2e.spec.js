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

test('homepage approved artwork is actually visible and contains image detail', async ({ page }) => {
  await page.setViewportSize({ width: 1600, height: 900 });
  await open(page, '/');
  const hero = page.locator('.home-hero__image');
  await expect(hero).toBeVisible();
  await hero.evaluate(img => img.decode ? img.decode() : Promise.resolve());
  const result = await hero.evaluate(img => {
    const style = getComputedStyle(img);
    const rect = img.getBoundingClientRect();
    const canvas = document.createElement('canvas');
    canvas.width = 80; canvas.height = 45;
    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    ctx.drawImage(img, 0, 0, 80, 45);
    const data = ctx.getImageData(0, 0, 80, 45).data;
    let min = 255, max = 0, sum = 0, sumSq = 0, n = 0;
    for (let i = 0; i < data.length; i += 4) {
      const y = .2126 * data[i] + .7152 * data[i + 1] + .0722 * data[i + 2];
      min = Math.min(min, y); max = Math.max(max, y); sum += y; sumSq += y * y; n++;
    }
    const mean = sum / n;
    const variance = sumSq / n - mean * mean;
    return { w: img.naturalWidth, h: img.naturalHeight, src: img.currentSrc, opacity: +style.opacity, rectW: rect.width, rectH: rect.height, range: max - min, variance };
  });
  expect(result.w).toBe(1672);
  expect(result.h).toBe(941);
  expect(result.src).toContain('glavnaya-approved.webp');
  expect(result.opacity).toBe(1);
  expect(result.rectW).toBeGreaterThan(1200);
  expect(result.rectH).toBeGreaterThan(700);
  expect(result.range).toBeGreaterThan(80);
  expect(result.variance).toBeGreaterThan(250);
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

test('desktop footer puts back-to-top on navigation row and it works', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await open(page, '/about/');
  const firstLink = page.locator('.footer-links a').first();
  const top = page.locator('.back-to-top');
  await expect(page.locator('.footer-links a[href="/founders/"]')).toBeVisible();
  await expect(top).toBeVisible();
  const a = await firstLink.boundingBox();
  const b = await top.boundingBox();
  expect(Math.abs((a.y + a.height / 2) - (b.y + b.height / 2))).toBeLessThan(18);
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await top.click();
  await page.waitForTimeout(900);
  expect(await page.evaluate(() => window.scrollY)).toBeLessThan(100);
});

test('mobile footer uses wide back-to-top above oval navigation', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await open(page, '/about/');
  const top = page.locator('.back-to-top');
  const links = page.locator('.footer-links');
  await expect(top).toBeVisible();
  const topBox = await top.boundingBox();
  const linksBox = await links.boundingBox();
  expect(topBox.width).toBeGreaterThan(340);
  expect(topBox.height).toBeLessThanOrEqual(50);
  expect(topBox.y).toBeLessThan(linksBox.y);
  const label = await top.evaluate(el => getComputedStyle(el, '::before').content);
  expect(label).toContain('Наверх');
});

test('privacy logo is transparent artwork centered above responsive heading', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await open(page, '/privacy/');
  const logo = page.locator('.legal-brand-art img');
  await expect(logo).toBeVisible();
  const logoBox = await logo.boundingBox();
  const heading = page.locator('.legal h1');
  const box = await heading.boundingBox();
  const natural = await logo.evaluate(img => ({ w: img.naturalWidth, h: img.naturalHeight, src: img.currentSrc }));
  expect(natural.w).toBe(396);
  expect(natural.h).toBe(218);
  expect(natural.src).toContain('privacy-logo-transparent.png');
  expect(Math.abs((logoBox.x + logoBox.width / 2) - 180)).toBeLessThan(4);
  expect(logoBox.y + logoBox.height).toBeLessThan(box.y);
  expect(box.x).toBeGreaterThanOrEqual(0);
  expect(box.x + box.width).toBeLessThanOrEqual(360);
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
