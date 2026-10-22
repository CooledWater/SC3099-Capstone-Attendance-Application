import test from 'node:test';
import assert from 'node:assert/strict';

// Run against the production frontend: node --test new-tests/frontend-api-proxy.test.mjs
const origin = process.env.FRONTEND_PROXY_TEST_URL ?? 'http://localhost:3000';

test('check-in POST reaches authentication without a backend redirect', async () => {
  const response = await fetch(`${origin}/api/v1/checkins`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}',
    redirect: 'manual',
  });
  assert.equal(response.status, 403);
  assert.equal(response.headers.get('location'), null);
  assert.match(response.headers.get('content-type'), /application\/json/);
});

test('same-origin API forwards authentication errors as JSON', async () => {
  const response = await fetch(`${origin}/api/v1/users/me`);
  assert.equal(response.status, 403); // HTTPBearer rejects requests without credentials.
  assert.match(response.headers.get('content-type'), /application\/json/);
  assert.equal(typeof (await response.json()).detail, 'string');
});

test('same-origin login POST reaches backend payload validation', async () => {
  const response = await fetch(`${origin}/api/v1/auth/login`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}',
  });
  assert.equal(response.status, 422);
  const { detail } = await response.json();
  assert.ok(detail.some(error => error.loc.includes('email')));
  assert.ok(detail.some(error => error.loc.includes('password')));
});
