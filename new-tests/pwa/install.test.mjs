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
const source = readFileSync(new URL('../../module1-frontend/components/PwaInstall.tsx', import.meta.url), 'utf8');
const javascript = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX } }).outputText;
function setup({ busy = false, standalone = false } = {}) {
  const window = new EventTarget();
  const media = new EventTarget(); media.matches = standalone;
  window.matchMedia = () => media;
  const context = { exports: {}, window, navigator: {}, require: name => dependencies(name) };
  vm.runInNewContext(javascript, context);
  let renderer;
  act(() => { renderer = create(React.createElement(context.exports.PwaInstall, { busy })); });
  let prompts = 0;
  const offer = outcome => {
    const event = new Event('beforeinstallprompt', { cancelable: true });
    event.prompt = async () => { prompts++; };
    event.userChoice = Promise.resolve({ outcome });
    act(() => window.dispatchEvent(event));
    assert.equal(event.defaultPrevented, true);
  };
  return { renderer, window, offer, get prompts() { return prompts; }, button: () => renderer.root.findByType('button'), close: () => act(() => renderer.unmount()) };
}

test('unsupported prompt shows manual installation guidance', async () => {
  const c = setup();
  try {
    assert.equal(c.button().children.join(''), 'How to install');
    await act(async () => c.button().props.onClick());
    assert(JSON.stringify(c.renderer.toJSON()).includes('Add to Home Screen'));
    assert.equal(c.prompts, 0);
  } finally { c.close(); }
});
test('browser prompt is invoked once; actual installation hides the control', async () => {
  const c = setup();
  try {
    c.offer('accepted');
    assert.equal(c.button().children.join(''), 'Install app');
    await act(async () => { c.button().props.onClick(); });
    assert.equal(c.prompts, 1);
    assert.equal(c.button().children.join(''), 'How to install');
    act(() => c.window.dispatchEvent(new Event('appinstalled')));
    assert.equal(c.renderer.toJSON(), null);
  } finally { c.close(); }
});
test('dismissed prompts are not reused and a fresh offer enables another attempt', async () => {
  const c = setup();
  try {
    c.offer('dismissed');
    await act(async () => c.button().props.onClick());
    assert(JSON.stringify(c.renderer.toJSON()).includes('Installation cancelled'));
    await act(async () => c.button().props.onClick());
    assert.equal(c.prompts, 1);
    c.offer('accepted');
    await act(async () => c.button().props.onClick());
    assert.equal(c.prompts, 2);
  } finally { c.close(); }
});
test('installation is disabled while check-in is busy', async () => {
  const c = setup({ busy: true });
  try {
    c.offer('accepted');
    assert.equal(c.button().props.disabled, true);
    await act(async () => c.button().props.onClick());
    assert.equal(c.prompts, 0);
  } finally { c.close(); }
});
test('standalone launch hides installation controls', () => {
  const c = setup({ standalone: true });
  try { assert.equal(c.renderer.toJSON(), null); } finally { c.close(); }
});
