import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { test } from 'node:test';
import vm from 'node:vm';
const ts = createRequire(new URL('../../module1-frontend/package.json', import.meta.url))('typescript');
test('installed app scope contains attendance and excludes dashboard', () => {
  const source = readFileSync(new URL('../../module1-frontend/app/manifest.ts', import.meta.url), 'utf8');
  const context = { exports: {} };
  vm.runInNewContext(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText, context);
  const manifest = context.exports.default();
  assert.equal(manifest.id, '/');
  assert.ok(manifest.start_url.startsWith(manifest.scope));
  assert.equal('/dashboard'.startsWith(manifest.scope), false);
});
test('offline attendance navigation restores its shell; dashboard and API stay outside cache handling', async () => {
  const events = new Map();
  const context = { URL, CACHE: 'test-cache', SHELL: ['/', '/attendance'], importScripts() {},
    self: { location: { origin: 'https://example.test' }, addEventListener: (name, handler) => events.set(name, handler) },
    fetch: async () => { throw new Error('offline'); },
    caches: { open: async () => ({ match: async path => `cached:${path}` }) },
    Response: { error: () => 'error' },
  };
  vm.runInNewContext(readFileSync(new URL('../../module1-frontend/public/sw.js', import.meta.url), 'utf8'), context);
  let result;
  const event = path => ({ request: { method: 'GET', mode: 'navigate', url: `https://example.test${path}` }, respondWith: promise => { result = promise; } });
  events.get('fetch')(event('/attendance')); assert.equal(await result, 'cached:/attendance');
  for (const path of ['/dashboard', '/api/v1/users/me']) {
    result = undefined; events.get('fetch')(event(path)); assert.equal(result, undefined);
  }
});
