import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import vm from "node:vm";
import { test } from "node:test";
const require = createRequire(new URL("../module4-observability/package.json", import.meta.url));
const ts = require("typescript"), jsx = require("react/jsx-runtime");
function load(path, resolve, globals = {}) {
  const code = ts.transpileModule(readFileSync(new URL(`../module4-observability/src/${path}`, import.meta.url), "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  const context = { exports: {}, ...globals, require: name => name === "react/jsx-runtime" ? jsx : resolve(name) };
  vm.runInNewContext(code, context); return context.exports;
}
const time = load("lib/time.ts", () => ({}));
const helpers = load("lib/student-attendance.ts", () => time);
function elements(node) {
  if (!node || typeof node !== "object") return [];
  if (Array.isArray(node)) return node.flatMap(elements);
  return [node, ...elements(node.props?.children)];
}
function text(node) {
  if (Array.isArray(node)) return node.map(text).join("");
  return node && typeof node === "object" ? text(node.props?.children) : node == null ? "" : String(node);
}
function hooks() {
  const values = []; let index = 0;
  return { reset() { index = 0; }, react: {
    useMemo: fn => fn(), useEffect() {}, useRef: value => ({ current: value }),
    useState(initial) { const key = index++; if (!(key in values)) values[key] = typeof initial === "function" ? initial() : initial;
      return [values[key], value => { values[key] = typeof value === "function" ? value(values[key]) : value; }]; },
  } };
}
class ApiError extends Error { constructor(status) { super(); this.status = status; } }
const course = (id, code, rate = 0.92) => ({ course_id: id, course_code: code, attendance_rate: rate, sessions_attended: 11, total_sessions: 12, average_risk_score: 0.12 });
const checkin = (code, when, extra = {}) => ({ course_code: code, session_name: "Lecture", checked_in_at: when, status: "approved", ...extra });
function harness() {
  const state = hooks(); let result, query, call;
  const Detail = load("components/dashboard/StudentAttendanceDetails.tsx", name => {
    if (name === "react") return state.react;
    if (name === "@tanstack/react-query") return { useQuery: options => { query = options; return result; } };
    if (name.endsWith("/student-attendance")) return helpers;
    if (name.endsWith("/time")) return time;
    if (name.endsWith("/api")) return { ApiError, api: { request(...args) { call = args; } } };
    throw new Error(name);
  }).StudentAttendanceDetails;
  return { set(resultValue) { result = resultValue; }, get query() { return query; }, get call() { return call; }, render(props = {}) {
    state.reset(); return Detail({ studentId: "s /1", viewerId: "i", initialCourseId: "b", courses: [{ id: "b", name: "Software Engineering" }], ...props });
  } };
}
const data = () => ({ student_id: "s /1", student_name: "John Doe", student_email: "john@example.edu", courses: [course("a", "A"), course("b", "B", 0.5)], recent_checkins: [checkin("A", "2026-10-28T03:00:00Z"), checkin("B", "2026-10-27T01:00:00"), checkin("B", "2026-10-28T02:02:00Z")] });
test("originating course selects its cards and records; switching updates all values and sorts newest first", () => {
  const h = harness(); h.set({ data: data() });
  let tree = h.render();
  const select = elements(tree).find(n => n.type === "select");
  assert.equal(select.props.value, "b"); assert.match(text(select), /Software Engineering/);
  assert.match(text(tree), /50%/); assert.match(text(tree), /0.12/);
  const rows = elements(tree).filter(n => n.type === "tbody")[0];
  assert.equal(elements(rows).filter(n => n.type === "tr").length, 2);
  assert.match(text(rows), /28 Oct 2026, 10:02/);
  assert.ok(text(rows).indexOf("28 Oct") < text(rows).indexOf("27 Oct"));
  assert.ok(elements(tree).some(n => n.props?.className?.includes("overflow-x-auto")));
  select.props.onChange({ target: { value: "a" } }); tree = h.render(); assert.match(text(tree), /92%/);
  const signal = new AbortController().signal; h.query.queryFn({ signal });
  assert.equal(h.call[0], "/stats/students/s%20%2F1"); assert.equal(h.call[1].signal, signal);
  assert.deepEqual(Array.from(h.query.queryKey), ["student-attendance", "i", "s /1"]);
  tree = h.render({ studentId: "another" });
  assert.equal(elements(tree).find(n => n.type === "select").props.value, "b");
  assert.equal(h.query.queryKey.at(-1), "another");
});
test("missing, valid zero, no sessions, single course, empty courses and recent records stay distinct", () => {
  const h = harness(), d = data(); d.courses = [{ ...course("a", "A", 0), average_risk_score: null, sessions_attended: 0 }]; d.recent_checkins = [];
  h.set({ data: d }); let tree = h.render();
  assert.equal(elements(tree).some(n => n.type === "select"), false);
  assert.match(text(tree), /0%/); assert.match(text(tree), /Not available/); assert.match(text(tree), /No recent check-ins/);
  d.courses[0].total_sessions = 0; tree = h.render(); assert.match(text(tree), /No attendance data/);
  assert.equal(elements(tree).some(n => n.props?.role === "progressbar"), false);
  d.courses[0].average_risk_score = 0; assert.match(text(h.render()), /0.00/);
  d.courses = []; assert.match(text(h.render()), /No authorised courses/);
});
test("loading and status-specific errors are retryable without leaking stale metrics", () => {
  const h = harness(); h.set({ isPending: true });
  assert.equal(h.render().type.name, "AttendanceSkeleton");
  for (const [code, expected] of [[401, /session has expired/], [403, /do not have permission/], [404, /could not be found/], [500, /Could not load/]]) {
    let retried = 0; h.set({ isError: true, error: new ApiError(code), refetch() { retried++; } });
    const tree = h.render(); assert.match(text(tree), expected);
    elements(tree).find(n => n.type === "button").props.onClick(); assert.equal(retried, 1);
    assert.equal(h.query.retry(0, new ApiError(code)), code === 500);
  }
});
test("ambiguous course codes never guess matches; course_id takes precedence", () => {
  const d = { courses: [course("a", "DUP"), course("b", "DUP")], recent_checkins: [checkin("DUP", "2026-10-01"), checkin("DUP", "2026-10-02", { course_id: "a" }), checkin("DUP", "2026-10-03", { course_id: "b" })] };
  const result = helpers.courseCheckIns(d, d.courses[0]);
  assert.equal(result.ambiguous, true); assert.equal(result.records.length, 1); assert.equal(result.records[0].course_id, "a");
});
test("roster links use student_id, originating course and real route; filters survive remount", () => {
  const store = new Map();
  const storage = { getItem: key => store.get(key) ?? null, setItem: (key, value) => store.set(key, value) };
  const make = () => {
    const state = hooks(); const session = load("hooks/useSessionValue.ts", () => state.react, { sessionStorage: storage });
    const Panel = load("components/dashboard/EnrollmentsPanel.tsx", name => {
      if (name === "react") return state.react;
      if (name.endsWith("/useSessionValue")) return session;
      if (name === "@tanstack/react-router") return { Link: "Link" };
      if (name === "@tanstack/react-query") return { useQueryClient: () => ({}), useQuery: options => ({ data: options.queryKey[0] === "enrollment-roster" ? { students: [{ id: "enrollment", student_id: "student", student_name: "Alice", student_email: "a@example.edu", is_active: true }] } : { items: [] } }) };
      return {};
    }).EnrollmentsPanel;
    return (enabled = true) => { state.reset(); return Panel({ courses: [{ id: "c", code: "CS", name: "Course" }], selectedCourseId: "c", onCourseChange() {}, canManage: false, loading: false, error: false, studentDetails: enabled, stateKey: "instructor:i:roster" }); };
  };
  const render = make(); let tree = render();
  const link = elements(tree).find(n => n.type === "Link"); assert.equal(link.props.params.studentId, "student"); assert.equal(link.props.search.courseId, "c");
  elements(tree).find(n => n.type === "input").props.onChange({ target: { value: "Alice" } });
  elements(tree).find(n => n.type === "select" && !n.props["aria-label"]).props.onChange({ target: { value: "true" } });
  tree = make()(); assert.equal(elements(tree).find(n => n.type === "input").props.value, "Alice");
  assert.equal(elements(tree).find(n => n.type === "select" && !n.props["aria-label"]).props.value, "true");
  assert.equal(elements(render(false)).some(n => n.type === "Link"), false);
});
