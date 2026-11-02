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
const userId = "11111111-1111-4111-8111-111111111111";
const resourceId = "22222222-2222-4222-8222-222222222222";
const row = (id) => ({
  id,
  timestamp: "2026-10-29T01:00:00Z",
  user_id: userId,
  user_email: "alice@example.edu",
  action: "user_updated",
  severity: "info",
  success: true,
  resource_type: "user",
  resource_id: resourceId,
  details: { message: 'A "quoted", value' },
});
function harness({
  request = async () => ({}),
  role = "admin",
  mode = "success",
  total = 260,
  records = [row("visible")],
} = {}) {
  const states = [],
    cache = new Map(),
    calls = [],
    queries = [],
    downloads = [];
  let cursor = 0;
  function state(value) {
    const i = cursor++;
    if (!(i in states))
      states[i] = typeof value === "function" ? value() : value;
    return [
      states[i],
      (next) => {
        states[i] = typeof next === "function" ? next(states[i]) : next;
      },
    ];
  }
  const api = {
    request: async (...args) => {
      calls.push(args);
      return request(...args);
    },
  };
  function load(path) {
    if (cache.has(path)) return cache.get(path);
    const context = {
      exports: {},
      Date,
      URLSearchParams,
      AbortController,
      require(name) {
        if (name === "react")
          return {
            useState: state,
            useEffect() {},
            useRef: (initial) => {
              const [ref] = state({ current: initial });
              return ref;
            },
          };
        if (name === "react/jsx-runtime") return jsx;
        if (name === "@/components/ui/dialog")
          return Object.fromEntries(
            [
              "Dialog",
              "DialogContent",
              "DialogDescription",
              "DialogHeader",
              "DialogTitle",
            ].map((name) => [name, name]),
          );
        if (name === "@tanstack/react-query")
          return {
            useQuery(options) {
              queries.push(options);
              const audit = options.queryKey[0] === "audit-logs";
              const data = audit
                ? { items: records, total }
                : {
                    items: [
                      {
                        id: userId,
                        full_name: "Alice Tan",
                        email: "alice@example.edu",
                      },
                    ],
                    total: 60,
                  };
              return {
                data: mode === "loading" ? undefined : data,
                isSuccess: mode === "success",
                isPending: mode === "loading",
                isError: mode === "error",
                isFetching: false,
                error: new Error("Forbidden"),
                refetch() {},
              };
            },
          };
        if (name.endsWith("/useAuth"))
          return {
            useAuth: () => ({ user: { id: userId, role }, loading: false }),
          };
        if (name.endsWith("/useDebouncedValue"))
          return { useDebouncedValue: (value) => value };
        if (name.endsWith("/api") || name === "./api") return { api };
        if (name.endsWith("/audit")) return load("lib/audit.ts");
        if (name.endsWith("/admin")) return load("lib/admin.ts");
        if (name.endsWith("/time") || name === "./time")
          return load("lib/time.ts");
        if (name.endsWith("/attendance"))
          return { downloadCsv: (...args) => downloads.push(args) };
        throw new Error(name);
      },
    };
    vm.runInNewContext(compile(path), context);
    cache.set(path, context.exports);
    return context.exports;
  }
  return {
    load,
    calls,
    queries,
    downloads,
    render() {
      cursor = 0;
      queries.length = 0;
      return load("components/dashboard/AuditLogs.tsx").AuditLogs();
    },
  };
}
const nodes = (tree) =>
  !tree || typeof tree !== "object"
    ? []
    : Array.isArray(tree)
      ? tree.flatMap(nodes)
      : [tree, ...nodes(tree.props?.children)];
const text = (tree) =>
  typeof tree === "string" || typeof tree === "number"
    ? String(tree)
    : Array.isArray(tree)
      ? tree.map(text).join("")
      : tree?.props
        ? text(tree.props.children)
        : "";
function find(tree, predicate) {
  const node = nodes(tree).find(predicate);
  assert.ok(node, "Expected control");
  return node;
}
const button = (tree, label) =>
  find(tree, (node) => node.type === "button" && text(node) === label);
const field = (tree, label, type) =>
  find(
    find(tree, (node) => node.type === "label" && text(node).startsWith(label)),
    (node) => node.type === type,
  );
const prevent = { preventDefault() {} };

test("audit requests pass every documented filter to the server with Singapore dates and pagination", async () => {
  const h = harness(),
    api = h.load("lib/audit.ts"),
    signal = new AbortController().signal;
  await api.fetchAuditPage(
    {
      userId,
      action: "user_updated",
      resourceType: " user ",
      resourceId,
      success: "false",
      startDate: "2026-10-01T00:00",
      endDate: "2026-10-29T23:59",
    },
    50,
    250,
    signal,
  );
  const params = new URL(h.calls[0][0], "http://local").searchParams;
  assert.equal(params.get("user_id"), userId);
  assert.equal(params.get("action"), "user_updated");
  assert.equal(params.get("resource_type"), "user");
  assert.equal(params.get("resource_id"), resourceId);
  assert.equal(params.get("success"), "false");
  assert.equal(params.get("start_date"), "2026-09-30T16:00:00.000Z");
  assert.equal(params.get("end_date"), "2026-10-29T15:59:00.000Z");
  assert.equal(params.get("offset"), "250");
  assert.equal(h.calls[0][1].signal, signal);
});

test("invalid IDs, invalid dates and reversed ranges do not issue requests", () => {
  const h = harness(),
    api = h.load("lib/audit.ts");
  for (const update of [
    { resourceId: "bad" },
    { userId: "bad" },
    { startDate: "2026-02-30T10:00" },
    { startDate: "2026-10-29T12:00", endDate: "2026-10-28T12:00" },
  ]) {
    assert.throws(() =>
      api.fetchAuditPage({ ...api.emptyAuditFilters, ...update }, 50, 0),
    );
  }
  assert.equal(h.calls.length, 0);
});

test("filtered exports consume every page beyond 200 with one fixed upper timestamp", async () => {
  const h = harness({
    request: async (path) => {
      const offset = Number(
        new URL(path, "http://local").searchParams.get("offset"),
      );
      return {
        items: Array.from({ length: offset === 0 ? 1000 : 205 }, (_, i) =>
          row(String(offset + i)),
        ),
        total: 1205,
      };
    },
  });
  const api = h.load("lib/audit.ts"),
    signal = new AbortController().signal;
  const rows = await api.fetchAuditExport(
    { ...api.emptyAuditFilters, action: "user_updated", success: "false" },
    signal,
  );
  assert.equal(rows.length, 1205);
  assert.equal(h.calls.length, 2);
  const params = h.calls.map(
    ([path]) => new URL(path, "http://local").searchParams,
  );
  assert.equal(params[1].get("offset"), "1000");
  assert.equal(params[0].get("end_date"), params[1].get("end_date"));
  assert.ok(h.calls.every(([, init]) => init.signal === signal));
  assert.ok(
    params.every(
      (p) => p.get("action") === "user_updated" && p.get("success") === "false",
    ),
  );
});

test("export retains selected end, stops on an empty page and propagates cancellation", async () => {
  const h = harness({ request: async () => ({ items: [], total: 100 }) }),
    api = h.load("lib/audit.ts");
  assert.equal(
    (
      await api.fetchAuditExport({
        ...api.emptyAuditFilters,
        endDate: "2026-10-29T10:00",
      })
    ).length,
    0,
  );
  assert.equal(
    new URL(h.calls[0][0], "http://local").searchParams.get("end_date"),
    "2026-10-29T02:00:00.000Z",
  );
  const controller = new AbortController();
  controller.abort();
  const aborted = harness({
    request: async (_path, init) => {
      if (init.signal.aborted) throw new Error("aborted");
    },
  });
  const a = aborted.load("lib/audit.ts");
  await assert.rejects(
    a.fetchAuditExport(a.emptyAuditFilters, controller.signal),
    /aborted/,
  );
});

test("CSV preserves contract columns, JSON details and quoting, and escapes spreadsheet formulas", () => {
  const api = harness().load("lib/audit.ts");
  const csv = api.auditCsv([
    { ...row("a"), user_email: '=HYPERLINK("x")' },
    { ...row("b"), user_email: null, details: null },
  ]);
  assert.ok(
    csv.startsWith(
      '\uFEFF"timestamp","user_email","action","severity","details"',
    ),
  );
  assert.ok(csv.includes("'=HYPERLINK"));
  assert.ok(csv.includes('""x""'));
  assert.ok(csv.includes('""message""'));
  assert.equal(csv.split("\r\n").length, 3);
});

test("audit table scrolls with a sticky header and server pagination reaches older entries", async () => {
  const h = harness();
  let tree = h.render();
  const region = find(
    tree,
    (node) => node.props?.["aria-label"] === "Audit events",
  );
  assert.match(region.props.className, /max-h-\[85vh\].*overflow-auto/);
  assert.match(
    find(tree, (node) => node.type === "thead").props.className,
    /sticky top-0/,
  );
  for (let i = 0; i < 5; i++) {
    button(tree, "Next").props.onClick();
    tree = h.render();
  }
  await h.queries
    .find((q) => q.queryKey[0] === "audit-logs")
    .queryFn({ signal: new AbortController().signal });
  assert.equal(
    new URL(h.calls[0][0], "http://local").searchParams.get("offset"),
    "250",
  );
  assert.equal(button(tree, "Next").props.disabled, true);
  assert.ok(text(tree).includes("251–251 of 260 events"));
});

test("applying full filters resets the page and resetting clears both form and API scope", async () => {
  const h = harness();
  let tree = h.render();
  button(tree, "Next").props.onClick();
  tree = h.render();
  field(tree, "Action", "select").props.onChange({
    target: { value: "login_failed" },
  });
  tree = h.render();
  field(tree, "Outcome", "select").props.onChange({
    target: { value: "false" },
  });
  tree = h.render();
  field(tree, "Resource ID", "input").props.onChange({
    target: { value: resourceId },
  });
  tree = h.render();
  find(tree, (node) => node.type === "form").props.onSubmit(prevent);
  tree = h.render();
  await h.queries
    .find((q) => q.queryKey[0] === "audit-logs")
    .queryFn({ signal: null });
  let params = new URL(h.calls[0][0], "http://local").searchParams;
  assert.equal(params.get("offset"), "0");
  assert.equal(params.get("action"), "login_failed");
  assert.equal(params.get("success"), "false");
  assert.equal(params.get("resource_id"), resourceId);
  button(tree, "Reset filters").props.onClick();
  tree = h.render();
  await h.queries
    .find((q) => q.queryKey[0] === "audit-logs")
    .queryFn({ signal: null });
  params = new URL(h.calls[1][0], "http://local").searchParams;
  assert.equal(params.get("action"), null);
  assert.equal(params.get("resource_id"), null);
});

test("user lookup searches the full user directory and applies the selected user ID", async () => {
  const h = harness();
  let tree = h.render();
  field(tree, "Find user", "input").props.onChange({
    target: { value: "alice@example.edu" },
  });
  tree = h.render();
  button(tree, "Next users").props.onClick();
  tree = h.render();
  await h.queries
    .find((q) => q.queryKey[0] === "audit-user-options")
    .queryFn({ signal: null });
  let params = new URL(h.calls[0][0], "http://local").searchParams;
  assert.equal(params.get("search"), "alice@example.edu");
  assert.equal(params.get("offset"), "25");
  field(tree, "User", "select").props.onChange({ target: { value: userId } });
  tree = h.render();
  find(tree, (node) => node.type === "form").props.onSubmit(prevent);
  tree = h.render();
  await h.queries
    .find((q) => q.queryKey[0] === "audit-logs")
    .queryFn({ signal: null });
  params = new URL(h.calls[1][0], "http://local").searchParams;
  assert.equal(params.get("user_id"), userId);
});

test("failed loads show an error, not empty results, and non-admin queries stay disabled", () => {
  const failed = harness({ mode: "error" }),
    tree = failed.render();
  assert.ok(text(tree).includes("Could not load audit logs"));
  assert.equal(text(tree).includes("No events match"), false);
  assert.equal(
    text(find(tree, (node) => node.type === "table")).includes(
      "alice@example.edu",
    ),
    false,
  );
  const denied = harness({ role: "instructor" }),
    deniedTree = denied.render();
  assert.ok(text(deniedTree).includes("administrators only"));
  assert.ok(denied.queries.every((q) => q.enabled === false));
});

test("activity rows follow reference hierarchy and View opens full details without another API request", () => {
  const h = harness();
  let tree = h.render();
  const table = find(tree, (node) => node.type === "table");
  assert.ok(text(tree).includes("Activity history"));
  assert.ok(text(tree).includes("Newest first"));
  const headings = nodes(table)
    .filter((node) => node.type === "th")
    .map(text);
  assert.deepEqual(headings.slice(1), [
    "User",
    "Action",
    "Resource",
    "Severity",
    "Outcome",
    "Details",
  ]);
  assert.equal(
    find(table, (node) => node.type === "th").props["aria-sort"],
    "descending",
  );
  assert.ok(text(table).includes("09:00"));
  assert.ok(text(table).includes("user updated"));
  assert.ok(text(table).includes("user_updated"));
  assert.equal(text(table).includes("11111111…"), false);
  assert.equal(text(table).includes("22222222…"), false);
  assert.equal(text(table).includes('A "quoted", value'), false);
  assert.equal(
    nodes(table).some((node) => node.props?.title === resourceId),
    false,
  );
  button(tree, "View").props.onClick();
  tree = h.render();
  const dialog = find(tree, (node) => node.type === "Dialog");
  assert.equal(dialog.props.open, true);
  assert.ok(text(dialog).includes("Event details"));
  assert.ok(text(dialog).includes(resourceId));
  assert.ok(text(dialog).includes(userId));
  assert.equal(
    text(find(dialog, (node) => node.type === "li")),
    'Message: A "quoted", value',
  );
  assert.equal(
    nodes(dialog).some((node) => node.type === "pre"),
    false,
  );
  assert.equal(h.calls.length, 0);
  dialog.props.onOpenChange(false);
  tree = h.render();
  assert.equal(find(tree, (node) => node.type === "Dialog").props.open, false);
});

test("outcomes use existing theme badges and system events retain a useful empty-details view", () => {
  const h = harness({
    records: [
      {
        ...row("system"),
        user_id: null,
        user_email: null,
        resource_id: null,
        details: null,
        success: false,
      },
    ],
  });
  let tree = h.render();
  const table = find(tree, (node) => node.type === "table");
  assert.ok(text(table).includes("System / unknown"));
  assert.equal(text(table).includes("No user identity"), false);
  const outcome = find(
    table,
    (node) => node.type === "span" && text(node) === "Failed",
  );
  assert.match(outcome.props.className, /bg-destructive\/10 text-destructive/);
  const severity = find(
    table,
    (node) => node.type === "span" && text(node) === "info",
  );
  assert.match(severity.props.className, /bg-accent\/10 text-accent/);
  button(tree, "View").props.onClick();
  tree = h.render();
  assert.ok(
    text(find(tree, (node) => node.type === "Dialog")).includes(
      "No additional details.",
    ),
  );
});

test("audit metadata becomes readable points, including transitions, booleans, nested fields and lists", () => {
  const api = harness().load("lib/audit.ts");
  const details = {
    status: { from: "scheduled", to: "active" },
    automatic: true,
    changes: {
      is_trusted: false,
      risk_threshold: 0,
      device_name: 'My "phone"',
    },
    fields: ["scheduled_start", "course_id"],
    session_id: resourceId,
    risk_factors: [{ type: "device_unknown", weight: 0.2 }],
    review_notes: null,
    other: [],
    metadata: {},
  };
  const before = JSON.stringify(details);
  const points = Array.from(api.auditDetailPoints(details));
  assert.ok(points.includes("Status changed from Scheduled to Active."));
  assert.ok(points.includes("Automatic update: Yes"));
  assert.ok(points.includes("Changes · Trusted: No"));
  assert.ok(points.includes("Changes · Risk threshold: 0"));
  assert.ok(points.includes('Changes · Device name: My "phone"'));
  assert.ok(points.includes("Updated fields: Scheduled start, Course ID"));
  assert.ok(points.includes(`Session ID: ${resourceId}`));
  assert.ok(points.includes("Risk factors · Item 1 · Type: Device unknown"));
  assert.ok(points.includes("Review notes: Not provided"));
  assert.ok(points.includes("Other: None"));
  assert.ok(points.includes("Metadata: None"));
  assert.equal(JSON.stringify(details), before);
  assert.equal(api.auditDetailPoints(null).length, 0);
  assert.equal(api.auditDetailPoints({}).length, 0);
});
