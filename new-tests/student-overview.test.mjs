import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import vm from "node:vm";
import { test } from "node:test";
const require = createRequire(new URL("../module4-observability/package.json", import.meta.url));
const ts = require("typescript");
function load(path, imports) {
  const code = ts.transpileModule(readFileSync(new URL(`../module4-observability/src/${path}`, import.meta.url), "utf8"), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX } }).outputText;
  const ctx = { exports: {}, require: imports, URLSearchParams };
  vm.runInNewContext(code, ctx); return ctx.exports;
}
function elements(node) {
  if (!node || typeof node !== "object") return [];
  if (Array.isArray(node)) return node.flatMap(elements);
  if (typeof node.type === "function") return elements(node.type(node.props));
  return [node, ...elements(node.props?.children)];
}
function text(node) {
  if (Array.isArray(node)) return node.map(text).join("");
  if (node && typeof node === "object") return typeof node.type === "function" ? text(node.type(node.props)) : text(node.props?.children);
  return node == null ? "" : String(node);
}
const metric = { courses: [{ id: "c", code: "SC4000", name: "Machine Learning", semester: "S1" }, { id: "z", code: "SC0000", name: "Empty", semester: "S1" }], period: { start: "2026-08-07T16:00:00Z", end: "2026-10-24T04:00:00Z", error: null }, attendance: { course_id: "c", approved: 9, eligible: 10, percentage: 90, unresolved: 1 } };
function harness(states = {}) {
  const queries = [], nav = [];
  const cards = load("components/dashboard/StudentOverview.tsx", name => {
    if (name === "react/jsx-runtime") return require(name);
    if (name === "@tanstack/react-query") return { useQuery(options) {
      queries.push(options);
      const section = options.queryKey[2];
      return states[section] ?? { data: section === "attendance" ? metric : section === "today" ? { today: { total: 2, active: 1, upcoming: 1, completed: 0, sessions: [] } } : { flagged: { total: 3, flagged: 2, appealed: 1 } } };
    } };
    if (name.includes("student-overview")) return { fetchStudentOverview: (...args) => args };
    return { formatSingaporeDateTime: value => value };
  });
  const props = { userId: "student", courseId: "c", onCourseChange: id => nav.push(["course", id]), onAttendance: (...args) => nav.push(["attendance", ...args]), onToday: () => nav.push(["today"]) };
  return { cards, props, queries, nav, render() { return cards.StudentOverviewCards(props); } };
}
test("cards show backend counts, accessible percentage and applied navigation filters", () => {
  const h = harness(), tree = h.render();
  assert.match(text(tree), /90%/); assert.match(text(tree), /9 of 10/); assert.match(text(tree), /1 awaiting review/);
  assert.ok(elements(tree).some(node => node.props?.role === "img" && /9 of 10/.test(node.props["aria-label"])));
  const click = label => elements(tree).find(node => node.type === "a" && text(node) === label).props.onClick({ preventDefault() {} });
  click("View attendance →"); click("View records →");
  assert.equal(JSON.stringify(h.nav), JSON.stringify([["attendance","c",[]],["attendance","all",["flagged","appealed"]]]));
  assert.doesNotMatch(text(tree), /View today/);
  assert.equal(h.queries.length, 3);
  assert.ok(h.queries.every(query => query.refetchInterval === 30000));
});
test("course switch isolates attendance request keys and carries cancellation", () => {
  const h = harness(); let tree = h.render();
  const oldKeys = h.queries.map(query => JSON.stringify(query.queryKey));
  elements(tree).find(node => node.type === "select").props.onChange({ target: { value: "z" } });
  h.props.courseId = "z"; h.render();
  assert.notEqual(JSON.stringify(h.queries[3].queryKey), oldKeys[0]);
  assert.equal(JSON.stringify(h.queries[4].queryKey), oldKeys[1]);
  assert.equal(JSON.stringify(h.queries[5].queryKey), oldKeys[2]);
  assert.equal(h.queries[3].placeholderData, undefined);
  const signal = new AbortController().signal;
  assert.equal(h.queries[3].queryFn({ signal })[2], signal);
});
test("zero denominator is neutral; independent errors never display fabricated zeros", () => {
  const empty = harness({ attendance: { data: { ...metric, attendance: { ...metric.attendance, approved: 0, eligible: 0, percentage: null, unresolved: 0 } } } });
  const tree = empty.render(); assert.match(text(tree), /No completed sessions/); assert.match(text(tree), /—/); assert.doesNotMatch(text(tree), /0%/);
  const failed = harness({ attendance: { isError: true, refetch() {} }, flagged: { isPending: true } });
  const output = text(failed.render()); assert.match(output, /Could not load this card/); assert.match(output, /Loading/); assert.match(output, /Active\s*1/); assert.doesNotMatch(output, /No records awaiting review/);
});
test("overview API helper scopes course only for attendance and passes abort signals", async () => {
  const calls = [];
  const api = load("lib/student-overview.ts", () => ({ api: { request: (...args) => { calls.push(args); return {}; } } }));
  const signal = new AbortController().signal;
  await api.fetchStudentOverview("attendance", "course x", signal);
  await api.fetchStudentOverview("today", "course x", signal);
  assert.match(calls[0][0], /course_id=course\+x/); assert.doesNotMatch(calls[1][0], /course_id/); assert.equal(calls[0][1].signal, signal);
});

test("today card shows a calm empty state instead of zero status chips", () => {
  const h = harness({ today: { data: { today: { total: 0, active: 0, upcoming: 0, completed: 0, sessions: [] } } } });
  const section = elements(h.render()).find(node => node.type === "section" && /Today's sessions/.test(text(node)));
  assert.match(text(section), /You’re all caught up today/);
  assert.doesNotMatch(text(section), /Active|Upcoming/);
  assert.ok(elements(section).some(node => node.type === "p" && text(node) === "0" && node.props.className.includes("text-slate-100")));
});

test("compact status items and next session time use real response values", () => {
  const h = harness({ today: { data: { today: { total: 3, active: 1, upcoming: 2, completed: 0, sessions: [
    { id: "later", status: "scheduled", scheduled_start: "2026-10-24T09:00:00Z" },
    { id: "active", status: "active", scheduled_start: "2026-10-24T01:00:00Z" },
    { id: "next", status: "scheduled", scheduled_start: "2026-10-24T03:00:00Z" },
  ] } } } });
  const tree = h.render();
  assert.match(text(tree), /Active\s*1/); assert.match(text(tree), /Upcoming\s*2/);
  assert.match(text(tree), /Next session.*2026-10-24T03:00:00Z/);
  assert.match(text(tree), /Flagged\s*2/); assert.match(text(tree), /Appealed\s*1/);
  const footer = elements(tree).find(node => node.type === "footer");
  assert.match(text(footer), /View records/);
  assert.doesNotMatch(text(tree), /Across your courses/);
});

test("review bar proportions distinguish orange appeals from red flags and handle zero", () => {
  const tree = harness().render();
  const bar = elements(tree).find(node => node.props?.role === "img" && /appeals pending/.test(node.props["aria-label"]));
  const segments = elements(bar).filter(node => node.props?.style?.width);
  assert.equal(segments.length, 2);
  assert.match(segments[0].props.className, /orange/);
  assert.match(segments[1].props.className, /red/);
  assert.ok(Math.abs(parseFloat(segments[0].props.style.width) - 100 / 3) < 0.001);
  const emptyTree = harness({ flagged: { data: { flagged: { total: 0, flagged: 0, appealed: 0 } } } }).render();
  const emptyBar = elements(emptyTree).find(node => node.props?.role === "img" && /appeals pending/.test(node.props["aria-label"]));
  assert.equal(elements(emptyBar).filter(node => node.props?.style?.width).length, 0);
});
test("three cards filter the existing history table without adding tabs", () => {
  const values = []; let index = 0;
  const view = load("components/dashboard/StudentView.tsx", name => {
    if (name === "react/jsx-runtime") return require(name);
    if (name === "react") return { useMemo: fn => fn(), useState(initial) {
      const i = index++; if (!(i in values)) values[i] = initial;
      return [values[i], value => { values[i] = typeof value === "function" ? value(values[i]) : value; }];
    } };
    if (name === "@tanstack/react-query") return { useQuery: () => ({ data: [] }) };
    if (name.includes("StudentOverview")) return { StudentOverviewCards: "cards" };
    if (name.includes("CourseHistory")) return { CourseHistory: "history" };
    if (name.includes("attendance")) return { toRows: value => value };
    return {};
  });
  const render = () => { index = 0; return view.StudentView({ userId: "student" }); };
  let tree = render(); const cards = elements(tree).find(node => node.type === "cards");
  cards.props.onAttendance("all", ["flagged","appealed"]);
  tree = render(); const history = elements(tree).find(node => node.type === "history");
  assert.equal(history.props.initialCourseId, "all");
  assert.equal(JSON.stringify(history.props.initialStatuses), '["flagged","appealed"]');
  assert.equal(elements(tree).filter(node => node.type === "history").length, 1);
  assert.ok(elements(tree).some(node => node.props?.id === "student-history"));
  assert.equal(elements(tree).filter(node => node.props?.role === "tablist").length, 0);
  cards.props.onAttendance("c", []); tree = render();
  assert.equal(elements(tree).find(node => node.type === "history").props.initialCourseId, "c");
});
