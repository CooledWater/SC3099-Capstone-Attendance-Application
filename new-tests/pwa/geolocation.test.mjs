import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { test } from 'node:test';
import vm from 'node:vm';
const frontend = createRequire(new URL('../../module1-frontend/package.json', import.meta.url));
const dependencies = createRequire(`${process.env.PWA_TEST_DEPENDENCIES ?? '/private/tmp/saiv-pwa-tests'}/package.json`);
const React = dependencies('react');
const { create, act } = dependencies('react-test-renderer');
const ts = frontend('typescript');
const source = readFileSync(new URL('../../module1-frontend/features/geolocation/useGeolocation.ts', import.meta.url), 'utf8');
const javascript = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
function mountHook() {
  const requests = [];
  const context = { exports: {}, require: name => { assert.equal(name, 'react'); return React; }, process: { env: {} },
    window: { isSecureContext: true }, navigator: { geolocation: { getCurrentPosition: (success, error) => { requests.push({ success, error }); } } } };
  vm.runInNewContext(javascript, context);
  let current;
  function Component() { current = context.exports.useGeolocation(); return null; }
  let renderer;
  act(() => { renderer = create(React.createElement(Component)); });
  return { requests, get current() { return current; }, unmount: () => act(() => renderer.unmount()) };
}
const position = { coords: { latitude: 1.3, longitude: 103.8, accuracy: 10 } };

test('reset invalidates pending GPS results and errors', async () => {
  const hook = mountHook();
  try {
    await act(async () => { await hook.current.request(); });
    act(() => hook.current.reset());
    act(() => hook.requests[0].success(position));
    assert.equal(hook.current.state, 'idle');
    assert.equal(hook.current.point, undefined);
    act(() => hook.requests[0].error({ code: 1, PERMISSION_DENIED: 1 }));
    assert.equal(hook.current.state, 'idle');
  } finally { hook.unmount(); }
});

test('a newer location request ignores an older response', async () => {
  const hook = mountHook();
  try {
    await act(async () => { await hook.current.request(); });
    await act(async () => { await hook.current.request(); });
    act(() => hook.requests[0].success(position));
    assert.equal(hook.current.state, 'requesting');
    assert.equal(hook.current.point, undefined);
    act(() => hook.requests[1].success(position));
    assert.equal(hook.current.state, 'ready');
    assert.equal(hook.current.point.latitude, 1.3);
    await act(async () => { await hook.current.request(); });
    assert.equal(hook.current.point, undefined);
  } finally { hook.unmount(); }
});
