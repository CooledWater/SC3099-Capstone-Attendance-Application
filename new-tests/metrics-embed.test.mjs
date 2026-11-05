import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import vm from "node:vm";
import { test } from "node:test";

const require = createRequire(new URL("../module4-observability/package.json", import.meta.url));
const ts = require("typescript");
const jsx = require("react/jsx-runtime");
const read = path => readFileSync(new URL(`../${path}`, import.meta.url), "utf8");
const source = read("module4-observability/src/components/dashboard/MetricsPanel.tsx");

function render(grafanaUrl, latencyState = {}, requestRateState = {}, errorRateState = {}) {
  const code = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 },
  }).outputText.replaceAll("import.meta.env", "buildEnv");
  const context = { exports: {}, buildEnv: { VITE_GRAFANA_URL: grafanaUrl }, require(name) {
    if (name === "react/jsx-runtime") return jsx;
    if (name === "@tanstack/react-query") return { useQuery: options =>
      options.queryKey[0] === "api-latency" ? { ...latencyState } :
      options.queryKey[0] === "api-request-rate" ? { ...requestRateState } :
      options.queryKey[0] === "api-error-rate" ? { ...errorRateState } : { data: [] } };
    if (name === "./KpiCard") return { KpiCard: "KpiCard" };
    if (name === "@/lib/api") return { api: {} };
    throw new Error(name);
  } };
  vm.runInNewContext(code, context);
  return context.exports.MetricsPanel();
}

function nodes(tree) {
  if (!tree || typeof tree !== "object") return [];
  if (Array.isArray(tree)) return tree.flatMap(nodes);
  return [tree, ...nodes(tree.props?.children)];
}

test("latency card uses Prometheus one-hour p95 and distinguishes unavailable data from zero", () => {
  for (const [state, expected] of [
    [{ data: { p95_ms: 250.7 } }, "251 ms"],
    [{ data: { p95_ms: 0 } }, "0 ms"],
    [{ data: { p95_ms: null } }, "No data"],
    [{ isPending: true }, "Loading…"],
    [{ isError: true, data: { p95_ms: 250 } }, "Unavailable"],
  ]) {
    const card = nodes(render(undefined, state)).find(node => node.type === "KpiCard" && node.props.label === "API p95 latency");
    assert.equal(card.props.value, expected);
    assert.equal(card.props.note, "across all endpoints, last 1h");
  }
});

test("request-rate card uses one-hour Prometheus rate and retains its mini chart", () => {
  for (const [state, expected] of [
    [{ data: { requests_per_hour: 360.4 } }, "360/h"],
    [{ data: { requests_per_hour: 0 } }, "0/h"],
    [{ data: { requests_per_hour: null } }, "No data"],
    [{ isPending: true }, "Loading…"],
    [{ isError: true, data: { requests_per_hour: 100 } }, "Unavailable"],
  ]) {
    const card = nodes(render(undefined, {}, state)).find(node => node.type === "KpiCard" && node.props.label === "Request rate");
    assert.equal(card.props.value, expected);
    assert.equal(card.props.note, "across all endpoints, last 1h");
    assert.deepEqual(Array.from(card.props.bars), [40, 62, 51, 78, 66, 100]);
  }
});

test("error-rate card uses one-hour Prometheus percentage and distinguishes missing data from zero", () => {
  for (const [state, expected] of [
    [{ data: { error_rate_percent: 2.54 } }, "2.5%"],
    [{ data: { error_rate_percent: 0 } }, "0.0%"],
    [{ data: { error_rate_percent: null } }, "No data"],
    [{ isPending: true }, "Loading…"],
    [{ isError: true, data: { error_rate_percent: 0 } }, "Unavailable"],
  ]) {
    const card = nodes(render(undefined, {}, {}, state)).find(node => node.type === "KpiCard" && node.props.label === "Error rate");
    assert.equal(card.props.value, expected);
    assert.equal(card.props.note, "5xx errors across all endpoints, last 1h");
  }
});

test("metrics embeds the existing Grafana dashboard without external navigation", () => {
  const tree = nodes(render());
  const frames = tree.filter(node => node.type === "iframe");
  assert.equal(frames.length, 1);
  const frame = frames[0];
  assert.equal(frame.props.title, "Grafana technical monitoring graphs");
  const url = new URL(frame.props.src);
  assert.equal(url.origin, "http://localhost:3001");
  assert.equal(url.pathname, "/d/saiv-technical/saiv-technical");
  assert.equal(url.searchParams.get("refresh"), "15s");
  assert.equal(url.searchParams.get("from"), "now-12h");
  assert.ok(url.searchParams.has("kiosk"));
  assert.equal(tree.some(node => node.type === "a"), false);
  assert.equal(tree.filter(node => node.type === "KpiCard").length, 3);
  assert.equal(tree.filter(node => node.type === "table").length, 1);
});

test("metrics supports a configured Grafana host and subpath without double slashes", () => {
  const frame = nodes(render("https://monitor.example.edu/grafana/")).find(node => node.type === "iframe");
  const url = new URL(frame.props.src);
  assert.equal(url.origin, "https://monitor.example.edu");
  assert.equal(url.pathname, "/grafana/d/saiv-technical/saiv-technical");
});

test("Grafana allows authenticated embedding with five panels and no check-in outcomes chart", () => {
  const compose = read("docker-compose.yml");
  assert.match(compose, /GF_SECURITY_ALLOW_EMBEDDING: "true"/);
  assert.doesNotMatch(compose, /GF_AUTH_ANONYMOUS_ENABLED:\s*["']?true/);
  const dashboard = JSON.parse(read("module4-observability/grafana/dashboards/saiv-technical.json"));
  assert.equal(dashboard.uid, "saiv-technical");
  assert.equal(dashboard.panels.length, 5);
  assert.ok(dashboard.panels.every(panel => panel.title !== "Check-in outcomes"));
  const risk = dashboard.panels.find(panel => panel.title === "Risk score distribution");
  assert.deepEqual(risk.targets.map(target => target.legendFormat), ["Low", "Medium", "High", "Critical"]);
  for (const [index, band] of ["low", "medium", "high", "critical"].entries()) {
    assert.equal(risk.targets[index].expr, `sum(increase(checkin_risk_level_total{band="${band}"}[1h]))`);
  }
  const datasource = read("module4-observability/grafana/provisioning/datasources.yml");
  const uid = datasource.match(/^\s+uid:\s*(\S+)/m)[1];
  assert.ok(dashboard.panels.every(panel => panel.datasource.uid === uid));
  assert.doesNotMatch(read("module4-observability/src/components/dashboard/InstructorView.tsx"), /MetricsPanel/);
});
