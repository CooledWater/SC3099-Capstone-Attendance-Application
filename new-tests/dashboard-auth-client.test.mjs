import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { test } from "node:test";
import vm from "node:vm";

const require = createRequire(new URL("../module4-observability/package.json", import.meta.url));
const ts = (() => {
  try { return require("typescript"); }
  catch { return createRequire(new URL("../module1-frontend/package.json", import.meta.url))("typescript"); }
})();
const source = readFileSync(new URL("../module4-observability/src/lib/api.ts", import.meta.url), "utf8")
  .replace('import.meta.env["VITE_API_BASE_URL"]', "undefined");
const javascript = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;

function storage() {
  const values = new Map();
  return { getItem: (key) => values.get(key) ?? null, setItem: (key, value) => values.set(key, value), removeItem: (key) => values.delete(key) };
}

function client(handler, local = storage(), timers = { setTimeout, clearTimeout }) {
  const calls = [];
  const context = { exports: {}, localStorage: local, sessionStorage: storage(), AbortController, Response,
    window: timers,
    fetch: async (url, init) => {
      const path = new URL(url, "http://localhost:8501").pathname.replace("/api/v1", "");
      calls.push(path);
      assert.equal(init.credentials, "include");
      return handler(path, init);
    },
  };
  vm.runInNewContext(javascript, context);
  return { ...context, api: context.exports.api, calls };
}

const ok = (body) => ({ status: 200, ok: true, json: async () => body });
const error = (status) => ({ status, ok: false, json: async () => ({ detail: "Rejected" }) });
const student = { id: "student", role: "student" };

for (const mode of ["json", "file"]) {
  test(`${mode} body remains protected by timeout after headers arrive`, async () => {
    let expire;
    let reading;
    const started = new Promise(resolve => { reading = resolve; });
    let cleared = false;
    const c = client((path, init) => {
      const body = () => {
        reading();
        return new Promise((resolve, reject) => init.signal.addEventListener("abort", () => reject(new Error("Body aborted")), { once: true }));
      };
      return { status: 200, ok: true, json: body, blob: body };
    }, storage(), { setTimeout: callback => { expire = callback; return 1; }, clearTimeout: () => { cleared = true; } });
    const pending = mode === "file" ? c.api.response("/export/attendance/course") : c.api.me();
    await started;
    assert.equal(cleared, false);
    expire();
    await assert.rejects(pending, failure => failure.status === 408 && /too long/.test(failure.message));
    assert.equal(cleared, true);
  });
}

test("file exports preserve response headers and binary body after authentication refresh", async () => {
  const response = { status: 200, ok: true, headers: new Map([["Content-Disposition", 'attachment; filename="attendance.csv"']]), blob: async () => "server bytes" };
  let attempts = 0;
  const c = client(path => path.endsWith("refresh") ? ok({ access_token: "renewed" }) : ++attempts === 1 ? error(401) : response);
  const file = await c.api.response("/export/attendance/course-a?format=csv");
  assert.equal(file.headers.get("Content-Disposition"), 'attachment; filename="attendance.csv"');
  assert.equal(await file.text(), "server bytes");
  assert.equal(attempts, 2);
});

test("CSV exports preserve backend contents and refresh authentication before retry", async () => {
  const csv = '\uFEFFstudent_id,student_name\r\n123,"Student, One"\r\n';
  let attempts = 0;
  const c = client((path, init) => {
    if (path.endsWith("refresh")) return ok({ access_token: "renewed" });
    assert.equal(path, "/export/session/session-123");
    assert.equal(init.headers.Accept, "text/csv");
    if (++attempts === 1) return error(401);
    assert.equal(init.headers.Authorization, "Bearer renewed");
    return { status: 200, ok: true, text: async () => csv };
  });
  assert.equal(await c.api.text("/export/session/session-123?format=csv"), csv);
  assert.equal(attempts, 2);
});

test("CSV export errors propagate without downloading error content", async () => {
  for (const status of [403, 404, 500]) {
    const c = client(() => error(status));
    await assert.rejects(c.api.text("/export/session/session-123?format=csv"),
      (failure) => failure.status === status && failure.message === "Rejected");
  }
});

test("restoration prefers the separate dashboard session", async () => {
  const c = client((path) => path.endsWith("refresh") ? ok({ access_token: "dashboard" }) : ok(student));
  assert.equal((await c.api.restoreSession()).id, "student");
  assert.deepEqual(c.calls, ["/auth/dashboard/refresh", "/users/me"]);
});

test("absent dashboard session tries the one-way student bridge", async () => {
  const c = client((path) => path.endsWith("refresh") ? error(401) : path.endsWith("student-session") ? ok({ access_token: "student" }) : ok(student));
  assert.equal((await c.api.restoreSession()).id, "student");
  assert.deepEqual(c.calls, ["/auth/dashboard/refresh", "/auth/dashboard/student-session", "/users/me"]);
});

test("staff bridge rejection leaves the dashboard signed out", async () => {
  const c = client((path) => error(path.endsWith("refresh") ? 401 : 403));
  assert.equal(await c.api.restoreSession(), null);
  assert.equal(c.calls.includes("/users/me"), false);
});

test("backend failure does not trigger an identity switch via the bridge", async () => {
  const c = client(() => error(503));
  await assert.rejects(c.api.restoreSession());
  assert.deepEqual(c.calls, ["/auth/dashboard/refresh"]);
});

test("concurrent restoration shares one request sequence", async () => {
  const c = client((path) => path.endsWith("refresh") ? ok({ access_token: "dashboard" }) : ok(student));
  await Promise.all([c.api.restoreSession(), c.api.restoreSession()]);
  assert.deepEqual(c.calls, ["/auth/dashboard/refresh", "/users/me"]);
});

test("401 refresh retries once using only the dashboard cookie", async () => {
  let reads = 0;
  const c = client((path) => path.endsWith("refresh") ? ok({ access_token: "renewed" }) : ++reads === 1 ? error(401) : ok(student));
  assert.equal((await c.api.me()).id, "student");
  assert.deepEqual(c.calls, ["/users/me", "/auth/dashboard/refresh", "/users/me"]);
});

test("failed refresh never falls back to another app during an API request", async () => {
  const c = client(() => error(401));
  await assert.rejects(c.api.me());
  assert.deepEqual(c.calls, ["/users/me", "/auth/dashboard/refresh"]);
});

test("dashboard logout suppresses automatic re-entry; explicit login resets it", async () => {
  const c = client((path) => path.endsWith("login") ? ok({ access_token: "new", user: student }) : ok({}));
  await c.api.logout();
  assert.equal(await c.api.restoreSession(), null);
  assert.deepEqual(c.calls, ["/auth/dashboard/logout"]);
  await c.api.login("student@example.com", "password");
  assert.equal(c.sessionStorage.getItem("saiv.dashboard.signed-out"), null);
  assert.equal(c.calls.at(-1), "/auth/dashboard/login");
});

test("failed logout still clears the local session and prevents auto-entry", async () => {
  const c = client((path, init) => {
    if (path.endsWith("login")) return ok({ access_token: "old", user: student });
    if (path.endsWith("logout")) return error(503);
    assert.equal(init.headers.Authorization, undefined);
    return ok(student);
  });
  await c.api.login("student@example.com", "password");
  await assert.rejects(c.api.logout());
  await c.api.me();
  assert.equal(await c.api.restoreSession(), null);
});

test("login sends the memory token without persisting credentials", async () => {
  const c = client((path, init) => {
    if (path.endsWith("login")) return ok({ access_token: "memory-only", refresh_token: "never-save", user: student });
    assert.equal(init.headers.Authorization, "Bearer memory-only");
    return ok(student);
  });
  await c.api.login("student@example.com", "password");
  await c.api.me();
  assert.equal(c.localStorage.getItem("saiv.dashboard.access-token"), null);
  assert.equal(c.localStorage.getItem("saiv.access-token"), null);
  assert.equal(c.sessionStorage.getItem("saiv.dashboard.access-token"), null);
});

test("reload loses the access token and restores it through the refresh cookie", async () => {
  const local = storage();
  const first = client(() => ok({ access_token: "before-reload", user: student }), local);
  await first.api.login("student@example.com", "password");
  const reloaded = client((path, init) => {
    if (path.endsWith("refresh")) {
      assert.equal(init.headers.Authorization, undefined);
      return ok({ access_token: "after-reload" });
    }
    assert.equal(init.headers.Authorization, "Bearer after-reload");
    return ok(student);
  }, local);
  assert.equal((await reloaded.api.restoreSession()).id, "student");
});

test("upgrade removes both old persisted access-token keys", () => {
  const local = storage();
  local.setItem("saiv.access-token", "legacy");
  local.setItem("saiv.dashboard.access-token", "previous");
  local.setItem("unrelated-setting", "keep");
  client(() => ok({}), local);
  assert.equal(local.getItem("saiv.access-token"), null);
  assert.equal(local.getItem("saiv.dashboard.access-token"), null);
  assert.equal(local.getItem("unrelated-setting"), "keep");
});
