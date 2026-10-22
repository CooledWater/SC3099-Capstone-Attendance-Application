import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { test } from 'node:test';
import vm from 'node:vm';
const ts = createRequire(new URL('../module1-frontend/package.json', import.meta.url))('typescript');
const code = ts.transpileModule(readFileSync(new URL('../module1-frontend/components/check-in/StudentDashboard.tsx', import.meta.url), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
}).outputText;
const session = id => ({ id, name: id, scheduled_start: '2026-10-23T01:00:00Z', checkin_closes_at: '2026-10-23T03:00:00Z' });
function setup(lookup) {
  const slots = [], deps = []; let cursor = 0, effects = [], tree, starts = 0;
  const stop = () => {}, reset = () => {};
  const props = { user: { id: 'student', full_name: 'Student', email: 's@example.test' }, demo: false, onLogout() {}, onBusyChange() {}, onOpenProfile() {} };
  const react = {
    useState(initial) { const i = cursor++; if (!(i in slots)) slots[i] = typeof initial === 'function' ? initial() : initial; return [slots[i], value => { slots[i] = typeof value === 'function' ? value(slots[i]) : value; }]; },
    useReducer(reducer, initial) { const [value, set] = this.useState(initial); return [value, action => set(previous => reducer(previous, action))]; },
    useEffect(effect, values) { const i = cursor++; if (!deps[i] || values.some((value, index) => value !== deps[i][index])) { effects.push(effect); deps[i] = values; } },
  };
  react.useReducer = react.useReducer.bind(react);
  const imports = {
    react,
    'react/jsx-runtime': { jsx: (type, props) => ({ type, props }), jsxs: (type, props) => ({ type, props }), Fragment: 'fragment' },
    '@/lib/time': { formatSingaporeDateTime: value => value, singaporeGreeting: () => 'morning' },
    '@/features/camera/useCamera': { useCamera: () => ({ state: 'idle', stop, start() { starts++; } }) },
    '@/features/geolocation/useGeolocation': { useGeolocation: () => ({ state: 'idle', reset }) },
    '@/lib/api/checkins': { getActiveSessions: async () => [session('one'), session('two')], getMySessionCheckIn: lookup },
    '@/lib/api/client': { ApiError: class extends Error {}, isConnectivityError: () => false },
    '@/lib/offline/sessionCache': { cacheActiveSessions: async () => {} },
  };
  const context = { exports: {}, require: name => imports[name] ?? {}, navigator: { onLine: true }, window: { addEventListener() {}, removeEventListener() {} } };
  vm.runInNewContext(code, context);
  function render() { cursor = 0; tree = context.exports.StudentDashboard(props); const queue = effects; effects = []; queue.forEach(effect => effect()); return tree; }
  async function settle() { for (let i = 0; i < 8; i++) { render(); await new Promise(resolve => setImmediate(resolve)); } return tree; }
  const text = () => JSON.stringify(tree);
  function find(node, type) { if (!node || typeof node !== 'object') return; if (node.type === type) return node; const children = node.props?.children; for (const child of [children].flat(Infinity)) { const match = find(child, type); if (match) return match; } }
  return { render, settle, text, find: type => find(tree, type), get starts() { return starts; } };
}
for (const [status, label] of [['approved', 'Attendance confirmed'], ['flagged', 'Submitted for review'], ['pending', 'Verification pending'], ['rejected', 'Check-in rejected'], ['appealed', 'Appeal submitted']]) {
  test(`refresh restores ${status} record without showing camera steps`, async () => {
    const c = setup(async id => ({ id: 'record', session_id: id, status, checked_in_at: '2026-10-23T01:00:00Z', risk_score: 0.1 }));
    c.render(); assert.ok(!c.text().includes('Allow camera access'));
    await c.settle(); assert.ok(c.text().includes(label)); assert.ok(!c.text().includes('Allow camera access')); assert.equal(c.starts, 0);
    c.find('select').props.onChange({ target: { value: 'two' } }); c.render();
    assert.ok(c.text().includes('Checking your attendance'));
  });
}
test('no existing record enables verification; lookup errors offer retry instead', async () => {
  const fresh = setup(async () => undefined); await fresh.settle(); assert.ok(fresh.text().includes('Allow camera access'));
  const failed = setup(async () => { throw new Error('Unavailable'); }); await failed.settle();
  assert.ok(failed.text().includes('Retry attendance check')); assert.ok(!failed.text().includes('Allow camera access'));
});
