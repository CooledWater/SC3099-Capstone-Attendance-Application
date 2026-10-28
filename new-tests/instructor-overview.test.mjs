import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import vm from "node:vm";
import { test } from "node:test";

const require = createRequire(new URL("../module4-observability/package.json", import.meta.url));
const ts = require("typescript");
const jsx = require("react/jsx-runtime");
const source = readFileSync(new URL("../module4-observability/src/components/dashboard/InstructorOverview.tsx", import.meta.url), "utf8");
const code = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
}).outputText;

function elements(node) {
  if (!node || typeof node !== "object") return [];
  if (Array.isArray(node)) return node.flatMap(elements);
  return [node, ...elements(node.props?.children)];
}

function harness(courseState = {}, riskDistribution = { scored_count: 0, bands: ["low", "medium", "high"].map(key => ({ key, count: 0 })) }) {
  const values = [];
  let cursor = 0, query, courseQuery, requestOptions;
  const context = { exports: {}, require(name) {
    if (name === "@tanstack/react-router") return { Link: "Link" };
    if (name === "recharts") return {};
    if (name === "react/jsx-runtime") return jsx;
    if (name === "react") return {
      useMemo: fn => fn(), useEffect() {},
      useState(initial) {
        const index = cursor++;
        if (!(index in values)) values[index] = typeof initial === "function" ? initial() : initial;
        return [values[index], value => { values[index] = value; }];
      },
    };
    if (name === "@tanstack/react-query") return { useQuery(options) {
      if (options.queryKey[0] === "instructor-course-stats") {
        courseQuery = options;
        return { data: { overall_attendance_rate: 0.73 }, ...courseState };
      }
      query = options;
      return { refetch() {}, data: {
        attendance: { rate: 0, approval_rate: null }, outstanding: { flagged: 0, appealed: 0 },
        today: { total: 0, breakdown: {} }, low_participation: { total: 0, students: [] },
        risk_distribution: riskDistribution, trend: [], recent_sessions: [],
      } };
    } };
    if (name === "@/lib/api") return { api: { request(path, options) { requestOptions = options; return path; } } };
    if (name === "@/lib/time") return { formatSingaporeDateTime: value => value };
    throw new Error(name);
  } };
  vm.runInNewContext(code, context);
  const render = () => {
    cursor = 0;
    return context.exports.InstructorOverview({
      courses: [{ id: "course", code: "CS", name: "Course" }], coursesLoading: false,
      selectedCourseId: "course", onCourseChange() {}, onOpenCheckIns() {}, onOpenSessions() {}, onOpenStudent() {},
    });
  };
  return { render, range: () => Array.from(query.queryKey).slice(-2),
    request: () => query.queryFn({ signal: undefined }),
    courseRequest: signal => courseQuery.queryFn({ signal }),
    courseKey: () => Array.from(courseQuery.queryKey),
    requestOptions: () => requestOptions,
    change(value, valid = true) {
      elements(render()).find(node => node.type === "input" && ["date", "month"].includes(node.props.type))
        .props.onChange({ target: { value, validity: { valid } } });
      render();
    },
    weekly() {
      elements(render()).find(node => node.type === "button" && node.props.children === "Weekly").props.onClick();
      render();
    },
  };
}

test("risk histogram renders API bands directly without numerical bins", () => {
  const h = harness({}, { scored_count: 12, bands: [
    { key: "low", count: 7 }, { key: "medium", count: 3 }, { key: "high", count: 2 },
  ] });
  const titles = elements(h.render()).map(node => node.props?.title).filter(Boolean);
  assert.deepEqual(titles, ["Low (<0.3): 7 check-ins", "Medium (0.3–<0.5): 3 check-ins", "High (≥0.5): 2 check-ins"]);
});

test("cleared or invalid period input preserves the selected monthly and weekly ranges", () => {
  const h = harness();
  h.render();
  for (const weekly of [false, true]) {
    if (weekly) h.weekly();
    const before = h.range();
    h.change("");
    assert.deepEqual(h.range(), before);
    h.change("invalid", false);
    assert.deepEqual(h.range(), before);
  }
});

test("monthly ranges handle leap years and year rollover with exclusive Singapore boundaries", () => {
  const h = harness();
  h.change("2024-02");
  assert.deepEqual(h.range(), ["2024-02-01", "2024-03-01"]);
  h.change("2026-12");
  assert.deepEqual(h.range(), ["2026-12-01", "2027-01-01"]);
  const url = new URL(h.request(), "https://example.test");
  assert.equal(url.searchParams.get("start_date"), "2026-12-01T00:00:00+08:00");
  assert.equal(url.searchParams.get("end_date"), "2027-01-01T00:00:00+08:00");
});

test("weekly ranges span seven days across leap day and year end", () => {
  const h = harness();
  h.weekly();
  h.change("2024-02-26");
  assert.deepEqual(h.range(), ["2024-02-26", "2024-03-04"]);
  h.change("2026-12-28");
  assert.deepEqual(h.range(), ["2026-12-28", "2027-01-04"]);
});

test("attendance card uses course statistics with inclusive Singapore end dates and cancellation", () => {
  const h = harness();
  const controller = new AbortController();
  for (const [month, finalDay] of [["2024-02", "2024-02-29"], ["2026-12", "2026-12-31"]]) {
    h.change(month);
    const url = new URL(h.courseRequest(controller.signal), "https://example.test");
    assert.equal(h.requestOptions().signal, controller.signal);
    assert.equal(url.pathname, "/stats/courses/course");
    assert.equal(url.searchParams.get("start_date"), `${month}-01T00:00:00+08:00`);
    assert.equal(url.searchParams.get("end_date"), `${finalDay}T23:59:59.999999+08:00`);
    assert.equal(h.courseKey().at(-1), `${finalDay}T23:59:59.999999+08:00`);
    assert.ok(elements(h.render()).some(node => node.type === "p" && node.props.children === "73%"));
  }
  h.weekly();
  h.change("2026-12-28");
  const url = new URL(h.courseRequest(controller.signal), "https://example.test");
  assert.equal(url.searchParams.get("end_date"), "2027-01-03T23:59:59.999999+08:00");
});

test("course statistics errors offer retry and loading does not display an overview fallback rate", () => {
  let retries = 0;
  const failed = harness({ isError: true, refetch() { retries++; } });
  const tree = failed.render();
  assert.ok(elements(tree).some(node => node.props?.role === "alert"));
  elements(tree).find(node => node.type === "button" && node.props.children === "Retry").props.onClick();
  assert.equal(retries, 1);
  const loading = harness({ data: undefined, isPending: true });
  assert.equal(elements(loading.render()).some(node => node.type === "p" && node.props.children === "0%"), false);
});

test("attendance trend tooltip shows exact rates, date range and provisional counts without bridging missing data", () => {
  const charts = Object.fromEntries(["Line", "LineChart", "ResponsiveContainer", "Tooltip", "XAxis", "YAxis"].map(name => [name, name]));
  const context = { exports: {}, require(name) {
    if (name === "react/jsx-runtime") return jsx;
    if (name === "recharts") return charts;
    return {};
  } };
  vm.runInNewContext(code + "\nexports.Trend = Trend;", context);
  const rows = [
    { start: "2026-10-01", end: "2026-10-08", recorded: 7, expected: 12, rate: 0.5833, provisional: true },
    { start: "2026-10-08", end: "2026-10-15", recorded: 0, expected: 0, rate: null, provisional: false },
    { start: "2026-10-15", end: "2026-10-22", recorded: 0, expected: 12, rate: 0, provisional: false },
  ];
  const tree = context.exports.Trend({ data: rows, monthly: true });
  const nodes = elements(tree);
  const chart = nodes.find(node => node.type === "LineChart");
  const line = nodes.find(node => node.type === "Line");
  const tooltip = nodes.find(node => node.type === "Tooltip");
  assert.equal(line.props.connectNulls, false);
  assert.deepEqual(Array.from(chart.props.data, point => point.rate), [0.5833, null, 0]);
  assert.deepEqual(Array.from(nodes.find(node => node.type === "YAxis").props.domain), [0, 1]);
  const text = node => Array.isArray(node) ? node.map(text).join("") : node && typeof node === "object" ? text(node.props?.children) : node == null ? "" : String(node);
  const hover = item => tooltip.props.content({ active: true, payload: [{ payload: item }] });
  assert.match(text(hover(chart.props.data[0])), /W1.*1 Oct.*7 Oct/);
  assert.match(text(hover(chart.props.data[0])), /7 recorded \/ 12 expected/);
  assert.match(text(hover(chart.props.data[0])), /58.33%/);
  assert.match(text(hover(chart.props.data[0])), /Provisional/);
  assert.match(text(hover(chart.props.data[1])), /No attendance rate available/);
  assert.match(text(hover(chart.props.data[2])), /Attendance rate: 0%/);
  assert.equal(tooltip.props.content({ active: false, payload: [] }), null);
});
