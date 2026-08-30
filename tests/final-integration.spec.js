const { test, expect } = require('@playwright/test');

const BASE = (process.env.BASE_URL || 'https://club-gravitation.ru').replace(/\/$/, '');
const QA_ID = 'GR-260830-232301-77';
const PHOTO = Buffer.from('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', 'base64');

test('FINAL: real application reaches Apps Script', async ({ page }) => {
  test.setTimeout(90000);
  await page.setViewportSize({ width: 1440, height: 1000 });
  const response = await page.goto(`${BASE}/apply/?utm_source=qa-final&utm_medium=automation&utm_campaign=v2-final`, { waitUntil: 'networkidle', timeout: 45000 });
  expect(response).toBeTruthy();
  expect(response.status()).toBeLessThan(400);

  await page.evaluate(id => sessionStorage.setItem('gravitation_pending_application_id', id), QA_ID);

  await page.locator('input[name="name"]').fill('QA FINAL V2');
  await page.locator('select[name="age"]').selectOption('35');
  await page.locator('select[name="gender"]').selectOption({ label: 'Мужчина' });
  await page.locator('select[name="city"]').selectOption({ label: 'Краснодар' });
  await page.locator('input[name="phone"]').fill('9990000001');
  await page.locator('input[name="telegram"]').fill('@qa_final_v2');
  await page.locator('input[name="email"]').fill('qa-final-v2@example.com');
  await page.locator('select[name="preferred_contact"]').selectOption({ label: 'Telegram' });
  await page.locator('#form-next').click();
  await expect(page.locator('.form-step[data-step="1"]')).toHaveClass(/is-active/);

  await page.locator('#photo').setInputFiles({ name: 'qa-final-v2.png', mimeType: 'image/png', buffer: PHOTO });
  await expect(page.locator('#photo-preview img')).toBeVisible({ timeout: 10000 });
  await page.waitForTimeout(1200);
  await expect(page.locator('#photo-error')).toHaveText('');
  await page.locator('#form-next').click();
  await expect(page.locator('.form-step[data-step="2"]')).toHaveClass(/is-active/);

  await page.locator('textarea[name="occupation"]').fill('Финальный автоматический QA V2');
  await page.locator('textarea[name="life_beyond_work"]').fill('Проверка полной цепочки сайта');
  await page.locator('textarea[name="interests"]').fill('Качество продукта и живые встречи');
  await page.locator('textarea[name="interest_reason"]').fill('Финальная интеграционная проверка перед приёмкой');
  await page.locator('textarea[name="expectations"]').fill('Подтвердить корректную запись в базу участников');
  await page.locator('#form-next').click();
  await expect(page.locator('.form-step[data-step="3"]')).toHaveClass(/is-active/);

  await page.locator('select[name="relationship_context"]').selectOption({ label: 'Предпочитаю обсудить лично' });
  await page.locator('input[name="connection_goal"][value="Близкие по духу люди"]').check();
  await page.locator('textarea[name="values_people"]').fill('Уважение, искренность, ответственность');
  await page.locator('textarea[name="meeting_barriers"]').fill('Нет, это QA-запись');
  await page.locator('select[name="social_comfort"]').selectOption({ label: '3 — нормально' });
  await page.locator('select[name="initiative"]').selectOption({ label: '3 — зависит от ситуации' });
  await page.locator('select[name="introduction_scenario"]').selectOption({ label: 'Через общее дело или занятие' });
  await page.locator('#form-next').click();
  await expect(page.locator('.form-step[data-step="4"]')).toHaveClass(/is-active/);

  await page.locator('textarea[name="successful_evening"]').fill('Люди общаются естественно и хотят продолжить общение');
  await page.locator('textarea[name="return_reason"]').fill('Качественная атмосфера и интересные люди');
  await page.locator('textarea[name="unacceptable_behavior"]').fill('Неуважение к личным границам');
  await page.locator('input[name="convenient_days"][value="Суббота"]').check();
  await page.locator('select[name="comfortable_price"]').selectOption({ label: '3 500–5 000 ₽' });
  await page.locator('select[name="source"]').selectOption({ label: 'Сайт / поиск' });
  await page.locator('#form-next').click();
  await expect(page.locator('.form-step[data-step="5"]')).toHaveClass(/is-active/);
  await expect(page.locator('.review-card')).toHaveCount(5);

  await page.locator('input[name="personal_data_consent"]').check();
  await page.locator('input[name="rules_consent"]').check();
  await page.locator('#form-submit').click();
  await expect(page.locator('#form-success')).toBeVisible({ timeout: 60000 });
  await expect(page.locator('#success-id')).toHaveText(QA_ID);
  console.log(`FINAL_QA_ID=${QA_ID}`);
  await page.waitForTimeout(3000);
});
