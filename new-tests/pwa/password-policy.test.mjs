import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { test } from 'node:test';
import vm from 'node:vm';
const frontend = createRequire(new URL('../../module1-frontend/package.json', import.meta.url));
const dependencies = createRequire(`${process.env.PWA_TEST_DEPENDENCIES ?? '/private/tmp/saiv-pwa-tests'}/package.json`);
const ts = frontend('typescript');
const React = dependencies('react');
const { create, act } = dependencies('react-test-renderer');
function loadPolicy(path) {
  const context = { exports: {}, TextEncoder };
  vm.runInNewContext(ts.transpileModule(readFileSync(new URL(path, import.meta.url), 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText, context);
  return context.exports;
}
for (const path of ['../../module1-frontend/lib/password-policy.ts', '../../module4-observability/src/lib/password-policy.ts']) test(`${path}: consistent new-password rules`, () => {
  const { newPasswordError } = loadPolicy(path);
  for (const password of ['shortA!', 'Aa!' + 'é'.repeat(35)]) assert.ok(newPasswordError(password));
  for (const password of ['Password!', 'StrongPass#123', 'Abcdefg!', 'lowercase123', '12345678', 'Password123']) assert.equal(newPasswordError(password), '');
});
test('login has no demo entry and weak registration is blocked before API submission', async () => {
  let registrations = 0;
  const context = { exports: {}, Error, process: { env: {} }, require: name => {
    if (name === 'react') return React;
    if (name === 'react/jsx-runtime') return dependencies(name);
    if (name === '@/lib/password-policy') return loadPolicy('../../module1-frontend/lib/password-policy.ts');
    if (name === '@/components/AppLogo') return { AppLogo: () => null };
    if (name === '@/lib/api/auth') return { register: async () => { registrations++; }, login: async () => ({}) };
    throw new Error(name);
  } };
  vm.runInNewContext(ts.transpileModule(readFileSync(new URL('../../module1-frontend/components/auth/AuthCard.tsx', import.meta.url), 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX } }).outputText, context);
  let renderer;
  act(() => { renderer = create(React.createElement(context.exports.AuthCard, { onAuthenticated() {} })); });
  assert.ok(!JSON.stringify(renderer.toJSON()).toLowerCase().includes('demo'));
  act(() => renderer.root.findAllByProps({ role: 'tab' })[1].props.onClick());
  act(() => renderer.root.findByProps({ type: 'password' }).props.onChange({ target: { value: 'short' } }));
  await act(async () => renderer.root.findByType('form').props.onSubmit({ preventDefault() {} }));
  assert.equal(registrations, 0);
  assert.ok(JSON.stringify(renderer.toJSON()).includes('8 characters'));
  act(() => renderer.root.findByProps({ type: 'password' }).props.onChange({ target: { value: 'ValidPass!' } }));
  await act(async () => renderer.root.findByType('form').props.onSubmit({ preventDefault() {} }));
  assert.equal(registrations, 1);
  act(() => renderer.unmount());
});
