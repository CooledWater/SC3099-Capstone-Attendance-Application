import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import vm from "node:vm";
import { test } from "node:test";
const require = createRequire(new URL("../module4-observability/package.json", import.meta.url));
const ts = require("typescript");
const source = readFileSync(new URL("../module4-observability/src/components/dashboard/StudentView.tsx", import.meta.url), "utf8");
const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX } }).outputText;
function render(enrollmentResult) {
  const calls = [];
  const context = { exports: {}, require(name) {
    if (name === "react") return { useMemo: fn => fn(), useState: value => [value, () => {}] };
    if (name === "react/jsx-runtime") return require(name);
    if (name === "@tanstack/react-query") return { useQuery(options) { calls.push(options.queryKey[0]); return options.queryKey[0] === "my-enrollments" ? enrollmentResult : { data: [] }; } };
    if (name.includes("attendance")) return { toRows: rows => rows };
    if (name.includes("time")) return { formatSingaporeDateTime: value => value };
    return {};
  } };
  vm.runInNewContext(code, context);
  return { tree: context.exports.StudentView(), calls };
}
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
test("all current enrollments appear even without check-ins; open sessions are not fetched", () => {
  const data = Array.from({ length: 105 }, (_, i) => ({ course_id: `${i}`, course_code: `CS${i}`, course_name: `Course ${i}`, semester: "Semester 1", instructor_name: "Dr Tan", enrolled_at: "2026-10-01T00:00:00Z" }));
  const { tree, calls } = render({ data });
  assert.deepEqual(calls, ["my-check-ins", "my-enrollments"]);
  const body = elements(tree).find(node => node.type === "tbody");
  assert.equal(elements(body).filter(node => node.type === "tr").length, 105);
  assert.match(text(tree), /CS104Course 104Semester 1Dr Tan/);
  assert.doesNotMatch(text(tree), /Open sessions/);
});
test("loading, empty and retry states remain distinct", () => {
  assert.match(text(render({ isPending: true }).tree), /Loading your course enrollments/);
  assert.match(text(render({ data: [] }).tree), /not currently enrolled/);
  let retried = false;
  const { tree } = render({ isError: true, refetch() { retried = true; } });
  const retry = elements(tree).find(node => node.type === "button" && text(node) === "Retry");
  retry.props.onClick();
  assert.equal(retried, true);
  assert.doesNotMatch(text(tree), /not currently enrolled/);
});
