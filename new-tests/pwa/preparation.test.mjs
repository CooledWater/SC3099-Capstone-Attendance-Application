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
const source = readFileSync(new URL('../../module1-frontend/components/check-in/StudentDashboard.tsx', import.meta.url), 'utf8');
const javascript = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX } }).outputText;
function mount(permission = 'granted') {
  const requests = { camera: [], location: [] };
  function useCamera() {
    const [state, setState] = React.useState('idle');
    const epoch = React.useRef(0);
    const videoRef = React.useRef(null);
    const stop = React.useCallback(() => { epoch.current++; setState('idle'); }, []);
    const start = React.useCallback(() => {
      const id = ++epoch.current;
      setState('requesting');
      requests.camera.push(next => { if (id === epoch.current) setState(next); });
    }, []);
    return { state, permissionState: permission, videoRef, start, stop, capture() {} };
  }
  function useGeolocation() {
    const [state, setState] = React.useState('idle');
    const [point, setPoint] = React.useState();
    const epoch = React.useRef(0);
    const reset = React.useCallback(() => { epoch.current++; setPoint(undefined); setState('idle'); }, []);
    const request = React.useCallback(() => {
      const id = ++epoch.current;
      setPoint(undefined); setState('requesting');
      requests.location.push(next => {
        if (id !== epoch.current) return;
        setState(next);
        if (next === 'ready') setPoint({ latitude: 1.3, longitude: 103.8, accuracy: 10 });
      });
    }, []);
    return { state, point, permissionState: permission, reset, request };
  }
  const context = { exports: {}, Date, navigator: { onLine: true }, window: { addEventListener() {}, removeEventListener() {} }, require: name => {
    if (name === 'react') return React;
    if (name === 'react/jsx-runtime') return dependencies(name);
    if (name.endsWith('useCamera')) return { useCamera };
    if (name.endsWith('useGeolocation')) return { useGeolocation };
    if (name === './FaceVerification') return { FaceVerification: () => React.createElement('p', { 'data-test': 'liveness' }, 'Liveness stage') };
    if (name === '@/lib/time') return { formatSingaporeDateTime: () => '12:00', singaporeGreeting: () => 'morning' };
    return new Proxy({}, { get: () => () => null });
  } };
  vm.runInNewContext(javascript, context);
  const props = { user: { id: 'student', full_name: 'Alex Tan', camera_consent: true, geolocation_consent: true }, demo: true, profileOpen: false, onBusyChange() {}, onOpenProfile() {}, onLogout() {} };
  let renderer;
  act(() => { renderer = create(React.createElement(context.exports.StudentDashboard, props)); });
  const click = text => act(() => renderer.root.findAllByType('button').find(item => item.children.includes(text)).props.onClick());
  return { renderer, requests, click,
    camera: state => act(() => requests.camera.at(-1)(state)),
    location: state => act(() => requests.location.at(-1)(state)),
    liveness: () => renderer.root.findAllByProps({ 'data-test': 'liveness' }).length > 0,
    update: changes => act(() => renderer.update(React.createElement(context.exports.StudentDashboard, { ...props, ...changes }))),
    unmount: () => act(() => renderer.unmount()),
  };
}
for (const permission of ['granted', 'unsupported']) test(`one action prepares both inputs with ${permission} permission queries`, () => {
  const app = mount(permission);
  try {
    app.click('Proceed to check in');
    assert.equal(app.requests.camera.length, 1);
    assert.equal(app.requests.location.length, 1);
    app.camera('ready');
    assert.equal(app.liveness(), false, 'camera alone must not advance');
    app.location('ready');
    assert.equal(app.liveness(), true);
    assert.ok(!JSON.stringify(app.renderer.toJSON()).includes('Confirm your location'));
  } finally { app.unmount(); }
});
test('location failure stays in preparation and can retry without skipping fresh capture', () => {
  const app = mount();
  try {
    app.click('Proceed to check in'); app.camera('ready'); app.location('timeout');
    assert.equal(app.liveness(), false);
    assert.ok(JSON.stringify(app.renderer.toJSON()).includes('Location timed out'));
    app.click('Retry preparation');
    assert.equal(app.requests.camera.length, 2);
    assert.equal(app.requests.location.length, 2);
    app.location('ready');
    assert.equal(app.liveness(), false);
    app.camera('ready'); assert.equal(app.liveness(), true);
  } finally { app.unmount(); }
});
test('camera denial never advances even when location succeeds', () => {
  const app = mount();
  try {
    app.click('Proceed to check in'); app.location('ready'); app.camera('denied');
    assert.equal(app.liveness(), false);
    assert.ok(JSON.stringify(app.renderer.toJSON()).includes('Camera access is blocked'));
  } finally { app.unmount(); }
});
test('cancel invalidates preparation and late callbacks do not advance', () => {
  const app = mount();
  try {
    app.click('Proceed to check in'); app.click('Cancel');
    app.camera('ready'); app.location('ready');
    assert.equal(app.liveness(), false);
    assert.ok(JSON.stringify(app.renderer.toJSON()).includes('Proceed to check in'));
  } finally { app.unmount(); }
});
test('opening Profile cancels preparation', () => {
  const app = mount();
  try {
    app.click('Proceed to check in');
    app.update({ profileOpen: true });
    app.camera('ready'); app.location('ready');
    assert.equal(app.liveness(), false);
  } finally { app.unmount(); }
});
