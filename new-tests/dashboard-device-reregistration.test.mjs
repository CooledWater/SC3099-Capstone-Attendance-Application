import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { webcrypto } from 'node:crypto';
import { test } from 'node:test';
import vm from 'node:vm';
const ts = createRequire(new URL('../module1-frontend/package.json', import.meta.url))('typescript');
const { IDBFactory } = createRequire(`${process.env.PWA_TEST_DEPENDENCIES ?? '/private/tmp/saiv-pwa-tests'}/package.json`)('fake-indexeddb');
const javascript = ts.transpileModule(readFileSync(new URL('../module4-observability/src/lib/devices.ts', import.meta.url), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;

async function setup(device) {
  const indexedDB = new IDBFactory();
  const keys = await webcrypto.subtle.generateKey({ name: 'ECDSA', namedCurve: 'P-256' }, false, ['sign', 'verify']);
  await new Promise((resolve, reject) => {
    const request = indexedDB.open('saiv-device-keys', 1);
    request.onupgradeneeded = () => request.result.createObjectStore('identities');
    request.onerror = () => reject(request.error);
    request.onsuccess = () => {
      const db = request.result;
      const transaction = db.transaction('identities', 'readwrite');
      transaction.objectStore('identities').put({ fingerprint: 'browser', publicKey: 'public-key', privateKey: keys.privateKey }, 'browser-installation-v1');
      transaction.oncomplete = () => { db.close(); resolve(); };
    };
  });
  const requests = [];
  const api = { request: async (path, options) => {
    requests.push(path);
    if (path === '/devices/my-devices') return [device];
    if (path === '/devices/registration-challenges') return { challenge_id: 'nonce', challenge: 'sign-me' };
    if (path === '/devices/register') {
      const payload = JSON.parse(options.body);
      assert.equal(payload.reregister_removed, true);
      assert.equal(payload.device_fingerprint, 'browser');
      assert.equal(payload.registration_challenge_id, 'nonce');
      assert.equal(await webcrypto.subtle.verify({ name: 'ECDSA', hash: 'SHA-256' }, keys.publicKey,
        Buffer.from(payload.registration_signature, 'base64'), new TextEncoder().encode('sign-me')), true);
      return { ...device, is_removed: false, is_active: true };
    }
    throw new Error(path);
  } };
  const context = { exports: {}, indexedDB, crypto: webcrypto, TextEncoder, Uint8Array, btoa,
    require: name => { assert.equal(name, '@/lib/api'); return { api }; } };
  vm.runInNewContext(javascript, context);
  return { client: context.exports, requests };
}

test('dashboard sign-in can submit fresh signed re-registration for the removed browser', async () => {
  const { client, requests } = await setup({ is_removed: true, browser_fingerprint: 'browser' });
  await client.reregisterRemovedBrowser();
  assert.deepEqual(requests, ['/devices/my-devices', '/devices/registration-challenges', '/devices/register']);
});
for (const device of [{ is_removed: false, is_active: false, browser_fingerprint: 'browser' },
  { is_removed: true, browser_fingerprint: 'another-browser' }]) {
  test(`dashboard does not restore ${device.is_removed ? 'another browser' : 'an admin-deactivated browser'}`, async () => {
    const { client, requests } = await setup(device);
    await client.reregisterRemovedBrowser();
    assert.deepEqual(requests, ['/devices/my-devices']);
  });
}
