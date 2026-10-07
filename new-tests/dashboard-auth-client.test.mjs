import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { test } from "node:test";
import vm from "node:vm";

const require = createRequire(new URL("../module4-observability/package.json", import.meta.url));
const ts = require("typescript");
const source = readFileSync(new URL("../module4-observability/src/lib/api.ts", import.meta.url), "utf8")
  .replace('import.meta.env["VITE_API_BASE_URL"]', "undefined");
const javascript = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;

function storage() {
  const values = new Map();
  return { getItem: (key) => values.get(key) ?? null, setItem: (key, value) => values.set(key, value), removeItem: (key) => values.delete(key) };
}

function client(handler, local = storage()) {
  const calls = [];
  const context = { exports: {}, localStorage: local, sessionStorage: storage(), AbortController,
    window: { setTimeout, clearTimeout },
    fetch: async (url, init) => {
      const path = new URL(url).pathname.replace("/api/v1", "");
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
