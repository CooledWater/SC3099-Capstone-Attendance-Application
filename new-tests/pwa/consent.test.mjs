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
const source = readFileSync(new URL('../../module1-frontend/components/PermissionSettings.tsx', import.meta.url), 'utf8');
function mount(fail = false) {
  const calls = [];
  const user = { id: 'student', role: 'student', camera_consent: true, geolocation_consent: true };
  const context = { Error, exports: {}, require: name => {
    if (name === './DataDeletionSettings') return { DataDeletionSettings: () => null };
    if (name === './PushNotifications') return { PushNotifications: () => React.createElement('div', { 'data-notification-controls': true }, 'Notification controls') };
    if (name === 'react') return React;
    if (name === 'react/jsx-runtime') return dependencies(name);
    if (name === '@/lib/api/auth') return { updateConsent: async (camera, location) => { calls.push([camera, location]); if (fail) throw new Error('Save failed'); return { ...user, camera_consent: camera, geolocation_consent: location }; } };
    throw new Error(name);
  } };
  vm.runInNewContext(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX } }).outputText, context);
  let current = user;
  function App() { const [account, setAccount] = React.useState(current); return React.createElement(context.exports.PermissionSettings, { user: account, demo: false, onChange: next => { current = next; setAccount(next); } }); }
  let renderer;
  act(() => { renderer = create(React.createElement(App)); });
  act(() => renderer.root.findAllByType('button')[0].props.onClick());
  return { renderer, calls, get user() { return current; } };
}
for (const permission of ['camera', 'location']) test(`saved ${permission} consent restores and disabling preserves the other choice`, async () => {
  const app = mount();
  act(() => app.renderer.root.findAllByType('button')[permission === 'camera' ? 1 : 2].props.onClick());
  let toggle = app.renderer.root.findByProps({ role: 'switch' });
  assert.equal(toggle.props['aria-checked'], true);
  await act(async () => toggle.props.onClick());
  assert.equal(app.renderer.root.findByProps({ role: 'switch' }).props['aria-checked'], false);
  assert.deepEqual(app.calls, [permission === 'camera' ? [false, true] : [true, false]]);
  assert.equal(app.user[permission === 'camera' ? 'geolocation_consent' : 'camera_consent'], true);
  act(() => app.renderer.unmount());
});
test('failed save reports an error without claiming permission changed', async () => {
  const app = mount(true);
  act(() => app.renderer.root.findAllByType('button')[1].props.onClick());
  await act(async () => app.renderer.root.findByProps({ role: 'switch' }).props.onClick());
  assert.equal(app.renderer.root.findByProps({ role: 'switch' }).props['aria-checked'], true);
  assert.equal(app.renderer.root.findByProps({ role: 'alert' }).children[0], 'Save failed');
  act(() => app.renderer.unmount());
});

test('check-in restores saved consent and blocks collection after consent is withdrawn', async () => {
  let starts = 0;
  let stops = 0;
  const stop = () => { stops++; };
  const reset = () => {};
  const camera = { state: 'idle', permissionState: 'granted', stop, start: () => { starts++; } };
  const geo = { state: 'idle', permissionState: 'granted', reset, request: () => {} };
  const context = { exports: {}, Date, navigator: { onLine: true }, window: { addEventListener() {}, removeEventListener() {} }, require: name => {
    if (name === './DataDeletionSettings') return { DataDeletionSettings: () => null };
    if (name === './PushNotifications') return { PushNotifications: () => React.createElement('div', { 'data-notification-controls': true }, 'Notification controls') };
    if (name === 'react') return React;
    if (name === 'react/jsx-runtime') return dependencies(name);
    if (name.endsWith('useCamera')) return { useCamera: () => camera };
    if (name.endsWith('useGeolocation')) return { useGeolocation: () => geo };
    if (name === '@/lib/time') return { formatSingaporeDateTime: () => '12:00', singaporeGreeting: () => 'morning' };
    if (name === '@/lib/api/client') return {};
    return new Proxy({}, { get: () => () => null });
  } };
  const source = readFileSync(new URL('../../module1-frontend/components/check-in/StudentDashboard.tsx', import.meta.url), 'utf8');
  vm.runInNewContext(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX } }).outputText, context);
  const props = { user: { id: 'student', full_name: 'Alex Tan', camera_consent: true, geolocation_consent: true }, demo: true, profileOpen: false, onBusyChange() {}, onOpenProfile() {}, onLogout() {} };
  let renderer;
  await act(async () => { renderer = create(React.createElement(context.exports.StudentDashboard, props)); });
  const button = renderer.root.findAllByType('button').find(item => item.children.includes('Start camera'));
  assert.ok(button);
  act(() => button.props.onClick());
  assert.equal(starts, 1);
  await act(async () => { renderer.update(React.createElement(context.exports.StudentDashboard, { ...props, user: { ...props.user, camera_consent: false } })); });
  assert.ok(stops > 0);
  assert.ok(renderer.root.findAllByType('h2').some(item => item.children.includes('Permission required')));
  assert.ok(!renderer.root.findAllByType('button').some(item => item.children.includes('Start camera')));
  act(() => renderer.unmount());
});

test('notification controls open under Settings and Back restores permission rows', () => {
  const app = mount();
  const panel = () => app.renderer.root.findByProps({ 'data-notification-controls': true }).parent.parent;
  assert.equal(panel().props.hidden, true);
  const row = app.renderer.root.findAllByType('button').find(button => button.findAllByType('span').some(span => span.children.includes('Attendance notifications')));
  act(() => row.props.onClick());
  assert.equal(panel().props.hidden, false);
  assert.equal(app.renderer.root.findByType('h2').children.join(''), 'Attendance notifications');
  act(() => app.renderer.root.findByProps({ 'aria-label': 'Back to settings' }).props.onClick());
  assert.equal(panel().props.hidden, true);
  assert.equal(app.renderer.root.findByType('h2').children.join(''), 'Settings');
  act(() => app.renderer.unmount());
});
