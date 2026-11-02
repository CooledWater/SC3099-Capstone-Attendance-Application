import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import { test } from 'node:test';

function worker(owner = 'student-one') {
  const handlers = {};
  const notifications = [], opened = [], focused = [];
  const context = {
    importScripts() {}, SHELL: [], CACHE: 'test', URL,
    indexedDB: { open() {
      const request = {};
      queueMicrotask(() => {
        request.result = { close() {}, transaction: () => ({ objectStore: () => ({ get() {
          const read = {};
          queueMicrotask(() => { read.result = owner; read.onsuccess(); });
          return read;
        } }) }) };
        request.onsuccess();
      });
      return request;
    } },
    self: {
      addEventListener: (type, handler) => { handlers[type] = handler; },
      location: { origin: 'https://attendance.test' },
      registration: { showNotification: async (...args) => notifications.push(args) },
      clients: { matchAll: async () => [], openWindow: async url => opened.push(url) },
    },
  };
  vm.runInNewContext(readFileSync(new URL('../../module1-frontend/public/sw.js', import.meta.url), 'utf8'), context);
  async function dispatch(type, data) {
    let pending;
    handlers[type]({ ...data, waitUntil: promise => { pending = promise; } });
    await pending;
  }
  return { context, notifications, opened, focused, dispatch };
}

test('approval push displays instructor message with fixed title and stable tag', async () => {
  const sw = worker();
  await sw.dispatch('push', { data: { json: () => ({ type: 'attendance-approved', user_id: 'student-one', checkin_id: 'checkin-1', body: 'Your GPS issue was confirmed. Attendance approved.', title: 'Attendance approved from SAIV' }) } });
  assert.equal(sw.notifications.length, 1);
  const [title, options] = sw.notifications[0];
  assert.equal(title, 'Attendance approved');
  assert.equal(options.tag, 'attendance-approved-checkin-1');
  assert.equal(options.body, 'Your GPS issue was confirmed. Attendance approved.');
});

test('signed-out and different-account browsers suppress old pushes', async () => {
  for (const owner of ['', 'other-student']) {
    const sw = worker(owner);
    await sw.dispatch('push', { data: { json: () => ({ type: 'attendance-approved', user_id: 'student-one' }) } });
    assert.equal(sw.notifications.length, 0);
  }
});

test('malformed or unrelated pushes are ignored', async () => {
  const sw = worker();
  await sw.dispatch('push', { data: { json() { throw new SyntaxError(); } } });
  await sw.dispatch('push', { data: { json: () => ({ type: 'other', user_id: 'student-one' }) } });
  assert.equal(sw.notifications.length, 0);
});

test('notification click opens same-origin dashboard and ignores supplied URLs', async () => {
  const sw = worker();
  let closed = false;
  await sw.dispatch('notificationclick', { notification: { close() { closed = true; }, data: { userId: 'student-one', url: 'https://evil.test' } } });
  assert.ok(closed);
  assert.deepEqual(sw.opened, ['https://attendance.test/dashboard/']);
});

test('existing dashboard window is focused; logged-out clicks do not navigate', async () => {
  const sw = worker();
  const actions = [];
  sw.context.self.clients.matchAll = async () => [{ url: 'https://attendance.test/dashboard/', navigate: async url => actions.push(url), focus: async () => actions.push('focus') }];
  await sw.dispatch('notificationclick', { notification: { close() {}, data: { userId: 'student-one' } } });
  assert.deepEqual(actions, ['https://attendance.test/dashboard/', 'focus']);
  const signedOut = worker('');
  await signedOut.dispatch('notificationclick', { notification: { close() {}, data: { userId: 'student-one' } } });
  assert.equal(signedOut.opened.length, 0);
});

for (const body of [undefined, null, '', '   ', 42]) test(`missing or invalid message uses default: ${body}`, async () => {
  const sw = worker();
  await sw.dispatch('push', { data: { json: () => ({ type: 'attendance-approved', user_id: 'student-one', body }) } });
  assert.equal(sw.notifications[0][1].body, 'Your attendance has been approved. Tap to view your attendance.');
});
