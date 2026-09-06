const test = require('node:test');
const assert = require('node:assert/strict');

const {
  createDataToken,
  validateDataToken,
  isReadOnlyApiRequest,
  normalizeUsername,
  proxyAuthorizationForPrincipal,
} = require('./server.cjs');

test('only the BETMAN Core username receives Data admin access', () => {
  const admin = validateDataToken(createDataToken('  BETMAN '));
  const customer = validateDataToken(createDataToken('punter@example.com'));

  assert.deepEqual(admin, { username: 'betman', isAdmin: true });
  assert.deepEqual(customer, { username: 'punter@example.com', isAdmin: false });
  assert.equal(normalizeUsername(' BeTmAn '), 'betman');
});

test('tampered Data tokens are rejected', () => {
  const token = createDataToken('punter@example.com');
  assert.equal(validateDataToken(`${token}x`), null);
});

test('read-only users can query data but cannot access admin or mutation routes', () => {
  assert.equal(isReadOnlyApiRequest('GET', '/v1/races?limit=20'), true);
  assert.equal(isReadOnlyApiRequest('POST', '/v1/assistant/query'), true);
  assert.equal(isReadOnlyApiRequest('GET', '/v1/admin/tenants'), false);
  assert.equal(isReadOnlyApiRequest('POST', '/v1/admin/tenants'), false);
  assert.equal(isReadOnlyApiRequest('PATCH', '/v1/anything'), false);
  assert.equal(isReadOnlyApiRequest('DELETE', '/v1/anything'), false);
});

test('principals select the narrowest available upstream credential', () => {
  assert.equal(proxyAuthorizationForPrincipal({ isAdmin: false }, 'read-key', 'admin-key'), 'read-key');
  assert.equal(proxyAuthorizationForPrincipal({ isAdmin: false }, '', 'admin-key'), 'admin-key');
  assert.equal(proxyAuthorizationForPrincipal({ isAdmin: true }, 'read-key', 'admin-key'), 'admin-key');
  assert.equal(proxyAuthorizationForPrincipal({ isAdmin: true }, 'read-key', ''), 'read-key');
});
