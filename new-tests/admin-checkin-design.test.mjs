import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import vm from "node:vm";
import { test } from "node:test";

const require = createRequire(
  new URL("../module4-observability/package.json", import.meta.url),
);
const ts = require("typescript");
const jsx = require("react/jsx-runtime");
const source = readFileSync(
  new URL(
    "../module4-observability/src/components/dashboard/InstructorCheckIns.tsx",
    import.meta.url,
  ),
  "utf8",
);
const code = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2022,
    jsx: ts.JsxEmit.ReactJSX,
  },
}).outputText;
function nodes(tree) {
  if (!tree || typeof tree !== "object") return [];
  if (Array.isArray(tree)) return tree.flatMap(nodes);
  return [tree, ...nodes(tree.props?.children)];
}
function render(initialFilter, items, courseOptions) {
  const data = { course_id: "course", session_id: "session", items };
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
          useState: (value) => [value, () => {}],
          useEffect() {},
          useRef: (value) => ({ current: value }),
        };
      if (name === "@tanstack/react-query")
        return {
          useQuery: (options) => ({
            data:
              options.queryKey[0] === "session-attendance"
                ? data
                : options.queryKey[0] === "checkin-sessions"
                  ? (courseOptions?.sessions ?? [])
                  : [],
            isPending: false,
            isError: false,
          }),
        };
      if (name.endsWith("/AttendanceTable"))
        return { AttendanceRoster: "AttendanceRoster" };
      if (name.endsWith("/time"))
        return {
          parseApiDateTime: (value) =>
            new Date(/Z$/.test(value) ? value : `${value}Z`),
          formatSingaporeDateTime: (value) => value,
        };
      return {};
    },
  };
  vm.runInNewContext(
    `${code}\nexports.Session = SessionCheckIns; exports.Course = CourseCheckIns;`,
    context,
  );
  if (courseOptions)
    return context.exports.Course({
      courseId: "course",
      userId: "admin",
      initialSessionId: courseOptions.selection ?? "",
      reviewOnly: false,
      initialFilter,
    });
  const tree = context.exports.Session({
    session: { id: "session" },
    courseId: "course",
    userId: "admin",
    reviewOnly: false,
    initialFilter,
  });
  return nodes(tree).find((node) => node.type === "AttendanceRoster").props;
}
const rows = [
  {
    checkin_id: "before",
    checked_in_at: "2026-10-29T15:59:59Z",
    risk_score: 0.9,
  },
  {
    checkin_id: "boundary",
    checked_in_at: "2026-10-29T16:00:00Z",
    risk_score: 0.5,
  },
  {
    checkin_id: "low",
    checked_in_at: "2026-10-30T10:00:00Z",
    risk_score: 0.49,
  },
  {
    checkin_id: "naive",
    checked_in_at: "2026-10-30T15:59:59",
    risk_score: 0.8,
  },
  {
    checkin_id: "tomorrow",
    checked_in_at: "2026-10-30T16:00:00Z",
    risk_score: 0.7,
  },
  { checkin_id: null, checked_in_at: null, risk_score: null },
];
test("admin overview filters use Singapore day boundaries and inclusive risk on the shared roster", () => {
  const props = render({ today: true, minRisk: 0.5 }, rows);
  assert.deepEqual(
    Array.from(props.rows, (row) => row.checkin_id),
    ["boundary", "naive"],
  );
});
test("ordinary shared roster retains historical and missing check-ins", () => {
  const props = render({}, rows);
  assert.equal(props.rows.length, rows.length);
  assert.equal(props.rows.at(-1).checkin_id, null);
});
test("admin review shortcut initializes the instructor verification filters", () => {
  const props = render({ statuses: ["flagged", "appealed"] }, rows);
  assert.deepEqual(Array.from(props.verification), ["flagged", "appealed"]);
});

const sessions = [
  { id: "old", scheduled_start: "2026-09-21T10:00:00Z", status: "closed" },
  { id: "today", scheduled_start: "2026-10-29T16:00:00Z", status: "closed" },
  { id: "tomorrow", scheduled_start: "2026-10-30T16:00:00Z", status: "active" },
];
test("today shortcut selects October 30 instead of a saved September 21 session", () => {
  const tree = render({ today: true }, [], { sessions, selection: "old" });
  const select = nodes(tree).find(
    (node) => node.props?.["aria-label"] === "Check-ins session",
  );
  assert.equal(select.props.value, "today");
  assert.deepEqual(
    nodes(select)
      .filter((node) => node.type === "option")
      .map((node) => node.props.value),
    ["today"],
  );
});
test("today shortcut shows an empty state when the course has only historical sessions", () => {
  const tree = render({ today: true }, [], {
    sessions: [sessions[0]],
    selection: "old",
  });
  assert.equal(
    nodes(tree).some((node) => node.type === "select"),
    false,
  );
  assert.match(
    tree.props.children,
    /No active or closed sessions are scheduled today/,
  );
});
test("normal check-in navigation retains an explicitly selected historical session", () => {
  const tree = render({}, [], { sessions, selection: "old" });
  assert.equal(
    nodes(tree).find((node) => node.type === "select").props.value,
    "old",
  );
});
