import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import vm from "node:vm";
import { test } from "node:test";

const require = createRequire(new URL("../module4-observability/package.json", import.meta.url));
const ts = require("typescript");
const source = readFileSync(new URL("../module4-observability/src/components/dashboard/AttendanceTable.tsx", import.meta.url), "utf8");
const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX } }).outputText;

function harness() {
  const state = []; let index = 0; let exported;
  const context = { exports: {}, require(name) {
    if (name === "react") return { useMemo: fn => fn(), useState(initial) { const i = index++; if (!(i in state)) state[i] = initial; return [state[i], value => { state[i] = typeof value === "function" ? value(state[i]) : value; }]; } };
    if (name === "react/jsx-runtime") return require(name);
    if (name.endsWith("/checkin-roster")) return {};
    if (name.includes("attendance")) return { statusText: { approved: "Approved", rejected: "Rejected", flagged: "Flagged", pending: "Pending", appealed: "Appealed" }, checkInsToCsv: rows => rows, downloadCsv: (name, rows) => { exported = rows; } };
    if (name.includes("time")) return { formatSingaporeDateTime: value => value };
    throw new Error(name);
  } };
  vm.runInNewContext(code, context);
  function render(rows, loading = false) { index = 0; return context.exports.AttendanceTable({ rows, loading }); }
  function elements(node) { if (!node || typeof node !== "object") return []; if (Array.isArray(node)) return node.flatMap(elements); return [node, ...elements(node.props?.children)]; }
  function text(node) { if (Array.isArray(node)) return node.map(text).join(""); if (node && typeof node === "object") return text(node.props?.children); return node == null ? "" : String(node); }
  function button(tree, label) { return elements(tree).find(e => e.type === "button" && text(e) === label); }
  function count(tree) { const body = elements(tree).find(e => e.type === "tbody"); return elements(body).filter(e => e.type === "tr").length; }
  return { render, text, button, count, exported: () => exported };
}
const rows = Array.from({ length: 120 }, (_, i) => ({ id: String(i), student: `Student ${i}`, email: `${i}@example.edu`, course: "CS", room: "R", time: new Date(2026, 0, 1, 0, i).toISOString(), status: i < 15 ? "flagged" : "approved", risk: i }));

test("50 rows per page with correct last-page counts and navigation boundaries", () => {
  const h = harness(); let tree = h.render(rows);
  assert.equal(h.count(tree), 50); assert.equal(h.button(tree, "Previous").props.disabled, true);
  assert.match(h.text(tree), /Showing 1–50 of 120 records/);
  h.button(tree, "Next").props.onClick(); tree = h.render(rows);
  assert.match(h.text(tree), /Showing 51–100 of 120 records/);
  h.button(tree, "Next").props.onClick(); tree = h.render(rows);
  assert.equal(h.count(tree), 20); assert.equal(h.button(tree, "Next").props.disabled, true);
  h.button(tree, "Previous").props.onClick(); assert.equal(h.count(h.render(rows)), 50);
});

test("filter/sort resets pagination and CSV includes all matching rows", () => {
  const h = harness(); let tree = h.render(rows);
  h.button(tree, "Next").props.onClick(); tree = h.render(rows);
  h.button(tree, "Flagged").props.onClick(); tree = h.render(rows);
  assert.equal(h.count(tree), 15); assert.match(h.text(tree), /Showing 1–15 of 15/);
  h.button(tree, "All").props.onClick(); tree = h.render(rows);
  h.button(tree, "Export CSV").props.onClick(); assert.equal(h.exported().length, 120);
  h.button(tree, "Next").props.onClick(); tree = h.render(rows);
  const sort = h.button(tree, "Student ↕"); sort.props.onClick(); tree = h.render(rows);
  assert.match(h.text(tree), /Page 1 of 3/);
});

test("empty, loading and shrinking results keep navigation valid", () => {
  const h = harness(); let tree = h.render(rows);
  h.button(tree, "Next").props.onClick(); tree = h.render(rows);
  h.button(tree, "Next").props.onClick(); tree = h.render(rows.slice(0, 10));
  assert.match(h.text(tree), /Showing 1–10 of 10/);
  tree = h.render([]); assert.match(h.text(tree), /Showing 0–0 of 0/);
  assert.equal(h.button(tree, "Next").props.disabled, true);
  tree = h.render(rows, true); assert.equal(h.button(tree, "Previous").props.disabled, true);
  assert.equal(h.button(tree, "Next").props.disabled, true);
});
