import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { webcrypto } from 'node:crypto';
import { test } from 'node:test';
import vm from 'node:vm';
const frontend = createRequire(new URL('../../module1-frontend/package.json', import.meta.url));
const dependencies = createRequire(`${process.env.PWA_TEST_DEPENDENCIES ?? '/private/tmp/saiv-pwa-tests'}/package.json`);
const { IDBFactory } = dependencies('fake-indexeddb');
const ts = frontend('typescript');
const source = readFileSync(new URL('../../module1-frontend/lib/device.ts', import.meta.url), 'utf8');
const javascript = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
function client(indexedDB = new IDBFactory(), request = async () => []) {
  const context = { exports: {}, TextEncoder, Uint8Array, Array, Object, Map, Promise, Error, indexedDB, crypto: webcrypto, btoa,
    navigator: { userAgent: 'Chrome', platform: 'MacIntel', maxTouchPoints: 0 },
    require: name => { assert.equal(name, './api/client'); return { apiRequest: request }; } };
  vm.runInNewContext(javascript, context);
  return context.exports;
}
test('browser identity survives reload, is shared across accounts, and private key cannot be exported', async () => {
  const storage = new IDBFactory();
  const first = await client(storage).getDeviceIdentity('student-a');
  const reloaded = await client(storage).getDeviceIdentity('student-a');
  assert.equal(first.fingerprint, reloaded.fingerprint);
  assert.match(first.fingerprint, /^[a-f0-9]{64}$/);
  assert.equal(first.fingerprint, (await client(storage).getDeviceIdentity('student-b')).fingerprint);
  await assert.rejects(webcrypto.subtle.exportKey('pkcs8', first.privateKey));
});
test('concurrent browser tabs converge on the persisted key', async () => {
  const storage = new IDBFactory();
  const [first, second] = await Promise.all([client(storage).getDeviceIdentity('student'), client(storage).getDeviceIdentity('student')]);
  assert.equal(first.fingerprint, second.fingerprint);
});
test('existing disabled registration is reused and never automatically enabled', async () => {
  const storage = new IDBFactory();
  const fingerprint = (await client(storage).getDeviceIdentity('student')).fingerprint;
  const calls = [];
  const c = client(storage, async (path, options) => { calls.push(path); return [{ id: 'device', device_fingerprint: fingerprint, browser_fingerprint: fingerprint, browser_identity_verified: true, is_active: false }]; });
  assert.equal((await c.registerCurrentDevice('student')).is_active, false);
  await assert.rejects(c.createDeviceProof('student', 'session'), /disabled/);
  assert.ok(calls.every(path => path === '/devices/my-devices'));
});
test('check-in proof signs the exact server challenge with the registered key', async () => {
  let registration;
  const c = client(new IDBFactory(), async (path, options) => {
    if (path === '/devices/my-devices') return registration ? [registration] : [];
    if (path === '/devices/registration-challenges') return { challenge_id: 'registration-challenge', challenge: 'registration-nonce' };
    if (path === '/devices/register') { registration = { ...JSON.parse(options.body), id: 'device', is_active: true }; return registration; }
    if (path === '/devices/challenges') { assert.equal(JSON.parse(options.body).session_id, 'session'); return { challenge_id: 'challenge', challenge: 'server-session-specific-nonce' }; }
    throw new Error(path);
  });
  const proof = await c.createDeviceProof('student', 'session');
  const der = Buffer.from(registration.public_key.replace(/-----[^-]+-----/g, '').replace(/\s/g, ''), 'base64');
  const publicKey = await webcrypto.subtle.importKey('spki', der, { name: 'ECDSA', namedCurve: 'P-256' }, false, ['verify']);
  assert.equal(await webcrypto.subtle.verify({ name: 'ECDSA', hash: 'SHA-256' }, publicKey, Buffer.from(proof.device_signature, 'base64'), new TextEncoder().encode('server-session-specific-nonce')), true);
  assert.equal(proof.device_challenge_id, 'challenge');
});

test('Profile shows current device, pending approval, and saved disabling', async () => {
  const React = dependencies('react');
  const { create, act } = dependencies('react-test-renderer');
  let device = { id: 'device', device_name: 'My phone', device_fingerprint: 'a'.repeat(64), is_active: true, is_trusted: false, last_seen_at: '2026-10-26T00:00:00Z', total_checkins: 2 };
  const mutations = [];
  const context = { exports: {}, Error, window: { confirm: () => true }, require: name => {
    if (name === 'react') return React;
    if (name === 'react/jsx-runtime') return dependencies(name);
    if (name === '@/lib/time') return { formatSingaporeDateTime: () => '26 Oct 2026' };
    if (name === '@/lib/device') return {
      registerCurrentDevice: async () => device, listDevices: async () => [device],
      getDeviceIdentity: async () => ({ fingerprint: device.device_fingerprint }),
      browserFingerprint: item => item.browser_fingerprint ?? item.device_fingerprint,
      changeDevice: async (id, changes) => { mutations.push([id, changes.is_active]); device = { ...device, ...changes }; },
    };
    throw new Error(name);
  } };
  const source = readFileSync(new URL('../../module1-frontend/components/MyDevices.tsx', import.meta.url), 'utf8');
  vm.runInNewContext(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX } }).outputText, context);
  let renderer;
  await act(async () => { renderer = create(React.createElement(context.exports.MyDevices, { userId: 'student', demo: false, visible: true })); });
  await act(async () => renderer.root.findByProps({ 'aria-expanded': false }).props.onClick());
  assert.ok(JSON.stringify(renderer.toJSON()).includes('Awaiting admin approval'));
  assert.ok(JSON.stringify(renderer.toJSON()).includes('This device'));
  await act(async () => renderer.root.findAllByType('button').find(item => item.children.includes('Disable')).props.onClick());
  assert.deepEqual(mutations, [['device', false]]);
  assert.ok(JSON.stringify(renderer.toJSON()).includes('Disabled'));
  act(() => renderer.unmount());
});

test('upgrade adopts an existing account key without generating a new registration', async () => {
  const storage = new IDBFactory();
  const oldIdentity = await client().getDeviceIdentity('old-account');
  const db = await new Promise((resolve, reject) => {
    const request = storage.open('saiv-device-keys', 1);
    request.onupgradeneeded = () => request.result.createObjectStore('identities');
    request.onsuccess = () => resolve(request.result); request.onerror = () => reject(request.error);
  });
  await new Promise((resolve, reject) => {
    const transaction = db.transaction('identities', 'readwrite');
    transaction.objectStore('identities').add(oldIdentity, 'old-account');
    transaction.oncomplete = resolve; transaction.onabort = () => reject(transaction.error);
  });
  db.close();
  assert.equal((await client(storage).getDeviceIdentity('old-account')).fingerprint, oldIdentity.fingerprint);
  assert.equal((await client(storage).getDeviceIdentity('another-account')).fingerprint, oldIdentity.fingerprint);
});

test('registration-limit errors leave Profile device management available', async () => {
  const React = dependencies('react');
  const { create, act } = dependencies('react-test-renderer');
  let rows = [1, 2].map(number => ({ id: String(number), device_name: `Device ${number}`, device_fingerprint: String(number).repeat(64), is_active: true, is_trusted: true, last_seen_at: '2026-10-26T00:00:00Z', total_checkins: 1 }));
  const context = { exports: {}, Error, window: { confirm: () => true }, require: name => {
    if (name === 'react') return React;
    if (name === 'react/jsx-runtime') return dependencies(name);
    if (name === '@/lib/time') return { formatSingaporeDateTime: () => '26 Oct' };
    if (name === '@/lib/device') return {
      listDevices: async () => rows, getDeviceIdentity: async () => ({ fingerprint: 'new-browser' }), browserFingerprint: item => item.device_fingerprint,
      registerCurrentDevice: async () => { if (rows.every(row => row.is_active)) throw new Error('Your account already has two active devices.'); return {}; },
      changeDevice: async (id, changes) => { rows = rows.map(row => row.id === id ? { ...row, ...changes } : row); },
    };
    throw new Error(name);
  } };
  const source = readFileSync(new URL('../../module1-frontend/components/MyDevices.tsx', import.meta.url), 'utf8');
  vm.runInNewContext(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX } }).outputText, context);
  let renderer;
  await act(async () => { renderer = create(React.createElement(context.exports.MyDevices, { userId: 'student', demo: false, visible: true })); });
  await act(async () => renderer.root.findByProps({ 'aria-expanded': false }).props.onClick());
  assert.ok(renderer.root.findByProps({ role: 'alert' }).children[0].includes('two active devices'));
  const disable = renderer.root.findAllByType('button').find(item => item.children.includes('Disable'));
  assert.equal(disable.props.disabled, false);
  await act(async () => disable.props.onClick());
  assert.ok(rows.some(row => !row.is_active));
  assert.equal(renderer.root.findAllByProps({ role: 'alert' }).length, 0);
  act(() => renderer.unmount());
});
