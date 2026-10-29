import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import vm from 'node:vm';
import { test } from 'node:test';
const require = createRequire(new URL('../../module1-frontend/package.json', import.meta.url));
const ts = require('typescript');
function client(fetch) {
  const context = { exports: {}, process: { env: {} }, AbortController, DOMException, TypeError, Error,
    sessionStorage: { removeItem() {} }, window: { setTimeout, clearTimeout }, fetch };
  vm.runInNewContext(ts.transpileModule(readFileSync(new URL('../../module1-frontend/lib/api/client.ts', import.meta.url), 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText, context);
  return context.exports;
}
const response = (status, data = {}) => ({ status, ok: status < 400, json: async () => data });
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done; }); return { promise, resolve }; };
test('simultaneous 401s share one refresh and retry with its token', async () => {
  const gate = deferred(); let refreshes = 0;
  const c = client(async (url, options) => {
    if (url.endsWith('/auth/refresh')) { refreshes++; await gate.promise; return response(200, { access_token: 'fresh' }); }
    return response(options.headers.Authorization === 'Bearer fresh' ? 200 : 401);
  });
  c.setAccessToken('expired');
  const requests = [c.apiRequest('/one'), c.apiRequest('/two'), c.apiRequest('/three')];
  await new Promise(resolve => setImmediate(resolve)); gate.resolve();
  await Promise.all(requests);
  assert.equal(refreshes, 1);
});
test('a slow old-token 401 retries the already refreshed token without another refresh', async () => {
  const slow = deferred(); let refreshes = 0;
  const c = client(async (url, options) => {
    if (url.endsWith('/auth/refresh')) { refreshes++; return response(200, { access_token: 'fresh' }); }
    if (url.endsWith('/slow') && options.headers.Authorization === 'Bearer expired') await slow.promise;
    return response(options.headers.Authorization === 'Bearer fresh' ? 200 : 401);
  });
  c.setAccessToken('expired'); const pending = c.apiRequest('/slow');
  await c.apiRequest('/fast'); slow.resolve(); await pending;
  assert.equal(refreshes, 1);
});
test('logout and a newer login cannot be overwritten by a late refresh response', async () => {
  const gate = deferred(); let lastToken;
  const c = client(async (url, options) => {
    if (url.endsWith('/auth/refresh')) { await gate.promise; return response(200, { access_token: 'old-account' }); }
    lastToken = options.headers.Authorization; return response(200);
  });
  const pending = c.refreshAccessToken(); c.clearTokens(); c.setAccessToken('new-account');
  gate.resolve(); assert.equal(await pending, false);
  await c.apiRequest('/me'); assert.equal(lastToken, 'Bearer new-account');
});
test('callers share failure while session restoration can request the connectivity error', async () => {
  const gate = deferred(); let calls = 0;
  const c = client(async () => { calls++; await gate.promise; return response(503); });
  const ordinary = c.refreshAccessToken(); const strict = c.refreshAccessToken(true);
  const rejected = assert.rejects(strict, error => error.status === 503);
  gate.resolve(); assert.equal(await ordinary, false); await rejected; assert.equal(calls, 1);
});
