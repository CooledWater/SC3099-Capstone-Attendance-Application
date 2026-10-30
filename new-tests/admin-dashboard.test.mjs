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

// Execute component event handlers with controlled hooks and API responses.
// No application server, real accounts, or database writes are involved.
function harness({
  request = async () => ({}),
  query = () => [],
  queryState = () => ({}),
  confirm = true,
} = {}) {
  const states = [],
    cache = new Map(),
    calls = [],
    mutations = [],
    invalidations = [];
  let cursor = 0;
  function useState(initial) {
    const i = cursor++;
    if (!(i in states))
      states[i] = typeof initial === "function" ? initial() : initial;
    return [
      states[i],
      (value) => {
        states[i] = typeof value === "function" ? value(states[i]) : value;
      },
    ];
  }
  const hooks = {
    useState,
    useEffect() {},
    useMemo: (callback) => callback(),
    useRef: (value) => ({ current: value }),
  };
  const queryHooks = {
    useQuery: (options) => ({
      data: query(options.queryKey),
      isSuccess: true,
      isPending: false,
      isLoading: false,
      isError: false,
      refetch() {},
      ...queryState(options.queryKey),
    }),
    useQueryClient: () => ({
      invalidateQueries: async (options) => {
        invalidations.push(options.queryKey);
      },
    }),
    useMutation: (options) => ({
      isPending: false,
      isError: false,
      isSuccess: false,
      reset() {},
      mutate: (value) => {
        const pending = Promise.resolve()
          .then(() => options.mutationFn(value))
          .then((result) => options.onSuccess?.(result));
        mutations.push(pending);
      },
    }),
  };
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
      TextEncoder,
      window: { confirm: () => confirm },
      require(name) {
        if (name === "react") return hooks;
        if (name === "react/jsx-runtime") return jsx;
        if (name === "@tanstack/react-query") return queryHooks;
        if (name.endsWith("/api") || name === "./api") return { api };
        if (name.endsWith("/useSessionValue"))
          return { useSessionValue: (_key, initial) => useState(initial) };
        if (name.endsWith("/useDebouncedValue"))
          return { useDebouncedValue: (value) => value };
        if (name.endsWith("/session-permissions"))
          return load("lib/session-permissions.ts");
        if (name.endsWith("/admin")) return load("lib/admin.ts");
        if (name.endsWith("/password-policy"))
          return load("lib/password-policy.ts");
        if (name.endsWith("/time") || name === "./time")
          return load("lib/time.ts");
        if (name.endsWith("/session-calendar"))
          return load("lib/session-calendar.ts");
        if (name.endsWith("/attendance") || name === "./attendance")
          return {
            toRows: (rows) => rows,
            trendOf: () => [],
            statusText: {},
            fetchCourses() {},
            fetchSessions() {},
          };
        if (name === "./InstructorView") return { buildCourseStats: () => [] };
        if (name === "sonner") return { toast: { error() {}, success() {} } };
        return new Proxy({}, { get: (_target, key) => String(key) });
      },
    };
    vm.runInNewContext(compile(path), context);
    cache.set(path, context.exports);
    return context.exports;
  }
  return {
    load,
    calls,
    invalidations,
    reset() {
      states.length = 0;
    },
    render(component, props) {
      cursor = 0;
      return component(props);
    },
    async settle() {
      await Promise.all(mutations);
    },
  };
}
function nodes(tree) {
  if (!tree || typeof tree !== "object") return [];
  if (Array.isArray(tree)) return tree.flatMap(nodes);
  return [tree, ...nodes(tree.props?.children)];
}
const text = (tree) =>
  typeof tree === "string" || typeof tree === "number"
    ? String(tree)
    : Array.isArray(tree)
      ? tree.map(text).join("")
      : tree?.props
        ? text(tree.props.children)
        : "";
const find = (tree, predicate) => {
  const node = nodes(tree).find(predicate);
  assert.ok(node, "Expected control was rendered");
  return node;
};
const click = (tree, label) =>
  find(
    tree,
    (node) => node.type === "button" && text(node) === label,
  ).props.onClick();
const prevent = { preventDefault() {} };

test("admin session permission includes other owners; missing identity and read-only remain denied", () => {
  const { canManageSession } = harness().load("lib/session-permissions.ts");
  assert.equal(canManageSession("admin", "other", true), true);
  assert.equal(canManageSession("instructor", "other"), false);
  assert.equal(canManageSession("instructor", "instructor"), true);
  assert.equal(canManageSession(undefined, "other", true), false);
  assert.equal(canManageSession("ta", "other", true, true), false);
});

test("admin assignment candidates consume all pages and preserve cancellation", async () => {
  const controller = new AbortController();
  const h = harness({
    request: async (path) => ({
      items: [{ id: path.includes("offset=0") ? "first" : "second" }],
      total: 2,
    }),
  });
  const result = await h
    .load("lib/admin.ts")
    .fetchStaff("instructor", controller.signal);
  assert.equal(result.length, 2);
  assert.ok(
    h.calls.every(
      ([path, init]) =>
        path.includes("role=instructor") &&
        path.includes("is_active=true") &&
        init.signal === controller.signal,
    ),
  );
  assert.ok(h.calls[1][0].includes("offset=1"));
});

test("inactive courses paginate and an empty page terminates loading", async () => {
  const h = harness({
    request: async (path) => ({
      items: path.includes("offset=0") ? [{ id: "old" }] : [],
      total: 5,
    }),
  });
  const result = await h.load("lib/admin.ts").fetchAdminCourses(false);
  assert.equal(result.length, 1);
  assert.equal(h.calls.length, 2);
  assert.ok(h.calls.every(([path]) => path.includes("is_active=false")));
});

test("assignment writes encode IDs, clear instructor with null, and keep TA identifiers separate", async () => {
  const h = harness(),
    api = h.load("lib/admin.ts");
  await api.saveInstructor("course/one", "");
  await api.assignTA("course/one", "ta/one");
  await api.unassignTA("course/one", "ta/one");
  assert.equal(h.calls[0][0], "/courses/course%2Fone");
  assert.deepEqual(JSON.parse(h.calls[0][1].body), { instructor_id: null });
  assert.deepEqual(JSON.parse(h.calls[1][1].body), { user_id: "ta/one" });
  assert.equal(h.calls[2][0], "/admin/courses/course%2Fone/tas/ta%2Fone");
  assert.equal(h.calls[2][1].method, "DELETE");
});

test("admin tabs reuse all-course roster workflow and enable foreign-owned session management", () => {
  const course = {
    id: "foreign",
    instructor_id: "someone-else",
    code: "SC3099",
  };
  const h = harness({ query: (key) => (key[0] === "courses" ? [course] : []) });
  const Component = h.load("components/dashboard/AdminView.tsx").AdminView;
  let tree = h.render(Component, { userId: "admin" });
  const tabs = find(tree, (node) => node.type === "Tabs");
  assert.ok(tabs.props.tabs.some((tab) => tab.id === "courses"));
  assert.ok(tabs.props.tabs.some((tab) => tab.id === "users"));
  tabs.props.onChange("sessions");
  tree = h.render(Component, { userId: "admin" });
  const sessions = find(tree, (node) => node.type === "SessionsPanel");
  assert.equal(sessions.props.isAdmin, true);
  assert.equal(sessions.props.currentUserId, "admin");
  sessions.props.onViewSession({ id: "foreign-session", course_id: "foreign" });
  tree = h.render(Component, { userId: "admin" });
  const roster = find(tree, (node) => node.type === "CheckInsPanel").props
    .instructor;
  assert.equal(roster.courses[0].id, "foreign");
  assert.equal(roster.initialSessionId, "foreign-session");
  assert.equal(roster.userId, "admin");
});

test("today's admin KPI uses the system-wide aggregate, including zero, rather than loaded rows", () => {
  for (const total of [245, 0]) {
    const h = harness({
      query: (key) => {
        if (key[0] === "admin-overview")
          return { total_checkins_today: total, timezone: "Asia/Singapore" };
        if (key[0] === "check-ins")
          return [{ id: "historical", status: "approved", risk: 0 }];
        return [];
      },
    });
    const Component = h.load("components/dashboard/AdminView.tsx").AdminView;
    const tree = h.render(Component, { userId: "admin" });
    const card = find(tree, (node) => node.props?.label === "Check-ins today");
    assert.equal(card.props.value, String(total));
    assert.equal(card.props.note, "Across all courses · All statuses");
    assert.equal(card.props.scope, "Today");
    card.props.onClick();
    const panel = find(
      h.render(Component, { userId: "admin" }),
      (node) => node.type === "AdminCheckIns",
    );
    assert.equal(panel.props.initialFilter.today, true);
    assert.equal(panel.props.initialFilter.statuses, undefined);
  }
});

test("today's admin KPI never substitutes historical rows when statistics are unavailable", () => {
  const h = harness({
    query: (key) => {
      if (key[0] === "admin-overview") return undefined;
      if (key[0] === "check-ins")
        return [{ id: "historical", status: "approved", risk: 0 }];
      return [];
    },
  });
  const tree = h.render(
    h.load("components/dashboard/AdminView.tsx").AdminView,
    { userId: "admin" },
  );
  const card = find(tree, (node) => node.props?.label === "Check-ins today");
  assert.equal(card.props.value, "—");
  assert.equal(card.props.note, "Loading today's total…");
});

test("every admin KPI opens cross-course check-ins while the normal tab keeps the session roster", () => {
  for (const label of [
    "Check-ins today",
    "Needs review",
    "High-risk check-ins",
  ]) {
    const courses = [
      { id: "one", instructor_id: "someone-else", code: "SC1" },
      { id: "two", instructor_id: "another-instructor", code: "SC2" },
    ];
    const h = harness({
      query: (key) => (key[0] === "courses" ? courses : []),
    });
    const Component = h.load("components/dashboard/AdminView.tsx").AdminView;
    let tree = h.render(Component, { userId: "admin" });
    find(tree, (node) => node.props?.label === label).props.onClick();
    tree = h.render(Component, { userId: "admin" });
    let panel = find(tree, (node) => node.type === "AdminCheckIns");
    assert.equal(panel.props.courses, courses);
    assert.equal(panel.props.userId, "admin");
    assert.ok(panel.props.initialFilter);
    if (label === "Needs review")
      assert.deepEqual(Array.from(panel.props.initialFilter.statuses), [
        "flagged",
        "appealed",
      ]);
    if (label === "High-risk check-ins")
      assert.equal(panel.props.initialFilter.minRisk, 0.5);
    find(tree, (node) => node.type === "Tabs").props.onChange("overview");
    tree = h.render(Component, { userId: "admin" });
    find(tree, (node) => node.props?.label === label).props.onClick();
    tree = h.render(Component, { userId: "admin" });
    find(tree, (node) => node.type === "Tabs").props.onChange("checkins");
    tree = h.render(Component, { userId: "admin" });
    panel = find(tree, (node) => node.type === "CheckInsPanel");
    assert.equal(panel.props.instructor.courses, courses);
  }
});

test("today shortcut leaves the saved session roster and opens all-course check-in results", () => {
  const courses = [{ id: "old-course" }, { id: "today-course" }];
  const sessions = [
    {
      id: "old-session",
      course_id: "old-course",
      status: "closed",
      starts_at: new Date(Date.now() - 40 * 86400000).toISOString(),
    },
    {
      id: "today-session",
      course_id: "today-course",
      status: "active",
      starts_at: new Date().toISOString(),
    },
  ];
  const h = harness({
    query: (key) =>
      key[0] === "courses" ? courses : key[0] === "sessions" ? sessions : [],
  });
  const Component = h.load("components/dashboard/AdminView.tsx").AdminView;
  let tree = h.render(Component, { userId: "admin" });
  find(tree, (node) => node.type === "Tabs").props.onChange("sessions");
  tree = h.render(Component, { userId: "admin" });
  find(tree, (node) => node.type === "SessionsPanel").props.onViewSession(
    sessions[0],
  );
  tree = h.render(Component, { userId: "admin" });
  find(tree, (node) => node.type === "Tabs").props.onChange("overview");
  tree = h.render(Component, { userId: "admin" });
  find(tree, (node) => node.props?.label === "Check-ins today").props.onClick();
  tree = h.render(Component, { userId: "admin" });
  const panel = find(tree, (node) => node.type === "AdminCheckIns");
  assert.equal(panel.props.sessions, sessions);
  assert.equal(panel.props.courses, courses);
  assert.equal(panel.props.initialFilter.today, true);
});

test("today's admin KPI offers retry when its aggregate fails to load", () => {
  let retries = 0;
  const h = harness({
    query: (key) => (key[0] === "admin-overview" ? undefined : []),
    queryState: (key) =>
      key[0] === "admin-overview"
        ? {
            isError: true,
            refetch() {
              retries += 1;
            },
          }
        : {},
  });
  const tree = h.render(
    h.load("components/dashboard/AdminView.tsx").AdminView,
    { userId: "admin" },
  );
  const card = find(tree, (node) => node.props?.label === "Check-ins today");
  assert.equal(card.props.value, "—");
  assert.equal(card.props.note, "Today's total unavailable");
  assert.ok(
    text(find(tree, (node) => node.props?.role === "alert")).includes(
      "Could not refresh overview statistics.",
    ),
  );
  click(tree, "Retry");
  assert.equal(retries, 1);
});

test("admin can edit and close foreign-owned sessions without allowing unrelated instructors", async () => {
  const start = new Date(Date.now() + 86400000).toISOString();
  const rows = [
    {
      id: "scheduled",
      course_id: "c",
      instructor_id: "owner",
      status: "scheduled",
      name: "Future",
      room: "LT1",
      starts_at: start,
      ends_at: new Date(Date.parse(start) + 3600000).toISOString(),
      checkin_opens_at: start,
      checkin_closes_at: new Date(Date.parse(start) + 3600000).toISOString(),
      geofence_radius_m: 100,
    },
    {
      id: "active",
      course_id: "c",
      instructor_id: "owner",
      status: "active",
      name: "Live",
      starts_at: start,
      ends_at: start,
    },
  ];
  const query = (key) =>
    key[0] === "sessions"
      ? rows
      : key[0] === "venues"
        ? { items: [{ code: "LT1", name: "LT1" }] }
        : [];
  const h = harness({
    query,
    request: async (path) =>
      path.endsWith("scheduled") ? { course_id: "c" } : { status: "closed" },
  });
  const Component = h.load(
    "components/dashboard/SessionsPanel.tsx",
  ).SessionsPanel;
  const props = {
    rows: [],
    canCreate: true,
    currentUserId: "admin",
    isAdmin: true,
    assignedCourses: [{ id: "c", instructor_id: "owner" }],
  };
  let tree = h.render(Component, props);
  find(
    tree,
    (node) => node.type === "DropdownMenuItem" && text(node) === "Edit",
  ).props.onSelect();
  tree = h.render(Component, props);
  const form = find(tree, (node) => node.props?.id === "edit-session-form");
  assert.equal(
    find(form, (node) => node.type === "fieldset").props.disabled,
    false,
  );
  await form.props.onSubmit(prevent);
  assert.equal(h.calls[0][0], "/sessions/scheduled");
  assert.equal(h.calls[0][1].method, "PATCH");
  find(
    tree,
    (node) =>
      node.type === "DropdownMenuItem" && text(node) === "Close session",
  ).props.onSelect();
  await new Promise((resolve) => setImmediate(resolve));
  assert.deepEqual(JSON.parse(h.calls[1][1].body), { status: "closed" });
  const other = harness({ query });
  const denied = other.render(
    other.load("components/dashboard/SessionsPanel.tsx").SessionsPanel,
    { ...props, isAdmin: false, currentUserId: "unrelated" },
  );
  assert.equal(
    nodes(denied).some(
      (node) => node.type === "DropdownMenuItem" && text(node) === "Edit",
    ),
    false,
  );
});

test("device controls submit rename, trust, activation and removal independently", async () => {
  const device = {
    id: "d/1",
    device_name: "Old",
    device_fingerprint: "123",
    user_email: "student@example.edu",
    is_active: true,
    is_trusted: false,
  };
  const h = harness({ query: () => ({ items: [device], total: 1 }) });
  const Component = h.load(
    "components/dashboard/DeviceApprovals.tsx",
  ).DeviceApprovals;
  let tree = h.render(Component, { userId: "admin" });
  click(tree, "Approve device");
  click(tree, "Deactivate");
  click(tree, "Remove");
  find(
    tree,
    (node) => node.props?.["aria-label"] === "Edit device name: Old",
  ).props.onDoubleClick();
  tree = h.render(Component, { userId: "admin" });
  find(tree, (node) => node.props?.["aria-label"] === "Device name").props.onChange({
    target: { value: " New " },
  });
  tree = h.render(Component, { userId: "admin" });
  find(tree, (node) => node.type === "form").props.onSubmit(prevent);
  await h.settle();
  assert.ok(h.calls.every(([path]) => path === "/devices/d%2F1"));
  assert.deepEqual(JSON.parse(h.calls[0][1].body), { is_trusted: true });
  assert.deepEqual(JSON.parse(h.calls[1][1].body), { is_active: false });
  assert.equal(h.calls[2][1].method, "DELETE");
  assert.deepEqual(JSON.parse(h.calls[3][1].body), { device_name: "New" });
});

test("cancelled device confirmations never send a mutation", async () => {
  const h = harness({
    confirm: false,
    query: () => ({
      items: [{ id: "d", device_fingerprint: "123", is_active: true }],
      total: 1,
    }),
  });
  const tree = h.render(
    h.load("components/dashboard/DeviceApprovals.tsx").DeviceApprovals,
    { userId: "admin" },
  );
  click(tree, "Remove");
  click(tree, "Deactivate");
  await h.settle();
  assert.equal(h.calls.length, 0);
});

test("user administration protects own role and sends confirmed changes for other accounts", async () => {
  const h = harness({
    query: () => ({
      items: [
        { id: "admin", email: "me@test.edu", role: "admin", is_active: true },
        { id: "other", email: "other@test.edu", role: "ta", is_active: true },
      ],
      total: 2,
    }),
  });
  const tree = h.render(
    h.load("components/dashboard/AdminUsers.tsx").AdminUsers,
    { userId: "admin" },
  );
  assert.equal(
    find(tree, (node) => node.props?.["aria-label"] === "Role for me@test.edu")
      .props.disabled,
    true,
  );
  find(
    tree,
    (node) => node.props?.["aria-label"] === "Role for other@test.edu",
  ).props.onChange({ target: { value: "instructor" } });
  await h.settle();
  assert.equal(h.calls[0][0], "/users/other");
  assert.deepEqual(JSON.parse(h.calls[0][1].body), { role: "instructor" });
});

test("admin calendar allows foreign session edits and moves while read-only and other instructors remain locked", async () => {
  const week = Date.parse("2030-10-21T00:00:00+08:00");
  const row = {
    id: "foreign",
    instructor_id: "owner",
    course_id: "c",
    status: "scheduled",
    name: "Lecture",
    starts_at: "2030-10-21T10:00:00+08:00",
    ends_at: "2030-10-21T11:00:00+08:00",
    checkin_opens_at: "2030-10-21T10:00:00+08:00",
    checkin_closes_at: "2030-10-21T11:00:00+08:00",
  };
  for (const [isAdmin, readOnly, allowed] of [
    [true, false, true],
    [false, false, false],
    [true, true, false],
  ]) {
    const h = harness({ query: () => [row] });
    const edits = [];
    const props = {
      userId: "viewer",
      courseId: "all",
      week,
      onWeekChange() {},
      onCreate() {},
      onEdit: (item) => edits.push(item.id),
      isAdmin,
      readOnly,
    };
    const tree = h.render(
      h.load("components/dashboard/SessionCalendar.tsx").SessionCalendar,
      props,
    );
    const block = find(
      tree,
      (node) => node.props?.["data-session-id"] === "foreign",
    );
    assert.equal(block.props.draggable, allowed);
    block.props.onClick();
    assert.equal(edits.length, allowed ? 1 : 0);
    const slot = find(tree, (node) => node.props?.["data-calendar-slot"]);
    slot.props.onDrop({
      preventDefault() {},
      dataTransfer: { getData: () => "foreign" },
    });
    const next = h.render(
      h.load("components/dashboard/SessionCalendar.tsx").SessionCalendar,
      props,
    );
    assert.equal(
      Boolean(find(next, (node) => node.type === "AlertDialog").props.open),
      allowed,
    );
  }
});

test("course management uses admin creation and staff assignments without filtering by current admin", async () => {
  const course = {
    id: "foreign",
    code: "SC3099",
    name: "Capstone",
    semester: "S1",
    instructor_id: "teacher",
    instructor_name: "Teacher",
    is_active: true,
  };
  const teacher = {
    id: "teacher",
    full_name: "Teacher",
    email: "teacher@example.edu",
  };
  const ta = {
    id: "ta",
    user_id: "ta",
    full_name: "Assistant",
    email: "ta@example.edu",
    is_active: true,
  };
  const h = harness({
    query: (key) =>
      key[0] === "admin-courses"
        ? [course]
        : key[0] === "admin-course-tas"
          ? { items: [ta] }
          : key[2] === "instructor"
            ? [teacher]
            : [],
  });
  const root = h.render(
    h.load("components/dashboard/AdminCourses.tsx").AdminCourses,
    { userId: "admin" },
  );
  const child = find(
    root,
    (node) =>
      typeof node.type === "function" && node.type.name === "CourseStaff",
  );
  h.reset();
  let tree = h.render(child.type, child.props);
  find(
    tree,
    (node) => node.type === "select" && node.props.value === "teacher",
  ).props.onChange({ target: { value: "" } });
  tree = h.render(child.type, child.props);
  const instructorForm = find(
    tree,
    (node) => node.type === "form" && text(node).includes("Save changes"),
  );
  instructorForm.props.onSubmit(prevent);
  click(tree, "Remove TA");
  await h.settle();
  assert.equal(h.calls[0][0], "/courses/foreign");
  assert.deepEqual(JSON.parse(h.calls[0][1].body), {
    name: "Capstone",
    semester: "S1",
    instructor_id: null,
  });
  assert.equal(h.calls[1][0], "/admin/courses/foreign/tas/ta");
  assert.equal(h.calls[1][1].method, "DELETE");
});

test("user creation respects the shared password policy and reports per-user API failures", async () => {
  const h = harness({
    query: () => ({ items: [], total: 0 }),
    request: async () => ({
      created: 0,
      errors: [{ error: "Email already registered" }],
    }),
  });
  const Root = h.load("components/dashboard/AdminUsers.tsx").AdminUsers;
  let tree = h.render(Root, { userId: "admin" });
  click(tree, "Create user");
  tree = h.render(Root, { userId: "admin" });
  const child = find(
    tree,
    (node) =>
      typeof node.type === "function" && node.type.name === "CreateUser",
  );
  h.reset();
  const draw = () => h.render(child.type, child.props);
  tree = draw();
  const inputs = nodes(tree).filter((node) => node.type === "input");
  inputs[0].props.onChange({ target: { value: " New User " } });
  tree = draw();
  find(
    tree,
    (node) => node.type === "input" && node.props.type === "email",
  ).props.onChange({ target: { value: "new@example.edu" } });
  tree = draw();
  assert.equal(
    find(tree, (node) => node.type === "button" && text(node) === "Save user")
      .props.disabled,
    true,
  );
  find(
    tree,
    (node) => node.type === "input" && node.props.type === "password",
  ).props.onChange({ target: { value: "ValidPassword!" } });
  tree = draw();
  assert.equal(
    find(tree, (node) => node.type === "button" && text(node) === "Save user")
      .props.disabled,
    false,
  );
  find(tree, (node) => node.type === "form").props.onSubmit(prevent);
  await assert.rejects(h.settle(), /Email already registered/);
  assert.equal(h.calls[0][0], "/admin/users/bulk");
  assert.equal(JSON.parse(h.calls[0][1].body).users[0].full_name, "New User");
});

test("one course save combines all fields, ignores pristine submissions and confirms instructor changes only", async () => {
  for (const scenario of ["details", "combined", "cancel"]) {
    const course = {
      id: "c",
      code: "SC3099",
      name: "Old",
      semester: "S1",
      instructor_id: "teacher",
      is_active: true,
    };
    const h = harness({
      confirm: scenario === "combined",
      query: (key) =>
        key[0] === "admin-courses"
          ? [course]
          : key[0] === "admin-course-tas"
            ? { items: [] }
            : [{ id: "teacher" }, { id: "new-teacher" }],
    });
    const root = h.render(
      h.load("components/dashboard/AdminCourses.tsx").AdminCourses,
      { userId: "admin" },
    );
    const child = find(
      root,
      (node) =>
        typeof node.type === "function" && node.type.name === "CourseStaff",
    );
    h.reset();
    const draw = () => h.render(child.type, child.props);
    let tree = draw();
    const save = (value) =>
      find(
        value,
        (node) => node.type === "button" && text(node) === "Save changes",
      );
    assert.equal(
      nodes(tree).filter(
        (node) => node.type === "button" && text(node).startsWith("Save"),
      ).length,
      1,
    );
    assert.equal(save(tree).props.disabled, true);
    find(
      tree,
      (node) => node.type === "form" && text(node).includes("Save changes"),
    ).props.onSubmit(prevent);
    await h.settle();
    assert.equal(h.calls.length, 0);
    find(
      tree,
      (node) => node.type === "input" && node.props.value === "Old",
    ).props.onChange({ target: { value: " Updated " } });
    tree = draw();
    find(
      tree,
      (node) => node.type === "input" && node.props.value === "S1",
    ).props.onChange({ target: { value: " S2 " } });
    tree = draw();
    if (scenario !== "details") {
      find(
        tree,
        (node) => node.type === "select" && node.props.value === "teacher",
      ).props.onChange({ target: { value: "new-teacher" } });
      tree = draw();
    }
    assert.equal(save(tree).props.disabled, false);
    find(
      tree,
      (node) => node.type === "form" && text(node).includes("Save changes"),
    ).props.onSubmit(prevent);
    await h.settle();
    if (scenario === "cancel") assert.equal(h.calls.length, 0);
    else {
      assert.equal(h.calls.length, 1);
      assert.equal(h.calls[0][0], "/courses/c");
      assert.equal(h.calls[0][1].method, "PUT");
      assert.deepEqual(JSON.parse(h.calls[0][1].body), {
        name: "Updated",
        semester: "S2",
        instructor_id: scenario === "combined" ? "new-teacher" : "teacher",
      });
    }
  }
});

test("device owner column shows the name above a smaller email, with an explicit missing-name fallback", () => {
  const h = harness({
    query: () => ({
      items: [
        {
          id: "named",
          user_name: "Alice Tan",
          user_email: "alice@example.edu",
          device_fingerprint: "one",
          is_active: true,
        },
        {
          id: "unknown",
          user_name: null,
          user_email: "other@example.edu",
          device_fingerprint: "two",
          is_active: false,
        },
      ],
      total: 2,
    }),
  });
  const tree = h.render(
    h.load("components/dashboard/DeviceApprovals.tsx").DeviceApprovals,
    { userId: "admin" },
  );
  const owner = find(
    tree,
    (node) => node.type === "td" && text(node).includes("Alice Tan"),
  );
  const spans = nodes(owner).filter((node) => node.type === "span");
  assert.equal(text(spans[0]), "Alice Tan");
  assert.equal(text(spans[1]), "alice@example.edu");
  assert.match(spans[1].props.className, /text-xs/);
  assert.match(spans[1].props.className, /block/);
  assert.ok(text(tree).includes("Unknown user"));
});

test("device names edit inline on double-click or keyboard; Escape, blank and unchanged names never save", async () => {
  const device = {
    id: "d",
    device_name: "Laptop",
    device_fingerprint: "123",
    is_active: true,
  };
  const h = harness({ query: () => ({ items: [device], total: 1 }) });
  const Component = h.load(
    "components/dashboard/DeviceApprovals.tsx",
  ).DeviceApprovals;
  const draw = () => h.render(Component, { userId: "admin" });
  let tree = draw();
  assert.equal(
    nodes(tree).some(
      (node) => node.type === "button" && text(node) === "Rename",
    ),
    false,
  );
  const nameButton = () =>
    find(
      tree,
      (node) => node.props?.["aria-label"] === "Edit device name: Laptop",
    );
  nameButton().props.onDoubleClick();
  tree = draw();
  const input = () =>
    find(
      tree,
      (node) =>
        node.type === "input" && node.props["aria-label"] === "Device name",
    );
  assert.equal(input().props.value, "Laptop");
  assert.equal(
    nodes(tree).some(
      (node) =>
        node.type === "td" &&
        nodes(node).some((child) => child.type === "input"),
    ),
    true,
  );
  input().props.onChange({ target: { value: "Not saved" } });
  tree = draw();
  input().props.onKeyDown({ key: "Escape", preventDefault() {} });
  tree = draw();
  assert.equal(
    nodes(tree).some((node) => node.props?.["aria-label"] === "Device name"),
    false,
  );
  nameButton().props.onKeyDown({ key: "F2", preventDefault() {} });
  tree = draw();
  assert.equal(input().props.value, "Laptop");
  input().props.onChange({ target: { value: "   " } });
  tree = draw();
  find(tree, (node) => node.type === "form").props.onSubmit(prevent);
  await h.settle();
  assert.equal(h.calls.length, 0);
  click(tree, "Cancel");
  tree = draw();
  nameButton().props.onKeyDown({ key: "Enter", preventDefault() {} });
  tree = draw();
  find(tree, (node) => node.type === "form").props.onSubmit(prevent);
  tree = draw();
  await h.settle();
  assert.equal(h.calls.length, 0);
  assert.equal(
    nodes(tree).some((node) => node.props?.["aria-label"] === "Device name"),
    false,
  );
});

test("inactive devices offer Reactivate and Remove as distinct actions", async () => {
  const h = harness({
    query: () => ({
      items: [
        {
          id: "d",
          device_name: "Laptop",
          device_fingerprint: "fingerprint",
          is_active: false,
          is_trusted: true,
        },
      ],
      total: 1,
    }),
  });
  const tree = h.render(
    h.load("components/dashboard/DeviceApprovals.tsx").DeviceApprovals,
    { userId: "admin" },
  );
  const remove = find(
    tree,
    (node) => node.type === "button" && text(node) === "Remove",
  );
  assert.equal(remove.props.disabled, false);
  assert.ok(text(tree).includes("Inactive"));
  assert.equal(
    nodes(tree).some(
      (node) => node.type === "button" && text(node) === "Disable",
    ),
    false,
  );
  click(tree, "Reactivate");
  click(tree, "Remove");
  await h.settle();
  assert.deepEqual(JSON.parse(h.calls[0][1].body), { is_active: true });
  assert.equal(h.calls[0][1].method, "PATCH");
  assert.equal(h.calls[1][1].method, "DELETE");
});

test("dashboard My devices hides removed registrations but retains temporarily inactive ones", async () => {
  const controller = new AbortController();
  const h = harness({
    request: async () => [
      { id: "active", is_active: true, is_removed: false },
      { id: "inactive", is_active: false, is_removed: false },
      { id: "removed", is_active: false, is_removed: true },
      { id: "legacy", is_active: true },
    ],
  });
  const result = await h
    .load("lib/devices.ts")
    .fetchMyDevices(controller.signal);
  assert.deepEqual(
    Array.from(result, (row) => row.id),
    ["active", "inactive", "legacy"],
  );
  assert.equal(h.calls[0][0], "/devices/my-devices");
  assert.equal(h.calls[0][1].signal, controller.signal);
});
