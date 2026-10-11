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
const source = readFileSync(new URL('../../module1-frontend/components/PwaUpdates.tsx', import.meta.url), 'utf8');
const javascript = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX } }).outputText;

async function setup(hasUpdate = true) {
  const window = new EventTarget(), document = new EventTarget();
  const serviceWorker = new EventTarget(), registration = new EventTarget(), worker = new EventTarget();
  worker.state = 'installed'; worker.postMessage = () => {};
  registration.waiting = hasUpdate ? worker : null;
  serviceWorker.register = async () => registration;
  let reloads = 0, timeout;
  const context = { exports: {}, window, document, navigator: { serviceWorker, onLine: true },
    location: { reload: () => reloads++ }, process: { env: { NODE_ENV: 'production' } },
    setTimeout: callback => { timeout = callback; return 1; }, clearTimeout: () => { timeout = undefined; },
    require: name => dependencies(name) };
  vm.runInNewContext(javascript, context);
  let renderer;
  await act(async () => { renderer = create(React.createElement(context.exports.PwaUpdates, { busy: false })); });
  return { renderer, worker, get reloads() { return reloads; },
    click: () => act(() => renderer.root.findByType('button').props.onClick()),
    expire: () => act(() => timeout()), close: () => act(() => renderer.unmount()) };
}
test('no waiting worker means no update banner', async () => {
  const c = await setup(false);
  try { assert.equal(c.renderer.toJSON(), null); } finally { c.close(); }
});
test('already activated worker reloads immediately instead of waiting forever', async () => {
  const c = await setup();
  try { c.worker.state = 'activated'; c.click(); assert.equal(c.reloads, 1); } finally { c.close(); }
});
test('activation reloads once after explicit update', async () => {
  const c = await setup();
  try {
    c.click(); assert.equal(c.reloads, 0);
    act(() => { c.worker.state = 'activated'; c.worker.dispatchEvent(new Event('statechange')); });
    assert.equal(c.reloads, 1);
  } finally { c.close(); }
});
test('stalled update gives retry guidance and enables the button', async () => {
  const c = await setup();
  try {
    c.click(); c.expire();
    assert.equal(c.renderer.root.findByType('button').props.disabled, false);
    assert(JSON.stringify(c.renderer.toJSON()).includes('taking longer'));
    assert.equal(c.reloads, 0);
  } finally { c.close(); }
});
