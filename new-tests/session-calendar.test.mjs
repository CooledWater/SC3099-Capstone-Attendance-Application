import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import vm from "node:vm";
import { test } from "node:test";
const require = createRequire(new URL("../module4-observability/package.json", import.meta.url));
const ts = require("typescript");
const compile = path => ts.transpileModule(readFileSync(new URL(`../module4-observability/src/${path}`, import.meta.url), "utf8"), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
function load(request = async () => ({})) {
  const time = { exports: {} }; vm.runInNewContext(compile("lib/time.ts"), time);
  const ctx = { exports: {}, Date, URLSearchParams, require(name) {
    if (name === "./time") return time.exports;
    if (name === "./api") return { api: { request } };
    if (name === "./attendance") return { toSessionRow: row => ({ ...row, starts_at: row.scheduled_start, ends_at: row.scheduled_end }) };
    throw new Error(name);
  } };
  vm.runInNewContext(compile("lib/session-calendar.ts"), ctx);
  return ctx.exports;
}
const row = (id, start, end, status = "scheduled") => ({ id, status, course_id: "c", starts_at: start, ends_at: end, checkin_opens_at: start, checkin_closes_at: end });
test("Singapore week boundaries include Sunday without UTC date drift", () => {
  const h = load();
  assert.equal(new Date(h.mondayOf(Date.parse("2026-10-18T23:30:00Z"))).toISOString(), "2026-10-18T16:00:00.000Z");
  assert.equal(new Date(h.mondayOf(Date.parse("2026-10-18T10:00:00Z"))).toISOString(), "2026-10-11T16:00:00.000Z");
});
test("overlap lanes keep all blocks visible and adjacent sessions share a lane", () => {
  const h = load(), day = Date.parse("2026-10-19T00:00:00+08:00");
  const rows = [row("a", "2026-10-19T10:00:00+08:00", "2026-10-19T11:00:00+08:00"), row("b", "2026-10-19T10:30:00+08:00", "2026-10-19T11:30:00+08:00"), row("c", "2026-10-19T11:30:00+08:00", "2026-10-19T12:30:00+08:00")];
  const blocks = h.layoutDay(rows, day);
  assert.equal(blocks.length, 3);
  assert.equal(blocks[0].lanes, 2); assert.equal(blocks[1].lanes, 2);
  assert.notEqual(blocks[0].lane, blocks[1].lane);
  assert.equal(blocks[2].lanes, 1);
});
test("overnight events are clipped to each day while retaining their identity", () => {
  const h = load(), rows = [row("night", "2026-10-23T23:30:00+08:00", "2026-10-24T01:00:00+08:00")];
  const friday = Date.parse("2026-10-23T00:00:00+08:00");
  assert.equal(h.layoutDay(rows, friday)[0].end, friday + h.DAY);
  assert.equal(h.layoutDay(rows, friday + h.DAY)[0].start, friday + h.DAY);
});
test("confirmed move payload preserves duration and check-in offsets and rejects active/past moves", () => {
  const h = load();
  const start = Date.now() + 7 * h.DAY;
  const r = row("a", new Date(start).toISOString(), new Date(start + 90 * 60000).toISOString());
  r.checkin_opens_at = new Date(start - 15 * 60000).toISOString();
  const payload = h.movePayload(r, start + h.DAY);
  assert.equal(Date.parse(payload.scheduled_end) - Date.parse(payload.scheduled_start), 90 * 60000);
  assert.equal(Date.parse(payload.scheduled_start) - Date.parse(payload.checkin_opens_at), 15 * 60000);
  assert.throws(() => h.movePayload({ ...r, status: "active" }, start + h.DAY), /Only Scheduled/);
  assert.throws(() => h.movePayload(r, Date.now() - 1), /future/);
});
test("weekday loading consumes all pages, passes cancellation and excludes weekend sessions", async () => {
  const calls = [], controller = new AbortController();
  const h = load(async (path, init) => {
    calls.push([path, init.signal]);
    const url = new URL(path, "http://local");
    const active = url.searchParams.get("status") === "active";
    const offset = Number(url.searchParams.get("offset"));
    const value = { id: active ? "active" : offset ? "weekend" : "overlap", course_id: "c", status: active ? "active" : "scheduled", scheduled_start: active ? "2026-10-21T10:00:00+08:00" : offset ? "2026-10-24T10:00:00+08:00" : "2026-10-18T23:00:00+08:00", scheduled_end: active ? "2026-10-21T11:00:00+08:00" : offset ? "2026-10-24T11:00:00+08:00" : "2026-10-19T01:00:00+08:00" };
    return { items: [value], total: active ? 1 : 2 };
  });
  const rows = await h.loadCalendarSessions("c", Date.parse("2026-10-19T00:00:00+08:00"), controller.signal);
  assert.equal(rows.length, 2); assert.equal(calls.length, 3);
  assert.ok(calls.every(([path, signal]) => path.includes("course_id=c") && signal === controller.signal));
  assert.ok(calls[1][0].includes("offset=1"));
});
