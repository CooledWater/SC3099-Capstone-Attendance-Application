import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import vm from "node:vm";
import { test } from "node:test";
const require = createRequire(new URL("../module4-observability/package.json", import.meta.url));
const ts = require("typescript");
test("rapid typing settles only the final search and unmount cancels pending updates", () => {
  let settled = "", cleanup, timer, updates = 0;
  const code = ts.transpileModule(readFileSync(new URL("../module4-observability/src/hooks/useDebouncedValue.ts", import.meta.url), "utf8"), { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
  const context = { exports: {}, setTimeout(fn, delay) { assert.equal(delay, 300); timer = fn; return fn; }, clearTimeout(fn) { if (timer === fn) timer = null; }, require: () => ({
    useState: () => [settled, value => { settled = value; updates++; }],
    useEffect(fn) { cleanup?.(); cleanup = fn(); },
  }) };
  vm.runInNewContext(code, context);
  for (const value of ["l", "le", "lec", "lecture"]) assert.equal(context.exports.useDebouncedValue(value), "");
  assert.equal(updates, 0);
  timer(); assert.equal(settled, "lecture"); assert.equal(updates, 1);
  context.exports.useDebouncedValue("different"); cleanup(); assert.equal(timer, null);
});
