// npm install --prefix /private/tmp/saiv-pwa-tests fake-indexeddb
// node --test new-tests/pwa/unit.test.mjs
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { test } from 'node:test';
import vm from 'node:vm';
const frontend = createRequire(new URL('../../module1-frontend/package.json', import.meta.url));
const dependencies = createRequire(`${process.env.PWA_TEST_DEPENDENCIES ?? '/private/tmp/saiv-pwa-tests'}/package.json`);
const ts = frontend('typescript');
const { IDBFactory } = dependencies('fake-indexeddb');
const source = readFileSync(new URL('../../module1-frontend/lib/offline/sessionCache.ts', import.meta.url), 'utf8');

function cacheClient() {
  const items = new Map();
  let now = Date.now();
  class Clock extends Date { static now() { return now; } }
  const context = { exports: {}, Date: Clock, window: { indexedDB: new IDBFactory() }, localStorage: {
    getItem: key => items.get(key) ?? null,
    setItem: (key, value) => items.set(key, value), removeItem: key => items.delete(key),
  } };
  vm.runInNewContext(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText, context);
  return { ...context.exports, advance: milliseconds => { now += milliseconds; } };
}
const session = (id, closes = Date.now() + 3600000) => ({ id, name: id, status: 'active', checkin_closes_at: new Date(closes).toISOString(), latitude: 1, image: 'private-biometric', motion_verification_id: 'private-proof' });

test('snapshots are isolated by account and omit sensitive verification fields', async () => {
  const c = cacheClient();
  c.setOfflineAccount('a');
  await c.cacheActiveSessions('a', [session('a-session')]);
  c.setOfflineAccount('b');
  assert.equal(await c.getCachedActiveSessions('b'), null);
  await c.cacheActiveSessions('b', [session('b-session')]);
  const a = await c.getCachedActiveSessions('a');
  const b = await c.getCachedActiveSessions('b');
  assert.equal(a.sessions[0].id, 'a-session');
  assert.equal(b.sessions[0].id, 'b-session');
  assert.equal(a.sessions[0].image, undefined);
  assert.equal(a.sessions[0].latitude, undefined);
  assert.equal(a.sessions[0].motion_verification_id, undefined);
});

test('expired sessions are filtered and stale snapshots are unavailable', async () => {
  const c = cacheClient(); c.setOfflineAccount('a');
  await c.cacheActiveSessions('a', [session('open'), session('closed', Date.now() - 1000)]);
  assert.deepEqual(Array.from((await c.getCachedActiveSessions('a')).sessions, item => item.id), ['open']);
  c.advance(15 * 60000 + 1);
  assert.equal(await c.getCachedActiveSessions('a'), null);
});

test('logout clears all accounts and late requests cannot repopulate snapshots', async () => {
  const c = cacheClient(); c.setOfflineAccount('a');
  await c.cacheActiveSessions('a', [session('open')]);
  await c.clearOfflineSessions();
  assert.equal(c.getOfflineAccount(), null);
  await c.cacheActiveSessions('a', [session('late')]);
  assert.equal(await c.getCachedActiveSessions('a'), null);
});

function worker(fetchFails = false) {
  const handlers = {};
  const cachesByName = new Map([['unrelated-app', new Map()], ['saiv-shell-old', new Map()]]);
  const calls = [];
  const cache = name => {
    if (!cachesByName.has(name)) cachesByName.set(name, new Map());
    const values = cachesByName.get(name);
    return { addAll: async paths => {
      if (fetchFails) throw new Error('Missing build asset');
      paths.forEach(path => values.set(path, { saved: path }));
    }, match: async request => values.get(typeof request === 'string' ? request : new URL(request.url).pathname) };
  };
  const context = { URL, Set, Response,
    CACHE: 'saiv-shell-test', SHELL: ['/', '/icon.svg', '/manifest.webmanifest', '/_next/static/app.js', '/_next/static/app.css'], importScripts: () => {}, self: { location: { origin: 'https://saiv.test' }, addEventListener: (name, handler) => { handlers[name] = handler; }, skipWaiting: () => calls.push('skipWaiting') },
    caches: { open: async name => cache(name), keys: async () => [...cachesByName.keys()], delete: async name => cachesByName.delete(name) },
    fetch: async request => { calls.push(request); if (fetchFails) throw new TypeError('Offline'); return { network: true }; },
  };
  const script = readFileSync(new URL('../../module1-frontend/public/sw.js', import.meta.url), 'utf8');
  vm.runInNewContext(script, context);
  return { handlers, cachesByName, calls };
}
const lifecycle = async (w, name) => { let work; w.handlers[name]({ waitUntil: promise => { work = promise; } }); await work; };

test('installation saves all shell assets before completing; activation preserves unrelated caches', async () => {
  const w = worker(); await lifecycle(w, 'install');
  assert(w.cachesByName.get('saiv-shell-test').has('/_next/static/app.css'));
  assert(w.cachesByName.get('saiv-shell-test').has('/_next/static/app.js'));
  await lifecycle(w, 'activate');
  assert(!w.cachesByName.has('saiv-shell-old'));
  assert(w.cachesByName.has('unrelated-app'));
});

test('failed precaching rejects installation and leaves the active old cache intact', async () => {
  const w = worker(true);
  await assert.rejects(lifecycle(w, 'install'), /Missing build asset/);
  assert(w.cachesByName.has('saiv-shell-old'));
});

test('worker ignores API, POST, RSC and external requests; updates require a message', async () => {
  const w = worker(); await lifecycle(w, 'install');
  for (const [url, method] of [['https://saiv.test/api/v1/sessions/active', 'GET'], ['https://saiv.test/', 'POST'], ['https://saiv.test/?_rsc=123', 'GET'], ['https://other.test/app.js', 'GET'], ['https://saiv.test/mediapipe/face_landmarker.task', 'GET']]) {
    let handled = false;
    w.handlers.fetch({ request: { url, method, mode: 'cors' }, respondWith: () => { handled = true; } });
    assert.equal(handled, false);
  }
  assert.equal(w.calls.length, 0);
  w.handlers.message({ data: { type: 'SKIP_WAITING' } });
  assert.deepEqual(w.calls, ['skipWaiting']);
});
