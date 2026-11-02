// Browser-only fixtures: no real account is scheduled for deletion or renewed.
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
const require = createRequire(`${process.env.PWA_TEST_DEPENDENCIES ?? '/private/tmp/saiv-pwa-tests'}/package.json`);
const { chromium } = require('playwright-core');
const browser = await chromium.launch({ executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless: true });
try {
  const context = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true });
  let device, scheduled = null, rotations = 0;
  await context.route('**/api/v1/**', async route => {
    const request = route.request(); const url = new URL(request.url()); const path = url.pathname;
    let body = {}, code = 200;
    if (path.endsWith('/auth/refresh')) body = { access_token: 'settings-fixture-token' };
    else if (path.endsWith('/users/me')) body = { id: 'settings-student', full_name: 'Settings Student', email: 'test@example.com', role: 'student', camera_consent: true, geolocation_consent: true };
    else if (path.endsWith('/push/config')) body = { enabled: false, public_key: null };
    else if (path.endsWith('/sessions/active') || path.endsWith('/sessions/my-sessions') || path.endsWith('/checkins/my-checkins')) body = [];
    else if (path.endsWith('/devices/my-devices')) body = device ? [device] : [];
    else if (path.endsWith('/devices/registration-challenges')) body = { challenge_id: 'registration-fixture', challenge: 'register-settings-browser' };
    else if (path.endsWith('/devices/register')) body = device = { ...request.postDataJSON(), id: 'settings-device', is_active: true, is_trusted: true, browser_identity_verified: true, last_seen_at: new Date().toISOString(), total_checkins: 0, public_key_expires_at: new Date(Date.now() + 90 * 86400000).toISOString() };
    else if (path.endsWith('/devices/key-rotation/challenges')) body = { challenge_id: 'rotation-fixture', challenge: 'renew-settings-browser' };
    else if (path.endsWith('/devices/key-rotation/complete')) { rotations++; body = { rotated: true }; }
    else if (path.endsWith('/users/me/deletion-request')) {
      if (request.method() !== 'GET' && request.postDataJSON().password !== 'testpass123') { code = 403; body = { detail: 'Your password is incorrect' }; }
      else {
        if (request.method() === 'POST') scheduled = new Date(Date.now() + 30 * 86400000).toISOString();
        if (request.method() === 'DELETE') scheduled = null;
        body = { scheduled_deletion_at: scheduled };
      }
    }
    await route.fulfill({ status: code, contentType: 'application/json', body: JSON.stringify(body) });
  });
  const page = await context.newPage(); const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('http://127.0.0.1:3000/attendance');
  await page.getByRole('button', { name: 'Profile', exact: true }).click();
  await page.getByRole('button', { name: /Settings/ }).click();
  await page.getByRole('button', { name: /Delete my data/ }).click();
  await page.getByText(/No data deletion is scheduled/).waitFor();
  const password = page.getByLabel('Confirm your current password');
  await password.fill('wrong');
  await page.getByRole('button', { name: 'Request data deletion in 30 days', exact: true }).click();
  await page.getByRole('alert').getByText('Your password is incorrect').waitFor();
  assert.equal(scheduled, null);
  await password.fill('testpass123');
  await page.getByRole('button', { name: 'Request data deletion in 30 days', exact: true }).click();
  await page.getByText(/Deletion scheduled for/).waitFor();
  assert.ok(scheduled);
  assert.equal(await password.inputValue(), '');
  await password.fill('testpass123');
  await page.getByRole('button', { name: 'Cancel deletion request', exact: true }).click();
  await page.getByText(/No data deletion is scheduled/).waitFor();
  assert.equal(scheduled, null);
  await page.screenshot({ path: '/private/tmp/saiv-delete-settings-mobile.png', fullPage: true });
  await page.getByRole('button', { name: 'Back to settings', exact: true }).click();
  await page.getByRole('button', { name: 'Back to profile', exact: true }).click();
  await page.getByRole('button', { name: /My devices/ }).click();
  const renewal = page.getByRole('button', { name: 'Renew this device’s security key', exact: true });
  await renewal.click();
  await page.waitForFunction(() => [...document.querySelectorAll('button')].some(button => button.textContent === 'Renew this device’s security key' && !button.disabled));
  assert.equal(rotations, 1);
  await page.getByText('Admin approved', { exact: true }).waitFor();
  assert.deepEqual(errors, []);
  console.log('PASS settings: password confirmation, 30-day scheduling/cancellation, manual key renewal and preserved approval');
} finally { await browser.close(); }
