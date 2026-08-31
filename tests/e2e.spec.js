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

async function inspectHero(page) {
  const hero = page.locator('.home-hero__image');
  await expect(hero).toBeVisible();
  await hero.evaluate(img => img.decode ? img.decode() : Promise.resolve());
  return hero.evaluate(img => {
    const style = getComputedStyle(img);
    const rect = img.getBoundingClientRect();
    const canvas = document.createElement('canvas');
    canvas.width = 80;
    canvas.height = 80;
    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    ctx.drawImage(img, 0, 0, 80, 80);
    const data = ctx.getImageData(0, 0, 80, 80).data;
    let min = 255, max = 0, sum = 0, sumSq = 0, n = 0;
    for (let i = 0; i < data.length; i += 4) {
      const y = .2126 * data[i] + .7152 * data[i + 1] + .0722 * data[i + 2];
      min = Math.min(min, y);
      max = Math.max(max, y);
      sum += y;
      sumSq += y * y;
      n++;
    }
    const mean = sum / n;
    return {
      w: img.naturalWidth,
      h: img.naturalHeight,
      src: img.currentSrc,
      opacity: +style.opacity,
      rectW: rect.width,
      rectH: rect.height,
      range: max - min,
      variance: sumSq / n - mean * mean
    };
  });
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

const heroCases = [
  { label: 'desktop', width: 1600, height: 900, asset: 'hero-desktop.png', portrait: false },
  { label: 'tablet landscape', width: 1024, height: 768, asset: 'hero-tablet-landscape.webp', portrait: false },
  { label: 'tablet portrait', width: 900, height: 1200, asset: 'hero-tablet-portrait.webp', portrait: true },
  { label: 'mobile portrait', width: 390, height: 844, asset: 'hero-mobile.webp', portrait: true }
];

for (const item of heroCases) {
  test(`homepage uses dedicated ${item.label} artwork`, async ({ page }) => {
    await page.setViewportSize({ width: item.width, height: item.height });
    await open(page, '/');
    const result = await inspectHero(page);
    expect(result.src).toContain(item.asset);
    expect(result.opacity).toBe(1);
    expect(result.w).toBeGreaterThan(800);
    expect(result.h).toBeGreaterThan(700);
    if (item.portrait) expect(result.h).toBeGreaterThan(result.w);
    else expect(result.w).toBeGreaterThan(result.h);
    expect(result.rectW).toBeGreaterThanOrEqual(item.width - 2);
    expect(result.rectH).toBeGreaterThanOrEqual(item.height - 2);
    expect(result.range).toBeGreaterThan(70);
    expect(result.variance).toBeGreaterThan(180);
    await expectNoHorizontalOverflow(page, item.label);
  });
}

test('homepage picture exposes all responsive hero sources', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await open(page, '/');
  const sources = await page.locator('.home-hero__picture source').evaluateAll(nodes => nodes.map(n => ({ media: n.media, srcset: n.srcset })));
  expect(sources).toHaveLength(3);
  expect(sources.some(s => s.srcset.includes('hero-mobile.webp'))).toBeTruthy();
  expect(sources.some(s => s.srcset.includes('hero-tablet-portrait.webp'))).toBeTruthy();
  expect(sources.some(s => s.srcset.includes('hero-tablet-landscape.webp'))).toBeTruthy();
  await expect(page.locator('.home-hero__image')).toHaveAttribute('src', /hero-desktop\.png$/);
});

test('tablet and mobile hero copy follows approved responsive zones', async ({ page }) => {
  const cases = [
    { label: 'tablet landscape', width: 1024, height: 768, portrait: false },
    { label: 'tablet portrait', width: 900, height: 1200, portrait: true },
    { label: 'mobile portrait', width: 390, height: 844, portrait: true }
  ];

  for (const item of cases) {
    await page.setViewportSize({ width: item.width, height: item.height });
    await open(page, '/');
    const kickerDisplay = await page.locator('.hero-kicker').evaluate(el => getComputedStyle(el).display);
    expect(kickerDisplay, `${item.label}: kicker should be removed`).toBe('none');
    const title = await page.locator('.hero-title-block').boundingBox();
    const body = await page.locator('.hero-body-block').boundingBox();
    const actions = await page.locator('.hero-actions').boundingBox();
    expect(title).toBeTruthy(); expect(body).toBeTruthy(); expect(actions).toBeTruthy();
    expect(title.y, `${item.label}: title should stay high`).toBeLessThan(item.height * .36);
    expect(actions.y + actions.height, `${item.label}: actions should fit hero`).toBeLessThanOrEqual(item.height + 2);
    if (item.portrait) {
      expect(title.width, `${item.label}: title wider than body`).toBeGreaterThan(body.width);
      expect(body.y, `${item.label}: body below title`).toBeGreaterThan(title.y);
      expect(actions.y, `${item.label}: actions below body`).toBeGreaterThan(body.y);
      const rightDelta = Math.abs((title.x + title.width) - (body.x + body.width));
      expect(rightDelta, `${item.label}: right edges align`).toBeLessThan(4);
      const color = await page.locator('.hero-intro').evaluate(el => getComputedStyle(el).color);
      const rgb = color.match(/\d+/g).slice(0, 3).map(Number);
      const luminance = .2126 * rgb[0] + .7152 * rgb[1] + .0722 * rgb[2];
      expect(luminance, `${item.label}: copy should be dark`).toBeLessThan(120);
    } else {
      expect(body.y, `${item.label}: copy lifted with title`).toBeLessThan(item.height * .58);
    }
    await expectNoHorizontalOverflow(page, `${item.label} approved copy zones`);
  }
});

test('about cards follow approved hierarchy', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await open(page, '/about/');
  const markers = page.locator('.principle-grid article > span');
  expect(await markers.count()).toBe(3);
  for (let i = 0; i < 3; i++) expect(await markers.nth(i).evaluate(el => getComputedStyle(el).display)).toBe('none');
  const principleHeadings = page.locator('.principle-grid h3');
  const alignments = await principleHeadings.evaluateAll(nodes => nodes.map(n => ({ align:getComputedStyle(n).textAlign, size:parseFloat(getComputedStyle(n).fontSize), y:n.getBoundingClientRect().y })));
  alignments.forEach(x => { expect(x.align).toBe('center'); expect(x.size).toBeGreaterThan(20); });
  expect(Math.max(...alignments.map(x=>x.y)) - Math.min(...alignments.map(x=>x.y))).toBeLessThan(3);
  const icons = page.locator('.outcome-grid i');
  const iconStyles = await icons.evaluateAll(nodes => nodes.map(n => ({ size:parseFloat(getComputedStyle(n).fontSize), align:getComputedStyle(n).textAlign })));
  iconStyles.forEach(x => { expect(x.size).toBeGreaterThan(50); expect(x.align).toBe('center'); });
});

test('founders highlighted phrase has readable darker gold', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await open(page, '/founders/');
  const color = await page.locator('.founders-hero h1 em').evaluate(el => getComputedStyle(el).color);
  const rgb = color.match(/\d+/g).slice(0,3).map(Number);
  const luminance = .2126*rgb[0]+.7152*rgb[1]+.0722*rgb[2];
  expect(luminance).toBeLessThan(165);
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
  await page.setViewportSize({ width: 1440, height: 900 }); await open(page, '/about/');
  const firstLink = page.locator('.footer-links a').first(); const top = page.locator('.back-to-top');
  await expect(page.locator('.footer-links a[href="/founders/"]')).toBeVisible(); await expect(top).toBeVisible();
  const a = await firstLink.boundingBox(); const b = await top.boundingBox();
  expect(Math.abs((a.y+a.height/2)-(b.y+b.height/2))).toBeLessThan(18);
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight)); await top.click(); await page.waitForTimeout(900);
  expect(await page.evaluate(() => window.scrollY)).toBeLessThan(100);
});

test('mobile footer uses wide back-to-top above oval navigation', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 }); await open(page, '/about/');
  const top = page.locator('.back-to-top'); const links = page.locator('.footer-links'); await expect(top).toBeVisible();
  const topBox = await top.boundingBox(); const linksBox = await links.boundingBox();
  expect(topBox.width).toBeGreaterThan(340); expect(topBox.height).toBeLessThanOrEqual(50); expect(topBox.y).toBeLessThan(linksBox.y);
  const label = await top.evaluate(el => getComputedStyle(el, '::before').content); expect(label).toContain('Наверх');
});

test('privacy logo is transparent artwork centered above responsive heading', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 }); await open(page, '/privacy/');
  const logo = page.locator('.legal-brand-art img'); await expect(logo).toBeVisible();
  const logoBox = await logo.boundingBox(); const heading = page.locator('.legal h1'); const box = await heading.boundingBox();
  const natural = await logo.evaluate(img => ({ w: img.naturalWidth, h: img.naturalHeight, src: img.currentSrc }));
  expect(natural.w).toBe(396); expect(natural.h).toBe(218); expect(natural.src).toContain('privacy-logo-transparent.png');
  expect(Math.abs((logoBox.x + logoBox.width / 2) - 180)).toBeLessThan(4); expect(logoBox.y + logoBox.height).toBeLessThan(box.y);
  expect(box.x).toBeGreaterThanOrEqual(0); expect(box.x + box.width).toBeLessThanOrEqual(360);
  await expectNoHorizontalOverflow(page, 'mobile privacy 360');
});

test('mobile menu still exposes all main routes', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 }); await open(page, '/');
  const toggle = page.locator('.menu-toggle'); await expect(toggle).toBeVisible(); await toggle.click();
  await expect(page.locator('.site-nav')).toHaveClass(/is-open/);
  await expect(page.locator('.site-nav a[href="/about/"]')).toBeVisible();
  await expect(page.locator('.site-nav a[href="/events/"]')).toBeVisible();
  await expect(page.locator('.site-nav a[href="/founders/"]')).toBeVisible();
  await expect(page.locator('.site-nav a[href="/apply/"]')).toBeVisible();
});
