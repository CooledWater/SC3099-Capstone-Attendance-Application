import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import vm from "node:vm";
import { test } from "node:test";
const require = createRequire(
  new URL("../module4-observability/package.json", import.meta.url),
);
const ts = require("typescript"),
  jsx = require("react/jsx-runtime");
const compile = (path) =>
  ts.transpileModule(
    readFileSync(
      new URL(`../module4-observability/src/${path}`, import.meta.url),
      "utf8",
    ),
    {
      compilerOptions: {
        module: ts.ModuleKind.CommonJS,
        target: ts.ScriptTarget.ES2022,
        jsx: ts.JsxEmit.ReactJSX,
      },
    },
  ).outputText;
function helpers(request = async () => ({}), fetchCourses = async () => []) {
  const time = { exports: {} };
  vm.runInNewContext(compile("lib/time.ts"), time);
  const context = {
    exports: {},
    URLSearchParams,
    require(name) {
      if (name === "./api") return { api: { request } };
      if (name === "./time") return time.exports;
      if (name === "./admin") return { fetchAdminCourses: fetchCourses };
      throw new Error(name);
    },
  };
  vm.runInNewContext(compile("lib/admin-overview-charts.ts"), context);
  return context.exports;
}

test("admin course table uses saved held-session denominators and preserves unknown data", () => {
  const context = { exports: {}, require: () => ({}) };
  vm.runInNewContext(compile("components/dashboard/InstructorView.tsx"), context);
  const session = (id, status, saved) => ({
    id, status, course_id: "c", courses: { code: "SC4000", name: "Course" },
    expected_attendance: 999, saved_expected_attendance: saved,
  });
  const sessions = [session("a", "closed", 18), session("b", "active", 17), session("future", "scheduled", null)];
  const checkins = ["a", "b", "future"].map((session_id) => ({ session_id, risk_score: 0.1, status: "rejected" }));
  const result = context.exports.buildCourseStats(checkins, sessions)[0];
  assert.equal(result.expected, 35);
  assert.equal(result.sessions, 2);
  assert.equal(result.checkIns, 2);
  sessions[0].expected_attendance = 1;
  assert.equal(context.exports.buildCourseStats(checkins, sessions)[0].expected, 35);
  sessions[1].saved_expected_attendance = null;
  assert.equal(context.exports.buildCourseStats(checkins, sessions)[0].expected, null);
});
test("calendar week uses Monday and crosses year boundaries; local bounds respect timezone/DST", () => {
  const h = helpers();
  assert.equal(h.weekStart("2026-10-30"), "2026-10-26");
  assert.equal(h.weekStart("2027-01-01"), "2026-12-28");
  assert.equal(
    h.midnightUtc("2026-10-26", "Asia/Singapore"),
    "2026-10-25T16:00:00.000Z",
  );
  assert.equal(
    Date.parse(h.midnightUtc("2026-03-09", "America/New_York")) -
      Date.parse(h.midnightUtc("2026-03-08", "America/New_York")),
    23 * 3600000,
  );
});
test("daily counts include all statuses, use local timestamps, zero-fill elapsed dates, and leave future dates null", () => {
  const h = helpers();
  const records = [
    "approved",
    "flagged",
    "appealed",
    "pending",
    "rejected",
  ].map((status, i) => ({
    id: String(i),
    status,
    checked_in_at: "2026-10-29T16:00:00",
  }));
  records.push(
    { id: "before", checked_in_at: "2026-10-29T15:59:59Z" },
    records[0],
  );
  const points = h.dailyCheckIns(
    records,
    "2026-10-26",
    "Asia/Singapore",
    new Date("2026-10-30T01:30:00Z"),
  );
  assert.deepEqual(
    Array.from(points, (row) => row.count),
    [0, 0, 0, 1, 5, null, null],
  );
  assert.equal(points[4].partial, true);
  assert.equal(points[4].date, "2026-10-30");
});
function chartResponse(courses = []) {
  return {
    timezone: "Asia/Singapore",
    chart_days: Array.from({ length: 7 }, (_, i) => ({
      date: helpers().addDays("2026-10-26", i),
      count: i >= 5 ? null : 0,
      partial: i === 4,
    })),
    chart_courses: courses,
  };
}
test("all courses load through one aggregate overview request with cancellation", async () => {
  const calls = [];
  const payload = chartResponse(
    Array.from({ length: 100 }, (_, i) => ({
      course_id: String(i),
      course_code: `SC${i}`,
      course_name: `Course ${i}`,
      total_sessions: 2,
      recorded_checkins: 5,
      expected_attendances: 20,
      active_sessions: 1,
      historical_enrollment_limited: true,
    })),
  );
  const h = helpers(async (path, init) => {
    calls.push([path, init]);
    return payload;
  });
  const signal = new AbortController().signal;
  const result = await h.fetchAdminChartData(
    "2026-10-26",
    "Asia/Singapore",
    signal,
  );
  assert.equal(calls.length, 1);
  assert.match(calls[0][0], /^\/stats\/overview\?/);
  assert.equal(calls[0][1].signal, signal);
  const params = new URLSearchParams(calls[0][0].split("?")[1]);
  assert.equal(params.get("include_course_participation"), "true");
  assert.equal(params.get("start_date"), "2026-10-26");
  assert.equal(params.get("end_date"), "2026-11-02");
  assert.equal(result.courses.length, 100);
  assert.ok(result.courses.every((course) => course.rate === 0.25));
  assert.equal(result.days.length, 7);
});
test("failed or incomplete aggregates reject instead of supplying zeros", async () => {
  for (const response of [
    {},
    { ...chartResponse(), chart_days: [] },
    { ...chartResponse(), chart_courses: [{}] },
    {
      ...chartResponse(),
      chart_days: chartResponse().chart_days.map((day) => ({
        ...day,
        count: undefined,
      })),
    },
  ]) {
    await assert.rejects(
      helpers(async () => response).fetchAdminChartData(
        "2026-10-26",
        "Asia/Singapore",
        new AbortController().signal,
      ),
    );
  }
  await assert.rejects(
    helpers(async () => {
      throw new Error("failed");
    }).fetchAdminChartData(
      "2026-10-26",
      "Asia/Singapore",
      new AbortController().signal,
    ),
  );
});
test("zero denominators are null and historical enrollment discrepancies are not capped", async () => {
  const courses = [0, 2, null].map((expected, i) => ({
    course_id: String(i),
    course_code: `SC${i}`,
    course_name: "Course",
    total_sessions: 1,
    active_sessions: 0,
    recorded_checkins: 6,
    expected_attendances: expected,
  }));
  const result = await helpers(async () =>
    chartResponse(courses),
  ).fetchAdminChartData(
    "2026-10-26",
    "Asia/Singapore",
    new AbortController().signal,
  );
  assert.equal(result.courses[0].rate, null);
  assert.equal(result.courses[1].rate, 3);
  assert.equal(result.courses[2].rate, null);
});
function nodes(tree) {
  if (!tree || typeof tree !== "object") return [];
  return Array.isArray(tree)
    ? tree.flatMap(nodes)
    : [tree, ...nodes(tree.props?.children)];
}
function text(tree) {
  return Array.isArray(tree)
    ? tree.map(text).join("")
    : tree && typeof tree === "object"
      ? text(tree.props?.children)
      : tree == null
        ? ""
        : String(tree);
}
function component(queryState = {}) {
  const values = [];
  let cursor = 0,
    retries = 0,
    query;
  const h = helpers();
  const course = {
    course_id: "c",
    course_code: "SC3099",
    course_name: "Capstone",
    recorded_checkins: 5,
    expected_attendances: 10,
    total_sessions: 2,
    active_sessions: 1,
    rate: 0.5,
  };
  const context = {
    exports: {},
    Date: class extends Date {
      constructor(...args) {
        super(...(args.length ? args : ["2026-10-30T12:00:00Z"]));
      }
    },
    require(name) {
      if (name === "react/jsx-runtime") return jsx;
      if (name === "react")
        return {
          useEffect() {},
          useRef: (value) => ({ current: value }),
          useState(initial) {
            const i = cursor++;
            if (!(i in values))
              values[i] = typeof initial === "function" ? initial() : initial;
            return [
              values[i],
              (value) => {
                values[i] = value;
              },
            ];
          },
        };
      if (name === "recharts")
        return new Proxy({}, { get: (_, key) => String(key) });
      if (name === "@tanstack/react-query")
        return {
          useQuery(options) {
            query = options;
            return {
              data: {
                days: chartResponse().chart_days,
                courses: [course],
              },
              refetch() {
                retries++;
              },
              ...queryState,
            };
          },
        };
      if (name === "@/lib/admin-overview-charts") return h;
      if (name === "./InstructorOverview")
        return { InstructorOverview: "InstructorOverview" };
      throw new Error(name);
    },
  };
  vm.runInNewContext(
    compile("components/dashboard/AdminOverviewCharts.tsx"),
    context,
  );
  return {
    draw() {
      cursor = 0;
      return context.exports.AdminOverviewCharts({
        userId: "admin",
        timezone: "Asia/Singapore",
        onOpenCheckIns() {},
        onOpenSessions() {},
      });
    },
    retries: () => retries,
    query: () => query,
  };
}
test("weekly UI uses daily straight-line counts, integer axis, future gaps, and exact partial-day tooltips", () => {
  const h = component();
  const tree = h.draw();
  assert.ok(!text(tree).includes("Monthly"));
  assert.equal(h.query().queryKey[2], "2026-10-26");
  const chart = nodes(tree).find((node) => node.type === "LineChart");
  assert.equal(chart.props.data.length, 7);
  const line = nodes(chart).find((node) => node.type === "Line");
  assert.equal(line.props.type, "linear");
  assert.equal(line.props.connectNulls, false);
  const axis = nodes(chart).find((node) => node.type === "YAxis");
  assert.equal(axis.props.allowDecimals, false);
  assert.equal(axis.props.domain[0], 0);
  const tooltip = nodes(chart).find((node) => node.type === "Tooltip");
  const partial = chart.props.data.find((row) => row.date === "2026-10-30");
  const content = tooltip.props.content({
    active: true,
    payload: [{ payload: { ...partial, partial: true, count: 245 } }],
  });
  assert.match(text(content), /30 Oct 2026/);
  assert.match(text(content), /245 check-ins/);
  assert.match(text(content), /Partial day/);
});
test("course bars disclose counts/provisional status and open existing analytics for the reporting week", () => {
  const h = component();
  let tree = h.draw();
  const bar = nodes(tree).find(
    (node) => node.type === "button" && node.props.title?.includes("SC3099"),
  );
  assert.match(bar.props.title, /5 recorded check-ins \/ 10 expected/);
  assert.equal(bar.props.title.includes("included sessions"), false);
  assert.equal(bar.props.title.includes("Closed sessions only"), false);
  assert.match(bar.props.title, /Provisional/);
  bar.props.onClick();
  tree = h.draw();
  const analytics = nodes(tree).find(
    (node) => node.type === "InstructorOverview",
  );
  assert.equal(analytics.props.selectedCourseId, "c");
  assert.equal(analytics.props.reportingWeek, "2026-10-26");
});
test("chart failures/loading hide all plots and offer retry without showing zero results", () => {
  for (const state of [
    { isError: true },
    { data: undefined, isPending: true },
  ]) {
    const h = component(state),
      tree = h.draw();
    assert.equal(
      nodes(tree).some((node) => node.type === "LineChart"),
      false,
    );
    if (state.isError) {
      nodes(tree)
        .find((node) => node.type === "button" && text(node) === "Retry")
        .props.onClick();
      assert.equal(h.retries(), 1);
    }
  }
});

test("course chart retains every course, shows No data, and does not cap enrollment discrepancies", () => {
  const courses = Array.from({ length: 60 }, (_, i) => ({
    course_id: String(i),
    course_code: `SC${i}`,
    course_name: `Course ${i}`,
    total_sessions: i === 0 ? 0 : 1,
    active_sessions: 0,
    recorded_checkins: i === 1 ? 3 : 0,
    expected_attendances: i === 0 ? 0 : 1,
    rate: i === 0 ? null : i === 1 ? 3 : 0,
  }));
  const h = component({ data: { days: chartResponse().chart_days, courses } });
  const tree = h.draw();
  const bars = nodes(tree).filter(
    (node) => node.type === "button" && node.props.title,
  );
  assert.equal(bars.length, 60);
  assert.match(bars[0].props.title, /No data/);
  assert.match(bars[1].props.title, /300%/);
  assert.match(text(tree), /without capping/);
  assert.ok(
    nodes(tree).some((node) => node.props?.style?.minWidth === 60 * 86),
  );
  assert.ok(!nodes(tree).some((node) => node.props?.style?.height === "300%"));
});

test("weekly date control keeps invalid inputs unchanged and normalizes valid selections to Monday", () => {
  const h = component();
  let tree = h.draw();
  const input = () => nodes(tree).find((node) => node.type === "input");
  input().props.onChange({ target: { value: "", validity: { valid: false } } });
  tree = h.draw();
  assert.equal(h.query().queryKey[2], "2026-10-26");
  assert.equal(input().props.value, "");
  input().props.onBlur({
    currentTarget: { value: "", validity: { valid: false } },
  });
  tree = h.draw();
  assert.equal(input().props.value, "2026-10-26");
  input().props.onChange({
    target: { value: "2026-10-23", validity: { valid: true } },
  });
  tree = h.draw();
  assert.equal(input().props.value, "2026-10-23");
  assert.equal(h.query().queryKey[2], "2026-10-26");
  input().props.onBlur({
    currentTarget: { value: "2026-10-23", validity: { valid: true } },
  });
  tree = h.draw();
  assert.equal(h.query().queryKey[2], "2026-10-19");
  assert.equal(input().props.value, "2026-10-19");
});

test("typing a date does not apply intermediate years; Enter commits and Escape restores the selected week", () => {
  const h = component();
  let tree = h.draw();
  const input = () => nodes(tree).find((node) => node.type === "input");
  for (const value of [
    "0002-10-23",
    "0020-10-23",
    "0202-10-23",
    "2026-10-23",
  ]) {
    input().props.onChange({ target: { value, validity: { valid: true } } });
    tree = h.draw();
    assert.equal(input().props.value, value);
    assert.equal(h.query().queryKey[2], "2026-10-26");
  }
  input().props.onKeyDown({
    key: "Enter",
    preventDefault() {},
    currentTarget: { value: "2026-10-23", validity: { valid: true } },
  });
  tree = h.draw();
  assert.equal(h.query().queryKey[2], "2026-10-19");
  input().props.onChange({ target: { value: "2026-10-30" } });
  tree = h.draw();
  input().props.onKeyDown({ key: "Escape", preventDefault() {} });
  tree = h.draw();
  assert.equal(input().props.value, "2026-10-19");
  assert.equal(h.query().queryKey[2], "2026-10-19");
});

test("admin overview charts omit the date-range subtitle and timezone suffix labels", () => {
  const tree = component().draw();
  assert.equal(text(tree).includes("All courses · 26 Oct 2026"), false);
  assert.equal(text(tree).includes("Asia/Singapore"), false);
  assert.equal(text(tree).includes("SGT"), false);
  assert.equal(text(tree).includes("Today is partial."), false);
  assert.equal(text(tree).includes("Future dates are blank."), false);
  assert.equal(text(tree).includes("All verification statuses"), false);
  assert.equal(
    text(tree).includes(
      "Current active enrollments define expected attendance",
    ),
    false,
  );
});
