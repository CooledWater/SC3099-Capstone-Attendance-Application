import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import vm from "node:vm";
import { test } from "node:test";

const require = createRequire(new URL("../module4-observability/package.json", import.meta.url));
const ts = require("typescript");
function load(path, imports) {
  const code = ts.transpileModule(readFileSync(new URL(`../module4-observability/src/${path}`, import.meta.url), "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  const context = { exports: {}, require: imports };
  vm.runInNewContext(code, context);
  return context.exports;
}
const time = { parseApiDateTime: value => new Date(value), formatSingaporeDateTime: value => value };
const attendance = load("lib/attendance.ts", name => name.includes("time") ? time : {});
const Button = "test-button";
let historyRows = [];
const history = load("components/dashboard/CourseHistory.tsx", name => {
  if (name === "react") return { useMemo: fn => fn(), useState: value => [value, () => {}] };
  if (name.includes("useDebouncedValue")) return { useDebouncedValue: value => value };
  if (name === "react/jsx-runtime") return require(name);
  if (name === "@tanstack/react-query") return { useQuery: () => ({ data: historyRows }), useQueryClient: () => ({}), useMutation: () => ({}) };
  if (name === "@/lib/api") return { ApiError: class extends Error {} };
  if (name.includes("time")) return time;
  if (name.includes("attendance")) return attendance;
  if (name.endsWith("/button")) return { Button };
  return {};
});
function elements(node) {
  if (!node || typeof node !== "object") return [];
  if (Array.isArray(node)) return node.flatMap(elements);
  return [node, ...elements(node.props?.children)];
}
function appealVisible(status, appealed_at, ageDays = 1) {
  historyRows = [{
    id: "checkin", session_id: "session", course_code: "CS", risk_score: 0,
    status, appealed_at, checked_in_at: new Date(Date.now() - ageDays * 86400000).toISOString(),
  }];
  const rows = attendance.toRows(historyRows);
  return elements(history.CourseHistory({ rows })).some(node => node.type === Button && node.props.children === "Appeal");
}
test("first flagged/rejected check-ins can be appealed within seven days", () => {
  assert.equal(appealVisible("flagged", null), true);
  assert.equal(appealVisible("rejected", null), true);
});
test("a rejected appeal stays ineligible after review and history reload", () => {
  const priorAppeal = new Date(Date.now() - 3600000).toISOString();
  assert.equal(appealVisible("rejected", priorAppeal), false);
  assert.equal(appealVisible("flagged", priorAppeal), false);
});
test("other statuses and expired records remain ineligible", () => {
  for (const status of ["approved", "pending", "appealed"]) assert.equal(appealVisible(status, null), false);
  assert.equal(appealVisible("rejected", null, 8), false);
});
