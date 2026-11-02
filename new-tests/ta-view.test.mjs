import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import vm from "node:vm";
import { test } from "node:test";

const require = createRequire(new URL("../module4-observability/package.json", import.meta.url));
const ts = require("typescript"), jsx = require("react/jsx-runtime");
function load(file, resolve) {
  const code = ts.transpileModule(readFileSync(new URL(`../module4-observability/src/${file}`, import.meta.url), "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  const context = { exports: {}, require: name => name === "react/jsx-runtime" ? jsx
    : name.endsWith("/session-permissions") ? load("lib/session-permissions.ts", () => ({})) : resolve(name) };
  vm.runInNewContext(code, context); return context.exports;
}
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
      return [values[key], value => { values[key] = value; }]; },
  } };
}
const session = (id, course_id, status = "active") => ({ id, course_id, instructor_id: "ta", name: id, status,
  starts_at: "2026-10-28T02:00:00Z", ends_at: "2026-10-28T03:00:00Z", expected_attendance: 10,
  courses: { code: course_id, name: course_id }, room: "Room" });
const courses = [{ id: "assigned", code: "SC4000", name: "Course", instructor_id: "teacher" }];

test("shared assigned-course loader reuses the existing endpoint with pagination and cancellation", async () => {
  const calls = [], signal = new AbortController().signal;
  const helper = load("lib/attendance.ts", name => name.endsWith("/api") ? { api: { request(path, init) {
    calls.push({ path, signal: init.signal });
    return { items: calls.length === 1 ? [{ id: "a" }, { id: "b" }] : [{ id: "c" }], total: 3 };
  } } } : {});
  const rows = await helper.fetchMyAssignedCourses({ signal });
  assert.deepEqual(Array.from(rows, row => row.id), ["a", "b", "c"]);
  assert.deepEqual(calls.map(call => call.path), [
    "/courses/my-courses?limit=100&offset=0", "/courses/my-courses?limit=100&offset=2",
  ]);
  assert.ok(calls.every(call => call.signal === signal));
});

test("TA has assigned-only overview, read-only sessions and enrollments, and shared instructor review", () => {
  const state = hooks(), queries = [];
  const view = load("components/dashboard/TaView.tsx", name => {
    if (name === "react") return state.react;
    if (name.endsWith("/useSessionValue")) return { useSessionValue: (_, initial) => state.react.useState(initial) };
    if (name === "@tanstack/react-query") return { useQuery(options) {
      queries.push(options);
      return { isSuccess: true, data: options.queryKey[0] === "ta-assigned-courses" ? courses
        : options.queryKey[0] === "ta-sessions" ? [session("owned", "assigned"), session("private", "other")]
          : [{ session_id: "owned", status: "flagged" }, { session_id: "private", status: "approved" }] };
    } };
    if (name.endsWith("/attendance")) return { toRows: rows => rows.map(row => ({ sessionId: row.session_id, status: row.status })) };
    if (name.endsWith("/time")) return { formatSingaporeDateTime: value => value };
    if (name.endsWith("/api")) return {};
    const component = name.split("/").at(-1); return { [component]: component };
  }).TaView;
  const render = () => { state.reset(); return view({ userId: "ta" }); };
  let tree = render();
  const tabs = elements(tree).find(node => node.type === "Tabs");
  assert.deepEqual(Array.from(tabs.props.tabs, tab => tab.id), ["overview", "sessions", "checkins", "enrollments"]);
  assert.ok(!text(tree).includes("private"));
  const overview = elements(tree).find(node => node.type === "TaOverview");
  assert.equal(overview.props.courseId, "assigned");
  overview.props.onOpenCheckIns("owned"); tree = render();
  const panel = elements(tree).find(node => node.type === "CheckInsPanel");
  assert.equal(panel.props.instructor.initialSessionId, "owned");
  assert.equal(panel.props.instructor.canExport, false);
  assert.deepEqual(panel.props.instructor.courses, courses);
  panel.props.instructor.onSessionChange("reviewed-session");
  tabs.props.onChange("overview");
  tree = render();
  assert.equal(elements(tree).find(node => node.type === "TaOverview").props.sessionId, "reviewed-session");
  elements(tree).find(node => node.type === "TaOverview").props.onOpenSessions("reviewed-session"); tree = render();
  const sessions = elements(tree).find(node => node.type === "SessionsPanel");
  assert.equal(sessions.props.canCreate, false);
  assert.equal(sessions.props.readOnly, true);
  assert.equal(sessions.props.currentUserId, "ta");
  assert.equal(sessions.props.selectedCourseId, "assigned");
  assert.deepEqual(Array.from(sessions.props.courseIds), ["assigned"]);
  assert.deepEqual(sessions.props.assignedCourses, courses);
  tabs.props.onChange("enrollments");
  tree = render();
  const roster = elements(tree).find(node => node.type === "EnrollmentsPanel");
  assert.deepEqual(roster.props.courses, courses);
  assert.equal(roster.props.selectedCourseId, "assigned");
  assert.equal(roster.props.canManage, false);
  assert.equal(roster.props.studentDetails, false);
  assert.equal(roster.props.stateKey, "ta:ta:roster");
});

test("read-only session list suppresses every session mutation and export even for a matching creator", () => {
  const state = hooks();
  const panel = load("components/dashboard/SessionsPanel.tsx", name => {
    if (name === "react") return state.react;
    if (name === "@tanstack/react-query") return { useQueryClient: () => ({}), useQuery: options => ({ isSuccess: true,
      data: options.queryKey[0] === "sessions" ? [session("Active", "assigned"), session("Closed", "assigned", "closed"), session("Hidden", "other")]
        : options.queryKey[0] === "courses" ? courses : { items: [] } }) };
    if (name.endsWith("/time")) return { parseApiDateTime: value => new Date(value), formatSingaporeDateTime: value => value };
    if (name.endsWith("/session-calendar")) return { mondayOf: () => "2026-10-26" };
    if (name.endsWith("/SessionCalendar")) return { SessionCalendar: "SessionCalendar" };
    if (name.endsWith("/AttendanceTable")) return { statusStyle: {} };
    if (name.endsWith("/attendance")) return { statusText: {} };
    return {};
  }).SessionsPanel;
  const props = { rows: [], canCreate: true, readOnly: true, currentUserId: "ta",
    assignedCourses: courses, courseIds: new Set(["assigned"]), onViewSession() {} };
  const tree = panel(props);
  assert.ok(!text(tree).includes("Hidden"));
  const labels = elements(tree).filter(node => node.type === "button").map(text);
  assert.ok(!labels.some(label => /New session|Create session|Edit|Cancel session|Delete|Close|Export/i.test(label)));
  elements(tree).find(node => node.type === "button" && text(node) === "Calendar").props.onClick();
  state.reset();
  const calendar = elements(panel(props)).find(node => node.type === "SessionCalendar");
  assert.equal(calendar.props.readOnly, true);
  assert.equal(calendar.props.userId, "ta");
  assert.deepEqual(Array.from(calendar.props.courseIds), ["assigned"]);
});

test("TA calendar blocks editing, creation and dragging while instructor interaction remains enabled", () => {
  const DAY = 86400000, week = Date.parse("2026-10-26T00:00:00+08:00");
  let edited = 0, created = 0, requests = 0;
  const state = hooks();
  const calendar = load("components/dashboard/SessionCalendar.tsx", name => {
    if (name === "react") return state.react;
    if (name === "@tanstack/react-query") return { useQueryClient: () => ({}), useQuery: () => ({ isSuccess: true,
      data: [session("Assigned", "assigned", "scheduled"), session("Unassigned", "other", "scheduled")] }) };
    if (name.endsWith("/time")) return { parseApiDateTime: value => new Date(value), formatSingaporeDateTime: value => String(value) };
    if (name.endsWith("/session-calendar")) return { DAY, SLOT: 1800000, mondayOf: () => week,
      layoutDay: (rows, day) => rows.filter(row => Date.parse(row.starts_at) >= day && Date.parse(row.starts_at) < day + DAY)
        .map(row => ({ session: row, start: Date.parse(row.starts_at), end: Date.parse(row.ends_at), lane: 0, lanes: 1 })) };
    if (name.endsWith("/api")) return { api: { request() { requests++; } } };
    return {};
  }).SessionCalendar;
  const props = { courseId: "assigned", courseIds: new Set(["assigned"]), userId: "ta", week,
    onWeekChange() {}, onEdit() { edited++; }, onCreate() { created++; } };
  let tree = calendar({ ...props, readOnly: true });
  const blocks = elements(tree).filter(node => node.props?.["data-session-id"]);
  assert.ok(blocks.length > 0);
  assert.ok(blocks.every(node => node.props.draggable === false && node.props["data-session-id"] === "Assigned"));
  blocks[0].props.onClick();
  let prevented = false;
  blocks[0].props.onDragStart({ preventDefault() { prevented = true; } });
  assert.equal(prevented, true);
  const slots = elements(tree).filter(node => node.props?.["data-calendar-slot"]);
  assert.ok(slots.every(node => node.props.disabled));
  slots[0].props.onClick();
  slots[0].props.onDrop({});
  assert.equal(edited, 0); assert.equal(created, 0); assert.equal(requests, 0);
  assert.ok(!text(tree).includes("New session on this day"));
  state.reset(); tree = calendar(props);
  const editable = elements(tree).find(node => node.props?.["data-session-id"]);
  assert.equal(editable.props.draggable, true);
  editable.props.onClick();
  elements(tree).find(node => node.props?.["data-calendar-slot"]).props.onClick();
  assert.equal(edited, 1); assert.equal(created, 1);
});
