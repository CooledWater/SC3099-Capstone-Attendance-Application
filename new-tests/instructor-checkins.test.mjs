import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import vm from "node:vm";
import { test } from "node:test";

const require = createRequire(new URL("../module4-observability/package.json", import.meta.url));
const ts = require("typescript");
const jsx = require("react/jsx-runtime");
const labels = { approved: "Approved", rejected: "Rejected", pending: "Pending", flagged: "Flagged", appealed: "Appealed" };
function moduleCode(path) {
  return ts.transpileModule(readFileSync(new URL(`../module4-observability/src/${path}`, import.meta.url), "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
}
function loadHelpers(request = async () => ({})) {
  const context = { exports: {}, require: () => ({ api: { request } }) };
  vm.runInNewContext(moduleCode("lib/checkin-roster.ts"), context);
  return context.exports;
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
const button = (tree, label) => elements(tree).find(node => node.type === "button" && text(node) === label);
function hooks() {
  const values = []; let next = 0;
  return { reset() { next = 0; }, react: {
    useMemo: fn => fn(), useEffect() {},
    useRef(initial) { const index = next++; return values[index] ??= { current: initial }; },
    useState(initial) { const index = next++; if (!(index in values)) values[index] = typeof initial === "function" ? initial() : initial;
      return [values[index], value => { values[index] = typeof value === "function" ? value(values[index]) : value; }]; },
  } };
}
const entry = (i, status = "approved", attendance = "present") => ({
  student_id: `s${i}`, student_name: `Student ${i}`, student_email: `s${i}@example.edu`,
  checkin_id: status ? `c${i}` : null, checked_in_at: status ? new Date(Date.UTC(2026, 0, 10, 9, i)).toISOString() : null,
  status, attendance,
});

test("complete pagination of flagged records and course sessions carries scope and cancellation", async () => {
  const calls = [], controller = new AbortController();
  const h = loadHelpers(async (path, init) => {
    calls.push([path, init.signal]);
    return { total: 3, items: path.endsWith("offset=0") ? [{ id: "a" }, { id: "b" }] : [{ id: "c" }] };
  });
  const rows = await h.fetchFlaggedSession("course x", "session y", controller.signal);
  assert.equal(rows.length, 3);
  assert.match(calls[0][0], /course_id=course%20x&session_id=session%20y&limit=100&offset=0/);
  assert.match(calls[1][0], /offset=2$/);
  assert.ok(calls.every(call => call[1] === controller.signal));
});

test("roster filters preserve five verification states, missing students, and latest-first order", () => {
  const h = loadHelpers();
  const rows = [entry(0), entry(1, "pending"), entry(2, "flagged", "present"), entry(3, "appealed"), entry(4, "rejected"), entry(5, null, "absent")];
  const all = h.filterRoster(rows, "", "all", []);
  assert.equal(all[0].checkin_id, "c4"); assert.equal(all.at(-1).checkin_id, null);
  assert.equal(h.filterRoster(rows, "S2@EXAMPLE", "present", []).length, 1);
  const review = h.filterRoster(rows, "", "all", ["flagged", "appealed"], new Set(["c2", "c3"]));
  assert.deepEqual(Array.from(review, row => row.status), ["appealed", "flagged"]);
  assert.equal(h.filterRoster(rows, "", "absent", ["none"]).length, 1);
  for (const status of Object.keys(labels)) assert.equal(h.filterRoster(rows, "", "all", [status]).length, 1);
  assert.equal(h.filterRoster(rows, "", "all", ["approved", "rejected"]).length, 2);
});

test("session selector includes only active and closed sessions", async () => {
  const h = loadHelpers(async () => ({ total: 5, items: [
    { id: "a", course_id: "c", status: "active", scheduled_start: "2026-01-10" },
    { id: "b", course_id: "c", status: "closed", scheduled_start: "2026-01-09" },
    { id: "s", course_id: "c", status: "scheduled", scheduled_start: "2026-01-11" },
    { id: "x", course_id: "c", status: "cancelled", scheduled_start: "2026-01-12" },
    { id: "other", course_id: "other", status: "active", scheduled_start: "2026-01-10" },
  ] }));
  assert.deepEqual(Array.from(await h.fetchCourseSessions("c"), row => row.id), ["a", "b"]);
});

test("review payload uses exact API statuses and retains returned factor precision", async () => {
  let call;
  const h = loadHelpers(async (...args) => { call = args; return {}; });
  await h.reviewCheckIn("c1", "approved", "  Reviewed explanation.  ");
  assert.equal(call[0], "/checkins/c1/review");
  assert.deepEqual(JSON.parse(call[1].body), { status: "approved", review_notes: "Reviewed explanation." });
  await h.reviewCheckIn("c1", "rejected", "");
  assert.deepEqual(JSON.parse(call[1].body), { status: "rejected", review_notes: null });
  assert.equal(h.factorLabel("geo_out_of_bounds"), "Outside permitted location");
  assert.equal(h.factorLabel("device_unknown"), "Unknown device");
  assert.equal(h.factorLabel("future_factor"), "Future factor");
});

function rosterHarness() {
  const state = hooks(), context = { exports: {}, require(name) {
    if (name === "react") return state.react;
    if (name === "react/jsx-runtime") return jsx;
    if (name.endsWith("/checkin-roster")) return loadHelpers();
    if (name.endsWith("/attendance")) return { statusText: labels };
    if (name.endsWith("/time")) return { formatSingaporeDateTime: value => value };
    throw new Error(name);
  } };
  vm.runInNewContext(moduleCode("components/dashboard/AttendanceTable.tsx"), context);
  return { render(props) { state.reset(); return context.exports.AttendanceRoster(props); } };
}

test("roster pagination, search reset, exact row actions and combined-filter reset", () => {
  const h = rosterHarness();
  let verification = [], selected;
  const props = { rows: Array.from({ length: 25 }, (_, i) => entry(i, i === 0 ? "flagged" : "approved")), loading: false, error: null, verification,
    onVerificationChange: value => { verification = value; }, flaggedIds: new Set(["c0"]), onSelect: row => { selected = row; }, onExport() {}, exporting: false };
  const render = () => h.render({ ...props, verification });
  let tree = render(); assert.match(text(tree), /1–10 of 25 students/);
  button(tree, "Next").props.onClick(); tree = render(); assert.match(text(tree), /11–20 of 25/);
  verification = ["flagged", "appealed"]; tree = render(); assert.match(text(tree), /1–1 of 1 students/);
  assert.ok(button(tree, "Review")); assert.equal(button(tree, "View details"), undefined);
  button(tree, "Review").props.onClick(); assert.equal(selected.checkin_id, "c0");
  button(tree, "Clear all").props.onClick(); tree = render();
  const search = elements(tree).find(node => node.type === "input");
  search.props.onChange({ target: { value: "s24@example" } });
  assert.match(text(render()), /1–1 of 1 students/);
});

test("verification checkboxes select statuses independently and chips remove one selection", () => {
  const h = rosterHarness();
  let verification = [];
  const props = { rows: [entry(0, "approved"), entry(1, "flagged"), entry(2, "appealed"), entry(3, "rejected")], loading: false, error: null,
    onVerificationChange: value => { verification = value; }, flaggedIds: undefined, onSelect() {}, onExport() {}, exporting: false };
  const render = () => h.render({ ...props, verification });
  const toggle = (tree, label) => elements(tree).find(node => node.type === "label" && text(node).trim() === label).props.children[0].props.onChange();
  let tree = render(); button(tree, "Filters").props.onClick(); tree = render();
  assert.doesNotMatch(text(tree), /Flagged \+ appealed/);
  toggle(tree, "Flagged"); tree = render();
  toggle(tree, "Appealed"); tree = render();
  assert.deepEqual(Array.from(verification), ["flagged", "appealed"]);
  assert.match(text(tree), /1–2 of 2 students/);
  elements(tree).find(node => node.props?.["aria-label"] === "Remove Flagged filter").props.onClick();
  tree = render(); assert.deepEqual(Array.from(verification), ["appealed"]);
  assert.match(text(tree), /1–1 of 1 students/);
  button(tree, "Clear all").props.onClick(); tree = render();
  assert.equal(verification.length, 0); assert.match(text(tree), /1–4 of 4 students/);
});

test("Risk column preserves decimal scores and sorts numerically both ways with missing scores last", () => {
  const h = rosterHarness();
  const props = { rows: [{ ...entry(0), risk_score: 0.9 }, { ...entry(1), risk_score: 0.174389 }, { ...entry(2), risk_score: 0 }, { ...entry(3, null, "absent"), risk_score: null }],
    loading: false, error: null, verification: [], onVerificationChange() {}, flaggedIds: undefined, onSelect() {}, onExport() {}, exporting: false };
  let tree = h.render(props);
  const columns = elements(tree).filter(node => node.type === "th").map(text);
  assert.equal(columns[3].startsWith("Verification"), true);
  assert.equal(columns[4], "Risk ↕"); assert.equal(columns[5], "Actions");
  button(tree, "Risk ↕").props.onClick(); tree = h.render(props);
  const ids = tree => elements(elements(tree).find(node => node.type === "tbody")).filter(node => node.type === "tr").map(node => node.key);
  assert.deepEqual(ids(tree), ["s2", "s1", "s0", "s3"]);
  assert.match(text(tree), /0.174389/);
  button(tree, "Risk ↑").props.onClick(); tree = h.render(props);
  assert.deepEqual(ids(tree), ["s0", "s1", "s2", "s3"]);
});

function detailHarness(initialStatus = "flagged") {
  const state = hooks(), invalidations = [], calls = [];
  let record = { ...entry(1), id: "c1", session_id: "s", course_id: "c", student_id: "s1", status: initialStatus, risk_score: 0.40123,
    risk_factors: [{ type: "geo_out_of_bounds", severity: "high", weight: 0.40123 }], appeal_reason: null };
  let handler = async (id, status) => ({ id, status });
  const helpers = loadHelpers();
  const context = { exports: {}, Error, require(name) {
    if (name === "react") return state.react;
    if (name === "react/jsx-runtime") return jsx;
    if (name === "@tanstack/react-query") return {
      useQuery: () => ({ data: record, isFetching: false, isError: false }),
      useQueryClient: () => ({ setQueryData(key, data) { record = data; }, invalidateQueries({ queryKey }) { invalidations.push(queryKey); return Promise.resolve(); } }),
    };
    if (name.endsWith("/checkin-roster")) return { ...helpers, async reviewCheckIn(...args) { calls.push(args); return handler(...args); } };
    if (name.endsWith("/attendance")) return { statusText: labels };
    if (name.endsWith("/time")) return { formatSingaporeDateTime: value => value };
    if (name.endsWith("/AttendanceTable")) return { VerificationBadge: ({ status }) => labels[status] };
    return {};
  } };
  vm.runInNewContext(moduleCode("components/dashboard/InstructorCheckIns.tsx") + "\nexports.Detail = CheckInDetail; exports.Breakdown = AttendanceBreakdown; exports.Summary = ReviewSummary; exports.Course = CourseCheckIns;", context);
  const props = { entry: entry(1, initialStatus, "present"), session: { id: "s", scheduled_start: "2026-01-10T09:00:00Z", name: "Lecture 9" }, courseId: "c", userId: "i", onClose() {} };
  return { calls, invalidations, get record() { return record; }, render() { state.reset(); return context.exports.Detail(props); }, setHandler(fn) { handler = fn; }, exports: context.exports };
}

test("details render actual risk score and keep appeal evidence only for appealed records", () => {
  for (const status of Object.keys(labels)) {
    const h = detailHarness(status), tree = h.render();
    assert.match(text(tree), /0.40123/);
    const appealed = status === "appealed";
    assert.equal(text(tree).includes("Risk factors"), appealed);
    assert.equal(text(tree).includes("Outside permitted location"), appealed);
    const reviewable = status === "flagged" || appealed;
    assert.equal(text(tree).includes("Student explanation"), appealed);
    assert.equal(!!button(tree, "Approve"), reviewable);
    if (reviewable) assert.match(button(tree, "Approve").props.className, /emerald/);
  }
});

test("approval blocks duplicate submission and refreshes details, roster and review counts", async () => {
  const h = detailHarness(); let resolve;
  h.setHandler(() => new Promise(done => { resolve = done; }));
  let tree = h.render();
  elements(tree).find(node => node.type === "textarea").props.onChange({ target: { value: "Evidence checked" } });
  tree = h.render(); const submit = elements(tree).find(node => node.type === "form").props.onSubmit;
  submit({ preventDefault() {} }); submit({ preventDefault() {} });
  assert.equal(h.calls.length, 1);
  assert.equal(h.calls[0][1], "approved");
  resolve({ id: "c1", status: "approved" }); await new Promise(setImmediate);
  assert.equal(h.record.status, "approved");
  assert.ok(h.invalidations.some(key => key[0] === "session-attendance"));
  assert.ok(h.invalidations.some(key => key[0] === "session-flagged"));
  assert.equal(button(h.render(), "Approve"), undefined);
  assert.match(text(h.render()), /Check-in approved/);
});

test("failed rejection retains notes and re-enables review controls", async () => {
  const h = detailHarness("appealed");
  h.setHandler(async () => { throw new Error("Review service unavailable"); });
  let tree = h.render();
  elements(tree).find(node => node.type === "textarea").props.onChange({ target: { value: "Keep these notes" } });
  tree = h.render(); button(tree, "Reject").props.onClick();
  await new Promise(setImmediate); tree = h.render();
  assert.equal(h.calls[0][1], "rejected");
  assert.equal(elements(tree).find(node => node.type === "textarea").props.value, "Keep these notes");
  assert.match(text(tree), /Review service unavailable/);
  assert.equal(button(tree, "Approve").props.disabled, false);
});

test("summary uses whole-session counts and combined review filter, including quiet zero state", () => {
  const h = detailHarness(); let filtered = false;
  const data = { expected: 8, session_status: "closed", summary: { present: 6, absent: 2, attendance_rate: 0.75, verification: { flagged: 1, appealed: 1 } } };
  const chart = h.exports.Breakdown({ data });
  assert.match(text(chart), /75%/); assert.match(text(chart), /25%/); assert.match(text(chart), /8 expected/);
  const summary = h.exports.Summary({ data, onFilter: () => { filtered = true; } });
  assert.match(text(summary), /1 flagged · 1 appealed/);
  button(summary, "Flagged check-ins").props.onClick(); assert.equal(filtered, true);
  const quiet = h.exports.Summary({ data: { ...data, summary: { verification: { flagged: 0, appealed: 0 } } }, onFilter() {} });
  assert.doesNotMatch(text(quiet), /No check-ins need review/); assert.doesNotMatch(quiet.props.className, /rose/);
});
