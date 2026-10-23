import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { test } from 'node:test';
import vm from 'node:vm';
const require = createRequire(new URL('../module4-observability/package.json', import.meta.url));
const ts = require('typescript');
const source = readFileSync(new URL('../module4-observability/src/lib/attendance.ts', import.meta.url), 'utf8');
const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
function load(request) {
  const context = { exports: {}, require: name => name.endsWith('/api') ? { api: { request } } : { parseApiDateTime: value => new Date(value) } };
  vm.runInNewContext(code, context);
  return context.exports;
}
const session = id => ({ id, course_id: 'c', name: id, course_name: 'Course', course_code: 'SC3099', status: 'scheduled' });
const checkin = (id, session_id) => ({ id, session_id, checked_in_at: '2026-10-22T01:00:00Z', risk_score: 0.1 });
test('instructor refresh paginates check-ins without one request per session', async () => {
  const calls = [];
  const api = load(async path => {
    calls.push(path);
    if (path.startsWith('/sessions/')) return { items: [session('s')] };
    if (path.endsWith('offset=0')) return { items: [checkin('a', 's')], total: 2 };
    return { items: [checkin('b', 's')], total: 2 };
  });
  const rows = await api.fetchCheckIns();
  assert.equal(rows.length, 2);
  assert.equal(rows[0].course_code, 'SC3099');
  assert.equal(calls[0], '/sessions/?limit=100');
  assert.equal(calls.length, 3);
  assert.match(calls[1], /^\/checkins\/\?limit=\d+&offset=0$/);
  assert.match(calls[2], /^\/checkins\/\?limit=\d+&offset=1$/);
});
test('TA loading keeps session-scoped endpoint and caps concurrent requests at two', async () => {
  let active = 0, peak = 0;
  const api = load(async path => {
    active++; peak = Math.max(active, peak);
    await new Promise(resolve => setTimeout(resolve, 2));
    active--;
    const id = path.split('/').at(-1);
    return [checkin(id, id), checkin('unrelated', 'outside')];
  });
  const rows = await api.fetchCheckInsForSessions(Array.from({ length: 8 }, (_, i) => session(String(i))));
  assert.equal(peak, 2);
  assert.equal(rows.length, 8);
});

test('session row retains the exact API risk score on the 0–1 scale', () => {
  const api = load(async () => ({}));
  const [row] = api.toRows([{ ...checkin('a', 's'), risk_score: 0.174389 }]);
  assert.equal(row.riskScore, 0.174389);
});
