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
  const context = { exports: {}, require: imports, URLSearchParams };
  vm.runInNewContext(code, context);
  return context.exports;
}
const raw = Array.from({ length: 120 }, (_, i) => ({ id: `${i}`, course_id: "course", course_code: "CS", session_id: i < 55 ? "s1" : "s2", session_name: i < 55 ? "Lecture 1" : "Lecture 2", checked_in_at: "2026-10-24T00:00:00Z", status: "approved", risk_score: 0.15 }));
const time = { parseApiDateTime: value => new Date(value), formatSingaporeDateTime: value => value };
function helpers(request) { return load("lib/attendance.ts", name => name.includes("time") ? time : { api: { request } }); }
function elements(node) {
  if (!node || typeof node !== "object") return [];
  if (Array.isArray(node)) return node.flatMap(elements);
  return [node, ...elements(node.props?.children)];
}
function text(node) {
  if (Array.isArray(node)) return node.map(text).join("");
  if (node && typeof node === "object") return text(node.props?.children);
  return node == null ? "" : String(node);
}
test("history client sends scope, offset, cancellation and 50-result pages", async () => {
  const calls = [];
  const api = helpers(async (path, init) => { calls.push([path, init]); return []; });
  const signal = new AbortController().signal;
  await api.fetchMyCheckInsPage("session x", 50, "course y", signal, " Lecture %_ ");
  const params = new URLSearchParams(calls[0][0].split("?")[1]);
  assert.equal(params.get("limit"), "50"); assert.equal(params.get("offset"), "50");
  assert.equal(params.get("session_id"), "session x"); assert.equal(params.get("course_id"), "course y");
  assert.equal(params.get("session_name"), "Lecture %_");
  assert.equal(calls[0][1].signal, signal);
});
test("summary and selector history loads every page of 50 without truncation", async () => {
  const offsets = [];
  const api = helpers(async path => {
    const params = new URLSearchParams(path.split("?")[1]);
    assert.equal(params.get("limit"), "50");
    const offset = Number(params.get("offset")); offsets.push(offset);
    return raw.slice(offset, offset + 50);
  });
  assert.equal((await api.fetchMyCheckIns()).length, 120);
  assert.deepEqual(offsets, [0, 50, 100]);
});
test("table displays session and raw risk; course and session-name search reset pagination", () => {
  const api = helpers(async () => []), values = [];
  let index = 0, query;
  const history = load("components/dashboard/CourseHistory.tsx", name => {
    if (name.includes("useDebouncedValue")) return { useDebouncedValue: value => value };
    if (name === "react/jsx-runtime") return require(name);
    if (name === "react") return { useMemo: fn => fn(), useState(initial) {
      const i = index++; if (!(i in values)) values[i] = initial;
      return [values[i], value => { values[i] = typeof value === "function" ? value(values[i]) : value; }];
    } };
    if (name === "@tanstack/react-query") return { useMutation: () => ({}), useQueryClient: () => ({}), useQuery(options) {
      query = options;
      const [, , course, search, page] = options.queryKey;
      return { data: raw.filter(row => (course === "all" || row.course_id === course) && row.session_name.toLowerCase().includes(search.toLowerCase())).slice(page * 50, (page + 1) * 50) };
    } };
    if (name.includes("attendance")) return api;
    if (name.includes("time")) return time;
    if (name === "@/lib/api") return { ApiError: class extends Error {} };
    if (name.endsWith("/button")) return { Button: "button" };
    return {};
  });
  function render() { index = 0; return history.CourseHistory({ rows: api.toRows(raw) }); }
  const button = (tree, label) => elements(tree).find(node => node.type === "button" && text(node) === label);
  let tree = render();
  const previousPage = raw.slice(0, 50);
  assert.equal(query.placeholderData(previousPage), previousPage);
  assert.equal(query.staleTime, 15000);
  assert.match(text(tree), /Lecture 1/); assert.match(text(tree), /0\.15/);
  assert.doesNotMatch(text(tree), /Room/);
  assert.equal(elements(elements(tree).find(node => node.type === "tbody")).filter(node => node.type === "tr").length, 50);
  button(tree, "Next").props.onClick(); tree = render(); assert.equal(query.queryKey[4], 1);
  elements(tree).find(node => node.type === "select").props.onChange({ target: { value: "course" } });
  tree = render(); assert.equal(query.queryKey[4], 0); assert.equal(query.queryKey[2], "course");
  button(tree, "Next").props.onClick(); tree = render();
  elements(tree).find(node => node.type === "input").props.onChange({ target: { value: "lecture 1" } });
  tree = render(); assert.equal(query.queryKey[4], 0); assert.equal(query.queryKey[3], "lecture 1");
  assert.equal(elements(tree).filter(node => node.type === "select").length, 1);
  button(tree, "Next").props.onClick(); tree = render();
  assert.equal(elements(elements(tree).find(node => node.type === "tbody")).filter(node => node.type === "tr").length, 5);
  assert.equal(button(tree, "Next").props.disabled, true);
});
