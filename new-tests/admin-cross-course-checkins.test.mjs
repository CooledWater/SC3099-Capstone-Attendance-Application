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
function code(path) {
  return ts.transpileModule(
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
}
function nodes(tree) {
  if (!tree || typeof tree !== "object") return [];
  return Array.isArray(tree)
    ? tree.flatMap(nodes)
    : [tree, ...nodes(tree.props?.children)];
}
function text(tree) {
  if (Array.isArray(tree)) return tree.map(text).join("");
  return tree && typeof tree === "object"
    ? text(tree.props?.children)
    : tree == null
      ? ""
      : String(tree);
}
const sessions = ["a", "b"].map((id) => ({
  id,
  course_id: id,
  name: `Session ${id}`,
  status: "closed",
  starts_at: "2026-09-21T00:00:00Z",
  ends_at: "2026-09-21T01:00:00Z",
  courses: { code: id.toUpperCase() },
}));
const checkIns = [
  {
    id: "a1",
    session_id: "a",
    student_id: "same-student",
    student_name: "Alice Tan",
    student_email: "alice@example.edu",
    checked_in_at: "2026-10-29T16:00:00Z",
    status: "flagged",
    risk_score: 0.5,
  },
  {
    id: "b1",
    session_id: "b",
    student_id: "same-student",
    student_name: "Alice Tan",
    student_email: "alice@example.edu",
    checked_in_at: "2026-10-30T01:30:00Z",
    status: "appealed",
    risk_score: 0.9,
  },
  {
    id: "old",
    session_id: "b",
    checked_in_at: "2026-10-29T15:59:59Z",
    status: "flagged",
    risk_score: 0.6,
  },
  {
    id: "approved",
    session_id: "b",
    checked_in_at: "2026-10-30T15:59:59Z",
    status: "approved",
    risk_score: 0.1,
  },
  {
    id: "tomorrow",
    session_id: "a",
    checked_in_at: "2026-10-30T16:00:00Z",
    status: "approved",
    risk_score: 0.1,
  },
];
function harness(initialFilter = {}, state = {}) {
  const values = [];
  let cursor = 0,
    exports = [],
    retries = 0;
  const hooks = {
    useState(initial) {
      const i = cursor++;
      if (!(i in values)) values[i] = initial;
      return [
        values[i],
        (value) => {
          values[i] = value;
        },
      ];
    },
    useMemo: (fn) => fn(),
  };
  const times = { exports: {} };
  vm.runInNewContext(code("lib/time.ts"), times);
  const context = {
    exports: {},
    Date: class extends Date {
      constructor(...args) {
        super(...(args.length ? args : ["2026-10-30T12:00:00Z"]));
      }
    },
    require(name) {
      if (name === "react") return hooks;
      if (name === "react/jsx-runtime") return jsx;
      if (name.endsWith("/time")) return times.exports;
      if (name.endsWith("/attendance"))
        return {
          toRows: (rows) => rows,
          checkInsToCsv: (rows) => rows,
          downloadCsv: (_name, rows) => exports.push(rows),
        };
      if (name === "./AttendanceTable")
        return { AttendanceRoster: "AttendanceRoster" };
      if (name === "./InstructorCheckIns")
        return { CheckInDetail: "CheckInDetail" };
      return {};
    },
  };
  vm.runInNewContext(code("components/dashboard/AdminCheckIns.tsx"), context);
  const props = {
    courses: [{ id: "a" }, { id: "b" }],
    sessions,
    checkIns,
    userId: "admin",
    initialFilter,
    loading: false,
    error: false,
    onRetry: () => {
      retries++;
    },
    ...state,
  };
  return {
    draw() {
      cursor = 0;
      return context.exports.AdminCheckIns(props);
    },
    exports,
    retries: () => retries,
  };
}
const table = (tree) =>
  nodes(tree).find((node) => node.type === "AttendanceRoster");
const select = (tree, label, value) =>
  nodes(tree)
    .find((node) => node.props?.["aria-label"] === label)
    .props.onChange({ target: { value } });

test("today KPI starts at all courses/all sessions and uses check-in dates even for September sessions", () => {
  const h = harness({ today: true });
  const tree = h.draw();
  for (const label of ["Check-ins course", "Check-ins session"]) {
    assert.equal(
      nodes(tree).find((node) => node.props?.["aria-label"] === label).props
        .value,
      "all",
    );
  }
  assert.deepEqual(
    Array.from(table(tree).props.rows, (row) => row.checkin_id),
    ["a1", "b1", "approved"],
  );
  assert.equal(table(tree).props.checkInsOnly, true);
  assert.match(
    table(tree).props.rowContext(table(tree).props.rows[1]),
    /B · Session b/,
  );
});

test("course/session column omits a trailing SGT timestamp and preserves other name text", () => {
  for (const [name, expected] of [
    [
      "Video replay R0 TEST phone video (30 Oct 10:01 SGT)",
      "Video replay R0 TEST phone video",
    ],
    ["Video replay (30 Oct 2026 9.30AM SGT)", "Video replay"],
    ["Video replay (phone video)", "Video replay (phone video)"],
    ["Video replay", "Video replay"],
  ]) {
    const h = harness(
      {},
      {
        sessions: [
          { ...sessions[0], name, courses: { code: "SC4000" } },
          sessions[1],
        ],
      },
    );
    const props = table(h.draw()).props;
    assert.equal(props.rowContext(props.rows[0]), `SC4000 · ${expected}`);
  }
});
test("review KPI includes flagged and appealed records across courses and past days", () => {
  const h = harness({ statuses: ["flagged", "appealed"] });
  const props = table(h.draw()).props;
  const matches = props.rows.filter((row) =>
    props.verification.includes(row.status),
  );
  assert.deepEqual(
    Array.from(matches, (row) => row.checkin_id),
    ["a1", "b1", "old"],
  );
  assert.equal(matches[0].student_id, matches[1].student_id);
});
test("course/session narrowing and returning to all courses resets stale session selection", () => {
  const h = harness({ today: true });
  let tree = h.draw();
  select(tree, "Check-ins course", "b");
  tree = h.draw();
  assert.deepEqual(
    Array.from(table(tree).props.rows, (row) => row.checkin_id),
    ["b1", "approved"],
  );
  select(tree, "Check-ins session", "b");
  tree = h.draw();
  select(tree, "Check-ins course", "a");
  tree = h.draw();
  assert.equal(
    nodes(tree).find(
      (node) => node.props?.["aria-label"] === "Check-ins session",
    ).props.value,
    "all",
  );
  assert.deepEqual(
    Array.from(table(tree).props.rows, (row) => row.checkin_id),
    ["a1"],
  );
  select(tree, "Check-ins course", "all");
  tree = h.draw();
  assert.equal(table(tree).props.rows.length, 3);
});
test("risk shortcut includes the threshold and exports the scoped verification results", () => {
  const h = harness({ today: true, minRisk: 0.5 });
  let tree = h.draw();
  assert.deepEqual(
    Array.from(table(tree).props.rows, (row) => row.checkin_id),
    ["a1", "b1"],
  );
  table(tree).props.onVerificationChange(["appealed"]);
  tree = h.draw();
  table(tree).props.onExport();
  assert.deepEqual(
    Array.from(h.exports[0], (row) => row.id),
    ["b1"],
  );
});
test("review opens details with the clicked record's course and session", () => {
  const h = harness({});
  let tree = h.draw();
  table(tree).props.onSelect(table(tree).props.rows[1]);
  tree = h.draw();
  const detail = nodes(tree).find((node) => node.type === "CheckInDetail");
  assert.equal(detail.props.courseId, "b");
  assert.equal(detail.props.session.id, "b");
  assert.equal(detail.props.entry.checkin_id, "b1");
  select(tree, "Check-ins course", "a");
  assert.equal(
    nodes(h.draw()).some((node) => node.type === "CheckInDetail"),
    false,
  );
});
test("load errors preserve retry without showing a successful empty result", () => {
  const h = harness({}, { error: true });
  const tree = h.draw();
  assert.match(table(tree).props.error, /Could not load/);
  nodes(tree)
    .find((node) => node.type === "button" && text(node) === "Retry")
    .props.onClick();
  assert.equal(h.retries(), 1);
});

test("cross-course table renders repeated students with distinct check-in keys and context", () => {
  const h = harness({ today: true });
  const props = table(h.draw()).props;
  const times = { exports: {} };
  vm.runInNewContext(code("lib/time.ts"), times);
  const context = {
    exports: {},
    require(name) {
      if (name === "react/jsx-runtime") return jsx;
      if (name === "react")
        return {
          useState: (value) => [value, () => {}],
          useMemo: (fn) => fn(),
        };
      if (name.endsWith("/attendance")) return { statusText: {} };
      if (name.endsWith("/time")) return times.exports;
      if (name.endsWith("/checkin-roster"))
        return { filterRoster: (rows) => [...rows], attendanceLabels: {} };
      return {};
    },
  };
  vm.runInNewContext(code("components/dashboard/AttendanceTable.tsx"), context);
  const tree = context.exports.AttendanceRoster(props);
  const body = nodes(tree).find((node) => node.type === "tbody");
  const keys = nodes(body)
    .filter((node) => node.type === "tr")
    .map((node) => node.key);
  assert.equal(new Set(keys).size, 3);
  assert.match(text(body), /A · Session a/);
  assert.match(text(body), /B · Session b/);
  const studentRow = nodes(body).find(
    (node) => node.type === "tr" && node.key === "b1",
  );
  const cells = nodes(studentRow).filter((node) => node.type === "td");
  assert.equal(text(cells[0]), "Alice Tanalice@example.edu");
  assert.equal(text(cells[1]), "30 Oct 2026 9.30AM");
  assert.equal(text(cells[4]), "B · Session b");
  const midnightRow = nodes(body).find(
    (node) => node.type === "tr" && node.key === "a1",
  );
  assert.equal(
    text(nodes(midnightRow).filter((node) => node.type === "td")[1]),
    "30 Oct 2026 12.00AM",
  );
});
