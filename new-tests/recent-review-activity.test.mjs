import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import vm from "node:vm";
import { test } from "node:test";

const require = createRequire(new URL("../module4-observability/package.json", import.meta.url));
const ts = require("typescript"), jsx = require("react/jsx-runtime");
const source = readFileSync(new URL("../module4-observability/src/components/dashboard/RecentReviewActivity.tsx", import.meta.url), "utf8");
const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX } }).outputText;
const context = { exports: {}, require(name) {
  if (name === "react/jsx-runtime") return jsx;
  if (name === "lucide-react") return { Check: "CheckIcon", X: "RejectIcon" };
  if (name.endsWith("/badge")) return { Badge: "Badge" };
  if (name.endsWith("/skeleton")) return { Skeleton: "Skeleton" };
  if (name.endsWith("/time")) return { parseApiDateTime: value => new Date(/(?:Z|[+-]\d{2}:\d{2})$/i.test(value) ? value : `${value}Z`) };
  throw new Error(name);
} };
vm.runInNewContext(code, context);
function elements(node) {
  if (!node || typeof node !== "object") return [];
  if (Array.isArray(node)) return node.flatMap(elements);
  return [node, ...elements(node.props?.children)];
}
function text(node) {
  if (Array.isArray(node)) return node.map(text).join("");
  return node && typeof node === "object" ? text(node.props?.children) : node == null ? "" : String(node);
}
const event = (id, timestamp, decision = "approved", extra = {}) => ({ id, session_id: "session", session_name: "capstone", action: "checkin_reviewed", decision, timestamp, previous_status: "flagged", ...extra });
const render = (props = {}) => context.exports.RecentReviewActivity({ sessionId: "session", sessionName: "capstone", courseCode: "SC4000", events: [], loading: false, error: false, onRetry() {}, ...props });

test("compact real-event rows show decision, optional supplied student, exact local time and course badge", () => {
  const tree = render({ events: [event("a", "2026-10-28T15:17:00Z"), event("b", "2026-10-28T15:18:00Z", "rejected", { student_name: "Aisha Tan" })] });
  const rows = elements(tree).filter(node => node.type === "li");
  assert.deepEqual(rows.map(row => row.key), ["b", "a"]);
  assert.match(text(tree), /capstone · 2 reviews shown/);
  assert.match(text(rows[0]), /Check-in rejected · Aisha Tan/);
  assert.match(text(rows[1]), /28 Oct · 11:17 pm SGT/);
  assert.equal(elements(rows[0]).some(node => node.type === "RejectIcon"), true);
  assert.equal(elements(rows[1]).some(node => node.type === "CheckIcon"), true);
  assert.equal(elements(tree).filter(node => node.type === "Badge").map(text).join(","), "SC4000,Rejected,Approved");
  assert.equal(elements(tree).some(node => node.type === "a" || node.type === "button"), false);
  assert.equal(elements(rows[1]).find(node => node.type === "time").props.dateTime, "2026-10-28T15:17:00Z");
});

test("sorts a copy, shows only five latest authorised-session manual events and labels count shown", () => {
  const events = Array.from({ length: 7 }, (_, i) => event(`e${i}`, `2026-10-28T15:${String(i).padStart(2, "0")}:00Z`));
  events.push(event("other-session", "2026-10-28T15:59:00Z", "approved", { session_id: "other" }));
  events.push(event("automatic", "2026-10-28T15:58:00Z", "approved", { action: "checkin_approved" }));
  const before = events.map(row => row.id);
  const tree = render({ events });
  assert.deepEqual(elements(tree).filter(node => node.type === "li").map(row => row.key), ["e6", "e5", "e4", "e3", "e2"]);
  assert.deepEqual(events.map(row => row.id), before);
  assert.match(text(tree), /5 reviews shown/);
  assert.equal(text(tree).includes("View all"), false);
});

test("loading, error retry, empty and changed-session states never display cached event rows", () => {
  const events = [event("old", "2026-10-28T15:17:00Z")];
  const loading = render({ events, loading: true });
  assert.equal(elements(loading).filter(node => node.type === "li").length, 0);
  assert.ok(elements(loading).some(node => node.props?.role === "status"));
  assert.equal(text(loading).includes("reviews shown"), false);
  let retried = 0;
  const error = render({ events, error: true, onRetry() { retried++; } });
  assert.equal(elements(error).filter(node => node.type === "li").length, 0);
  assert.match(text(error), /Could not load review activity/);
  elements(error).find(node => node.type === "button").props.onClick();
  assert.equal(retried, 1);
  const empty = render({ sessionId: "new-session", events });
  assert.match(text(empty), /No review activity yet/);
  assert.match(text(empty), /0 reviews shown/);
});

test("timestamps honour the application timezone and valid midnight values", () => {
  const tree = render({ timeZone: "UTC", events: [event("a", "2026-10-28T00:00:00Z")] });
  assert.match(text(tree), /28 Oct · 12:00 am UTC/);
  const singular = render({ events: [event("a", "2026-10-28T15:17:00")] });
  assert.match(text(singular), /1 review shown/);
  assert.match(text(singular), /11:17 pm SGT/);
});
