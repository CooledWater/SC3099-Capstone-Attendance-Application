// Setup: npm install --prefix /private/tmp/saiv-pwa-tests playwright-core fake-indexeddb
// Run after npm run build and npm run start (port 13010): node new-tests/pwa/browser.mjs
// Override PWA_TEST_DEPENDENCIES, PWA_TEST_URL or PWA_BROWSER_PATH as needed.
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { readFile, writeFile } from 'node:fs/promises';
const require = createRequire(`${process.env.PWA_TEST_DEPENDENCIES ?? '/private/tmp/saiv-pwa-tests'}/package.json`);
const { chromium } = require('playwright-core');
const origin = process.env.PWA_TEST_URL ?? 'http://127.0.0.1:13010';
const workerPath = new URL('../../module1-frontend/public/sw-precache.js', import.meta.url);
const originalWorker = await readFile(workerPath, 'utf8');
const browser = await chromium.launch({ executablePath: process.env.PWA_BROWSER_PATH ?? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless: true, args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'] });
let context;
try {
  context = await browser.newContext({ permissions: ['camera'] });
  let sessionRequests = 0;
  let sessionName = 'Original seminar';
  let status = 200;
  const user = { id: 'student-a', email: 'a@test.local', full_name: 'Test Student', role: 'student' };
  await context.route('**/api/v1/**', async route => {
    const path = new URL(route.request().url()).pathname;
    let body;
    let code = 200;
    if (path.endsWith('/auth/refresh')) body = { access_token: 'test-token' };
    else if (path.endsWith('/users/me')) body = user;
    else if (path.endsWith('/sessions/active') || path.endsWith('/sessions/my-sessions')) {
      sessionRequests++;
      code = status;
      body = status === 200 ? [{ id: 'session-a', name: sessionName, status: 'active', course_code: 'SC3099', scheduled_start: new Date().toISOString(), scheduled_end: new Date(Date.now() + 3600000).toISOString(), checkin_opens_at: new Date().toISOString(), checkin_closes_at: new Date(Date.now() + 3600000).toISOString(), venue_name: 'Test room' }] : { detail: 'Permission denied' };
    } else if (path.endsWith('/checkins/my-checkins')) body = [];
    else body = {};
    await route.fulfill({ status: code, contentType: 'application/json', body: JSON.stringify(body) });
  });
  const page = await context.newPage();
  const pageErrors = [];
  page.on('pageerror', error => pageErrors.push(error.message));
  await page.goto(origin);
  await page.getByRole('heading', { name: 'Original seminar' }).waitFor();
  await page.evaluate(async () => {
    await navigator.serviceWorker.ready;
    await new Promise(resolve => {
      const check = () => {
        const request = indexedDB.open('saiv-offline', 2);
        request.onsuccess = () => {
          const db = request.result;
          const read = db.transaction('session-snapshots').objectStore('session-snapshots').get('active-sessions:student-a');
          read.onsuccess = () => { db.close(); if (read.result) resolve(); else setTimeout(check, 50); };
        };
      };
      check();
    });
  });
  const cachedPaths = await page.evaluate(async () => {
    const keys = await caches.keys();
    const cache = await caches.open(keys.find(key => key.startsWith('saiv-shell-')));
    return (await cache.keys()).map(request => new URL(request.url).pathname);
  });
  assert(cachedPaths.some(path => path.endsWith('.css')));
  assert(cachedPaths.some(path => path.includes('/chunks/app/page-') && path.endsWith('.js')));
  assert(!cachedPaths.some(path => path.includes('/api/')));
  console.log('PASS: first visit precaches HTML, CSS and page JavaScript without API data');

  await context.setOffline(true);
  await page.reload();
  await page.getByRole('heading', { name: 'Saved sessions' }).waitFor();
  await page.getByText('You are offline — saved sessions only', { exact: true }).waitFor();
  await page.getByRole('heading', { name: 'Original seminar' }).waitFor();
  assert.equal(await page.getByRole('button', { name: 'Submit check-in', exact: true }).count(), 0);
  await page.getByText(/Last saved:/).waitFor();
  console.log('PASS: offline refresh displays labelled read-only sessions and saved time');

  sessionName = 'Fresh seminar';
  const before = sessionRequests;
  await context.setOffline(false);
  await page.getByRole('heading', { name: 'Fresh seminar' }).waitFor();
  assert(sessionRequests > before);
  console.log('PASS: reconnection restores authentication and fetches fresh sessions');

  await context.setOffline(true);
  await page.getByRole('heading', { name: 'Saved sessions' }).waitFor();
  status = 403;
  await context.setOffline(false);
  await page.getByText('Permission denied', { exact: true }).waitFor();
  assert.equal(await page.getByRole('heading', { name: 'Saved sessions' }).count(), 0);
  assert.equal(await page.getByRole('heading', { name: 'Fresh seminar' }).count(), 0);
  console.log('PASS: permission errors do not display cached sessions');

  status = 200;
  await page.reload();
  await page.getByRole('heading', { name: 'Fresh seminar' }).waitFor();
  // A different script/cache version represents a newly deployed build.
  await writeFile(workerPath, originalWorker.replace(/saiv-shell-([^"']+)/, 'saiv-shell-test-update-$1'));
  await page.evaluate(async () => { await (await navigator.serviceWorker.getRegistration()).update(); });
  const update = page.getByRole('button', { name: 'Update and reload' });
  await update.waitFor();
  assert.equal(await update.isEnabled(), true);
  await page.getByRole('checkbox', { name: /I consent to camera verification/ }).check();
  await page.getByRole('button', { name: /Start camera|Allow camera access/ }).click();
  await page.getByRole('heading', { name: 'Confirm your location' }).waitFor();
  assert.equal(await update.isEnabled(), false);
  await page.reload();
  await page.getByRole('heading', { name: 'Fresh seminar' }).waitFor();
  await update.waitFor();
  await page.waitForFunction(() => [...document.querySelectorAll('button')].some(button => button.textContent === 'Update and reload' && !button.disabled));
  await Promise.all([page.waitForNavigation({ waitUntil: 'load' }), update.click()]);
  await page.waitForFunction(() => navigator.serviceWorker.controller?.state === 'activated');
  await page.getByRole('heading', { name: 'Fresh seminar' }).waitFor();
  await page.waitForFunction(async () => (await caches.keys()).some(key => key.startsWith('saiv-shell-test-update-')));
  console.log('PASS: updates are blocked during camera check-in, then activate and reload on request');

  await context.setOffline(true);
  await page.reload();
  await page.getByRole('heading', { name: 'Saved sessions' }).waitFor();
  await page.getByRole('button', { name: 'Sign out and clear saved sessions' }).click();
  await page.getByRole('heading', { name: 'Sign in to your account' }).waitFor();
  const remaining = await page.evaluate(async () => {
    const owner = localStorage.getItem('saiv-offline-owner');
    const count = await new Promise(resolve => {
      const request = indexedDB.open('saiv-offline', 2);
      request.onsuccess = () => {
        const db = request.result;
        const read = db.transaction('session-snapshots').objectStore('session-snapshots').count();
        read.onsuccess = () => { db.close(); resolve(read.result); };
      };
    });
    return { owner, count };
  });
  assert.deepEqual(remaining, { owner: null, count: 0 });
  await page.reload();
  await page.getByRole('heading', { name: 'Sign in to your account' }).waitFor();
  assert.deepEqual(pageErrors, []);
  console.log('PASS: offline logout clears snapshots and remains signed out after reload');
} finally {
  await writeFile(workerPath, originalWorker);
  await context?.close();
  await browser.close();
}
