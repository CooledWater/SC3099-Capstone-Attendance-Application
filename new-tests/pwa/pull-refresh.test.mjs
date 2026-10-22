import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { test } from 'node:test';
import vm from 'node:vm';
const ts = createRequire(new URL('../../module1-frontend/package.json', import.meta.url))('typescript');
const source = readFileSync(new URL('../../module1-frontend/components/PullToRefresh.tsx', import.meta.url), 'utf8');
const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX } }).outputText;
function setup(busy = false) {
  const handlers = new Map(); let reloads = 0, cleanup;
  const react = { useState: value => [value, () => {}], useRef: value => ({ current: value }), useEffect: effect => { cleanup = effect(); } };
  const context = { exports: {}, Element: class {}, getComputedStyle: () => ({ overflowY: 'visible' }),
    document: { documentElement: { classList: { add() {}, remove() {} } }, addEventListener: (name, fn) => handlers.set(name, fn), removeEventListener: name => handlers.delete(name) },
    window: { scrollY: 0, location: { reload: () => reloads++ } },
    require: name => name === 'react' ? react : { jsx: (type, props) => ({ type, props }), jsxs: (type, props) => ({ type, props }) },
  };
  vm.runInNewContext(code, context);
  const tree = context.exports.PwaRefreshControls({ busy });
  const send = (name, x, y, count = 1) => handlers.get(name)({ touches: Array.from({ length: count }, () => ({ clientX: x, clientY: y })), cancelable: true, preventDefault() {} });
  return { send, context, tree, handlers, cleanup: () => cleanup(), get reloads() { return reloads; } };
}
test('downward pull refreshes once only after release at the top', () => {
  const c = setup(); c.send('touchstart', 0, 0); c.send('touchmove', 0, 120);
  assert.equal(c.reloads, 0); c.send('touchend'); c.send('touchend'); assert.equal(c.reloads, 1);
  c.cleanup(); assert.equal(c.handlers.size, 0);
});
test('short, horizontal, cancelled and multitouch gestures do not refresh', () => {
  for (const [x, y, cancel, count] of [[0, 50, false, 1], [200, 110, false, 1], [0, 120, true, 1], [0, 120, false, 2]]) {
    const c = setup(); c.send('touchstart', 0, 0); c.send('touchmove', x, y, count);
    c.send(cancel ? 'touchcancel' : 'touchend'); assert.equal(c.reloads, 0);
  }
});
test('busy state blocks gesture; scrolling blocks gesture', () => {
  const c = setup(true); c.send('touchstart', 0, 0); c.send('touchmove', 0, 120); c.send('touchend');
  assert.equal(c.tree, null); assert.equal(c.reloads, 0);
  const scrolled = setup(); scrolled.context.window.scrollY = 20;
  scrolled.send('touchstart', 0, 0); scrolled.send('touchmove', 0, 120); scrolled.send('touchend'); assert.equal(scrolled.reloads, 0);
});

for (const mode of ['browser', 'standalone', 'ios']) {
  test(`refresh controls are restricted to installed PWA: ${mode}`, () => {
    let state = false;
    let effect;
    const context = { exports: {}, navigator: { standalone: mode === 'ios' },
      window: { matchMedia: () => ({ matches: mode === 'standalone', addEventListener() {}, removeEventListener() {} }) },
      require: name => name === 'react' ? {
        useState: () => [state, value => { state = value; }], useEffect: fn => { effect = fn; },
      } : { jsx: (type, props) => ({ type, props }) },
    };
    vm.runInNewContext(code, context);
    assert.equal(context.exports.PullToRefresh({ busy: false }), null);
    const cleanup = effect();
    const rendered = context.exports.PullToRefresh({ busy: false });
    assert.equal(rendered !== null, mode !== 'browser');
    cleanup();
  });
}
