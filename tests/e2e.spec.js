const { test, expect } = require('@playwright/test');

const SITE_URL = 'https://club-gravitation.ru/';
const SITE_ORIGIN = new URL(SITE_URL).origin;
const PNG_1X1 = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9ZQmcAAAAASUVORK5CYII=',
  'base64'
);

test.setTimeout(180000);
test.describe.configure({ mode: 'serial' });

test('desktop: landing and embedded application remain available', async ({ browser }) => {
  const context = await browser.newContext({ viewport: { width: 1365, height: 900 } });
  const page = await context.newPage();
  await page.goto(SITE_URL, { waitUntil: 'domcontentloaded' });
  await expect(page.locator('#main-nav')).toBeVisible();
  await page.locator('#apply').scrollIntoViewIfNeeded();
  await expect(page.locator('#application-frame')).toBeVisible();
  await expect(page.getByText('Не удалось открыть файл.')).toHaveCount(0);
  await context.close();
});

test('mobile web: full real application cycle leaves final record for manual review', async ({ browser }) => {
  const context = await browser.newContext({
    viewport: { width: 360, height: 800 },
    isMobile: true,
    hasTouch: true,
    userAgent: 'Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Mobile Safari/537.36'
  });
  const page = await context.newPage();
  const stamp = Date.now();
  const name = `ФИНАЛЬНАЯ ПРОВЕРКА WEB 30.08.2026 ${stamp}`;

  await page.goto(`${SITE_URL}?utm_source=final-e2e&utm_medium=android&utm_campaign=final-web-check`, { waitUntil: 'domcontentloaded' });
  await expect(page.locator('#main-nav')).toBeHidden();
  await expect(page.locator('.menu-toggle')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBeTruthy();

  await page.locator('#apply').scrollIntoViewIfNeeded();
  await expect(page.locator('.mobile-apply-card')).toBeVisible();
  const mobileLink = page.locator('[data-mobile-apply-link]');
  await expect(mobileLink).toBeVisible();
  const href = await mobileLink.getAttribute('href');
  const target = new URL(href);
  expect(target.origin).toBe(SITE_ORIGIN);
  expect(target.pathname).toBe('/apply.html');

  await mobileLink.click();
  await page.waitForURL(url => url.origin === SITE_ORIGIN && url.pathname === '/apply.html', { timeout: 20000 });
  await expect(page.locator('#application-v2')).toBeVisible();

  // 1. Контакты
  await page.locator('[name="name"]').fill(name);
  await page.locator('[name="age"]').selectOption('31');
  await page.locator('[name="gender"]').selectOption({ label: 'Мужчина' });
  await page.locator('[name="city"]').selectOption({ label: 'Краснодар' });
  await page.locator('[name="phone"]').fill('+7 999 123-45-67');
  await page.locator('[name="telegram"]').fill('@gravitation_final_test');
  await page.locator('[name="email"]').fill('final-web-test@example.com');
  await page.locator('[name="preferred_contact"]').selectOption({ label: 'Telegram' });
  await page.locator('#v2-next').click();
  await expect(page.locator('.v2-step[data-step="1"]')).toHaveClass(/is-active/);

  // 2. Фото
  await page.locator('#v2-photo').setInputFiles({
    name: 'final-web-test.png',
    mimeType: 'image/png',
    buffer: PNG_1X1
  });
  await expect(page.locator('#v2-photo-preview img')).toBeVisible({ timeout: 15000 });
  await expect(page.locator('#v2-photo-name')).toContainText('final-web-test.png');
  await page.locator('#v2-next').click();

  // 3. О вас
  await page.locator('[name="occupation"]').fill('Финальный автоматический тест сайта Гравитация');
  await page.locator('[name="life_beyond_work"]').fill('Живое общение, путешествия и проверка работающих веб-форм.');
  await page.locator('[name="interests"]').fill('Люди, новые впечатления, музыка и качественные сообщества.');
  await page.locator('[name="interest_reason"]').fill('Хочу убедиться, что анкета действительно работает от начала до конца.');
  await page.locator('[name="expectations"]').fill('Получить корректную запись в базе, фото и номер участника без красной ошибки.');
  await page.locator('#v2-next').click();

  // 4. Знакомства
  await page.locator('[name="relationship_context"]').selectOption({ label: 'Свободен / свободна' });
  await page.locator('[name="connection_goal"][value="Новые друзья"]').check();
  await page.locator('[name="connection_goal"][value="Близкие по духу люди"]').check();
  await page.locator('[name="values_people"]').fill('Честность, уважение, живость и чувство юмора.');
  await page.locator('[name="meeting_barriers"]').fill('Нехватка естественного контекста для знакомства.');
  await page.locator('[name="social_comfort"]').selectOption({ label: '4' });
  await page.locator('[name="initiative"]').selectOption({ label: '4' });
  await page.locator('[name="introduction_scenario"]').selectOption({ label: 'Через живой разговор' });
  await page.locator('#v2-next').click();

  // 5. Формат встреч
  await page.locator('[name="successful_evening"]').fill('Хорошая атмосфера, несколько настоящих разговоров и желание не смотреть на часы.');
  await page.locator('[name="return_reason"]').fill('Если после встречи останется ощущение живого контакта и интереса к людям.');
  await page.locator('[name="unacceptable_behavior"]').fill('Давление, грубость, нарушение границ и навязчивость.');
  await page.locator('[name="convenient_days"][value="Суббота"]').check();
  await page.locator('[name="convenient_days"][value="Зависит от мероприятия"]').check();
  await page.locator('[name="comfortable_price"]').selectOption({ label: '2 500–3 500 ₽' });
  await page.locator('[name="source"]').selectOption({ label: 'Сайт / поиск' });
  await page.locator('#v2-next').click();

  // 6. Проверка
  await expect(page.locator('.v2-step[data-step="5"]')).toHaveClass(/is-active/);
  await expect(page.locator('#v2-next')).toBeHidden();
  await expect(page.locator('#v2-review')).toContainText(name);
  await expect(page.locator('#v2-review')).toContainText('Финальный автоматический тест сайта Гравитация');
  await expect(page.locator('#v2-review')).toContainText('Суббота');
  await page.locator('[name="personal_data_consent"]').check();
  await page.locator('[name="rules_consent"]').check();

  await page.locator('#v2-submit').click();
  await expect(page.locator('#v2-submit')).toHaveText('ОТПРАВЛЯЕМ…');
  await expect(page.locator('#v2-success')).toBeVisible({ timeout: 60000 });
  await expect(page.getByText('Сервер не подтвердил завершение отправки.')).toHaveCount(0);
  await expect(page.getByText('Не удалось открыть файл.')).toHaveCount(0);

  const id = (await page.locator('#v2-success-id').textContent() || '').trim();
  expect(id).toMatch(/^GR-\d{6}-\d{6}-\d{2}$/);
  expect(new URL(page.url()).origin).toBe(SITE_ORIGIN);
  expect(new URL(page.url()).pathname).toBe('/apply.html');

  console.log(`FINAL_APPLICATION_ID=${id}`);
  console.log(`FINAL_APPLICATION_NAME=${name}`);

  await context.close();
});