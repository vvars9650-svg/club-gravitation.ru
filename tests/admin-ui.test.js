const assert = require('node:assert/strict');
const fs = require('node:fs');
const admin = require('../assets/js/admin.js');

assert.equal(admin.STATUSES.length, 9);
assert.deepEqual(admin.OPERATIONAL, ['lifecycle_status', 'owner', 'priority', 'next_action', 'next_contact_at', 'decision', 'internal_comment']);
assert.ok(admin.FIELDS.includes('occupation'));
assert.ok(admin.FIELDS.includes('unacceptable_behavior'));
const source = fs.readFileSync(require.resolve('../assets/js/admin.js'), 'utf8');
assert.match(source, /Загрузка заявок/);
assert.match(source, /Заявок по выбранным условиям нет/);
assert.match(source, /Не удалось загрузить заявки/);

(async () => {
  const calls = [];
  const client = admin.createClient({__V5_ADMIN_API_URL__: 'https://admin.test/'}, async (url, options = {}) => {
    calls.push({url, options});
    return {ok: true, json: async () => ({environment: 'TEST', applications: []})};
  });
  await client.list({q: 'тест', sort: 'submitted_at', order: 'desc'});
  await client.save('PT-1', {owner: 'Влад'});
  assert.match(calls[0].url, /\/admin\/applications\?/);
  assert.equal(calls[1].options.method, 'PATCH');
  assert.equal(calls[1].options.headers['Content-Type'], 'application/json');
  console.log('admin ui contract: ok');
})();
