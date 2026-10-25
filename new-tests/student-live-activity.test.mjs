import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import vm from "node:vm";
import { test } from "node:test";
const require = createRequire(new URL("../module4-observability/package.json", import.meta.url));
const ts = require("typescript");
const code = ts.transpileModule(readFileSync(new URL("../module4-observability/src/components/dashboard/LiveActivity.tsx", import.meta.url), "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
}).outputText;
const context = { exports: {}, require(name) {
  if (name === "react/jsx-runtime") return require(name);
  return {
    parseApiDateTime: value => new Date(value),
    formatSingaporeDateTime: (value, options) => new Intl.DateTimeFormat("en-US", { ...options, timeZone: "Asia/Singapore" }).format(new Date(value)),
  };
} };
vm.runInNewContext(code, context);
function text(node) {
  if (Array.isArray(node)) return node.map(text).join("");
  if (node && typeof node === "object") return text(node.props?.children);
  return node == null ? "" : String(node);
}
const row = { id: "one", student: "You", course: "SC4000", sessionName: "Lecture 5: Neural Networks", time: "2026-10-23T02:31:00Z", status: "approved" };
test("student messages identify course/session and use appeal submission time", () => {
  const output = text(context.exports.LiveActivity({ student: true, rows: [row, { ...row, id: "two", status: "appealed", appealedAt: "2026-10-23T03:03:00Z" }] }));
  assert.match(output, /You submitted an appeal for SC4000, Lecture 5: Neural Networks11:03 AM/);
  assert.match(output, /You checked in for SC4000, Lecture 5: Neural Networks10:31 AM/);
  assert.ok(output.indexOf("submitted an appeal") < output.indexOf("You checked in"));
  assert.doesNotMatch(output, /You was|SGT/);
});
test("staff activity retains existing subject and metadata", () => {
  assert.match(text(context.exports.LiveActivity({ rows: [{ ...row, student: "Alex" }] })), /Alex checked in10:31 AM SGT · SC4000/);
});
test("rejected appeals show review time and sort before older check-ins", () => {
  const reviewed = { ...row, id: "reviewed", sessionName: "LT1A session", status: "rejected", appealedAt: "2026-10-23T03:03:00Z", reviewedAt: "2026-10-23T04:30:00Z" };
  const output = text(context.exports.LiveActivity({ student: true, rows: [row, reviewed] }));
  assert.match(output, /Your appeal was rejected for SC4000, LT1A session12:30 PM/);
  assert.ok(output.indexOf("Your appeal was rejected") < output.indexOf("You checked in"));
  assert.doesNotMatch(output, /SGT/);
  const originalRejection = text(context.exports.LiveActivity({ student: true, rows: [{ ...row, status: "rejected", reviewedAt: reviewed.reviewedAt }] }));
  assert.match(originalRejection, /Your check-in for/);
  assert.doesNotMatch(originalRejection, /Your appeal/);
});
test("approved appeals show updated verification status and use review time", () => {
  const approved = { ...row, id: "approved-appeal", status: "approved", appealedAt: "2026-10-23T03:03:00Z", reviewedAt: "2026-10-23T04:30:00Z" };
  const output = text(context.exports.LiveActivity({ student: true, rows: [row, approved] }));
  assert.match(output, /Your appeal for SC4000, Lecture 5: Neural Networks was approved\. Verification status updated\.12:30 PM/);
  assert.ok(output.indexOf("Your appeal for") < output.indexOf("You checked in"));
});
