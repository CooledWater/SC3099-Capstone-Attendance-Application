import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import vm from "node:vm";
import { test } from "node:test";
const require = createRequire(new URL("../module4-observability/package.json", import.meta.url));
const ts = require("typescript"), jsx = require("react/jsx-runtime");
function load(path, resolve) {
  const code = ts.transpileModule(readFileSync(new URL(`../module4-observability/src/${path}`, import.meta.url), "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  const context = { exports: {}, require: name => name === "react/jsx-runtime" ? jsx : resolve(name) };
  vm.runInNewContext(code, context); return context.exports;
}
const time = load("lib/time.ts", () => ({}));
const helpers = load("lib/ta-overview.ts", name => name.endsWith("time") ? time : {});
const stats = () => ({ session_id: "s", course_id: "c", course_code: "SC4000", session_name: "Lecture", status: "active",
  scheduled_start: "2026-10-28T02:00:00Z", scheduled_end: "2026-10-28T03:00:00Z", actual_end: null,
  checkin_opens_at: "2026-10-28T01:45:00Z", checkin_closes_at: "2026-10-28T02:30:00Z", server_time: "2026-10-28T02:02:00Z",
  timezone: "Asia/Singapore", submitted_count: 5, expected_count: 6, scored_count: 5, average_risk_score: 0.4,
  by_status: { approved: 1, pending: 1, flagged: 1, appealed: 1, rejected: 1 }, timeline_bucket_minutes: 5, pre_opening_count: 1,
  checkin_timeline: [{ minute: 0, count: 2 }, { minute: 5, count: 1 }, { minute: 15, count: 1 }, { minute: 75, count: 1 }],
  today: { date: "2026-10-28", total: 2, breakdown: { active: 1, scheduled: 1 } }, recent_review_activity: [] });
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
  return { reset() { index = 0; }, react: { useEffect() {}, useRef: () => ({ current: null }),
    useState(initial) { const key = index++; if (!(key in values)) values[key] = initial;
      return [values[key], value => { values[key] = value; }]; },
  } };
}

test("timeline preserves five-minute opening anchor, empty elapsed intervals, current partial interval, future gaps and outliers", () => {
  const buckets = helpers.sessionTimeline(stats());
  assert.equal(helpers.sessionClock(buckets[0].start, "Asia/Singapore"), "09:45");
  assert.equal(buckets[0].end - buckets[0].start, 300000);
  assert.equal(buckets[0].preOpening, 1);
  assert.equal(buckets[2].count, 0);
  assert.equal(buckets[3].current, true);
  assert.equal(buckets[4].count, null);
  assert.equal(buckets[15].count, 1);
  assert.equal(buckets[15].outsideWindow, true);
  assert.equal(buckets.reduce((n, item) => n + (item.count ?? 0), 0), 5);
  const beforeOpen = { ...stats(), status: "scheduled", server_time: "2026-10-28T01:00:00Z", checkin_timeline: [] };
  assert.ok(helpers.sessionTimeline(beforeOpen).every(item => item.count === null));
  const closed = { ...stats(), status: "closed", actual_end: "2026-10-28T02:10:00Z", server_time: "2026-10-28T04:00:00Z" };
  assert.ok(helpers.sessionTimeline(closed).every(item => !item.current));
  assert.equal(helpers.sessionTimeline(closed)[5].count, null);
});

test("session default prefers active, then recent closed; course session loading consumes all pages and cancellation", async () => {
  const sessions = [{ id: "closed", status: "closed", scheduled_start: "2026-10-28T03:00:00Z" }, { id: "active", status: "active", scheduled_start: "2026-10-28T02:00:00Z" }];
  assert.equal(helpers.defaultTaSession(sessions).id, "active");
  assert.equal(helpers.defaultTaSession(sessions.slice(0, 1)).id, "closed");
  const calls = [], signal = new AbortController().signal;
  const api = load("lib/ta-overview.ts", name => name.endsWith("time") ? time : { api: { request(path, init) {
    calls.push([path, init.signal]);
    return { total: 2, items: [{ id: calls.length, course_id: "course /" }] };
  } } });
  assert.equal((await api.fetchTaCourseSessions("course /", signal)).length, 2);
  assert.match(calls[0][0], /course_id=course%20%2F/);
  assert.match(calls[1][0], /offset=1$/);
  assert.ok(calls.every(call => call[1] === signal));
});

test("KPI review shortcut and donut share roster filters, review details preserve context, and no-denominator/missing-score states are honest", () => {
  const state = hooks(), queries = [], calls = [];
  let data = stats();
  const Overview = load("components/dashboard/TaOverview.tsx", name => {
    if (name === "react") return state.react;
    if (name === "@tanstack/react-query") return { useQuery(options) { queries.push(options); return { data: options.queryKey[0] === "session-stats" ? data
      : options.queryKey[0] === "session-attendance" ? { session_id: "s", course_id: "c", items: [] } : [] }; } };
    if (name.endsWith("/ta-overview")) return helpers;
    if (name.endsWith("/time")) return time;
    if (name.endsWith("/api")) return { api: { request(...args) { calls.push(args); } } };
    if (name.endsWith("/checkin-roster")) return {};
    if (name.endsWith("/AttendanceTable")) return { AttendanceRoster: "Roster" };
    if (name.endsWith("/InstructorCheckIns")) return { CheckInDetail: "Detail" };
    return {};
  }).TaSessionOverview;
  const opened = [], scrolls = [];
  const props = { session: { id: "s", course_id: "c", name: "Lecture", scheduled_start: data.scheduled_start }, courseId: "c", userId: "ta",
    onOpenSessions: id => opened.push(["sessions", id]), onOpenCheckIns: id => opened.push(["checkins", id]) };
  const render = () => { state.reset(); return Overview(props); };
  let tree = render();
  assert.match(text(tree), /83%/);
  elements(tree).find(node => node.type === "button" && text(node).includes("Today’s sessions")).props.onClick();
  elements(tree).find(node => node.type === "button" && text(node).includes("Check-in rate")).props.onClick();
  assert.deepEqual(opened, [["sessions", "s"], ["checkins", "s"]]);
  elements(tree).find(node => node.props?.className?.includes("scroll-mt-4")).props.ref.current = { scrollIntoView(options) { scrolls.push(options); } };
  elements(tree).find(node => node.type === "button" && text(node).includes("Needs review")).props.onClick();
  assert.equal(scrolls.length, 1);
  assert.equal(scrolls[0].block, "start");
  tree = render();
  let roster = elements(tree).find(node => node.type === "Roster");
  assert.deepEqual(Array.from(roster.props.verification), ["flagged", "appealed"]);
  assert.equal(roster.props.checkInsOnly, true);
  assert.equal(roster.props.canExport, false);
  const donut = elements(tree).find(node => node.type?.name === "VerificationDonut");
  donut.props.onFilter(["rejected"]); tree = render();
  roster = elements(tree).find(node => node.type === "Roster");
  assert.deepEqual(Array.from(roster.props.verification), ["rejected"]);
  roster.props.onSelect({ checkin_id: "id", student_name: "Student" }); tree = render();
  elements(tree).find(node => node.type === "Detail").props.onClose();
  assert.deepEqual(Array.from(elements(render()).find(node => node.type === "Roster").props.verification), ["rejected"]);
  const query = queries.find(q => q.queryKey[0] === "session-stats"), signal = new AbortController().signal;
  query.queryFn({ signal }); assert.equal(calls[0][0], "/stats/sessions/s"); assert.equal(calls[0][1].signal, signal);
  assert.equal(query.refetchInterval({ state: { data } }), 15000);
  data = { ...data, expected_count: 0, scored_count: 0 }; tree = render();
  assert.match(text(tree), /Unavailable/); assert.match(text(tree), /No scored check-ins/);
  data = { ...data, course_id: "unrelated" }; tree = render();
  assert.equal(text(tree).includes("83%"), false);
});
