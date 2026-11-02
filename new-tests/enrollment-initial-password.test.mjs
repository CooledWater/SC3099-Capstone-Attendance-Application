import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
import { createRequire } from "node:module";
import vm from "node:vm";
import { test } from "node:test";
const require = createRequire(new URL("../module4-observability/package.json", import.meta.url));
const ts = require("typescript");
const source = readFileSync(new URL("../module4-observability/src/components/dashboard/EnrollmentsPanel.tsx", import.meta.url), "utf8");
const code = ts.transpileModule(source + "\nexport { AddStudents };", {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
}).outputText;
function nodes(node) {
  if (!node || typeof node !== "object") return [];
  if (Array.isArray(node)) return node.flatMap(nodes);
  return [node, ...nodes(node.props?.children)];
}
function text(node) {
  if (Array.isArray(node)) return node.map(text).join("");
  if (node && typeof node === "object") return text(node.props?.children);
  return node == null ? "" : String(node);
}
function harness(result) {
  const values = [], effects = [], calls = [];
  let cursor = 0;
  const context = { exports: {}, require(name) {
    if (name === "react/jsx-runtime") return require(name);
    if (name === "react") return {
      useState(initial) { const i = cursor++; if (!(i in values)) values[i] = initial; return [values[i], value => { values[i] = value; }]; },
      useRef(value) { const i = cursor++; if (!(i in values)) values[i] = { current: value }; return values[i]; },
      useEffect(callback) { effects.push(callback); },
    };
    if (name === "@/lib/enrollments") return {
      parseEnrollmentEmails: value => ({ emails: value.split("\n").filter(Boolean), invalid: [] }),
      bulkEnroll: async (...args) => { calls.push(args); return result; },
    };
    if (name.includes("/ui/")) return new Proxy({}, { get: (_, key) => key });
    return {};
  } };
  vm.runInNewContext(code, context);
  return {
    calls,
    render(open = true) {
      cursor = 0;
      const tree = context.exports.AddStudents({ course: { id: "course", code: "SC4000", name: "Course" }, open, setOpen() {}, refresh: async () => {} });
      effects.splice(0).forEach(effect => effect());
      return tree;
    },
  };
}
test("new student initial passwords appear beside their email and clear after closing", async () => {
  const password = "generated-only-for-new-student";
  const h = harness({ enrolled: 2, created: 1, details: [
    { email: "new@example.edu", status: "created", initial_password: password },
    { email: "existing@example.edu", status: "enrolled" },
  ] });
  nodes(h.render()).find(node => node.type === "button" && text(node) === "Bulk enrollment").props.onClick();
  let tree = h.render();
  nodes(tree).find(node => node.type === "textarea").props.onChange({ target: { value: "new@example.edu\nexisting@example.edu" } });
  nodes(tree).find(node => node.type === "input" && node.props.type === "checkbox").props.onChange({ target: { checked: true } });
  tree = h.render();
  await nodes(tree).find(node => node.type === "form").props.onSubmit({ preventDefault() {} });
  // The form deliberately starts its async handler without returning its promise.
  await new Promise(resolve => setTimeout(resolve, 0));
  tree = h.render();
  assert.equal(h.calls.length, 1);
  assert.equal(h.calls[0][2], true);
  const rows = nodes(tree).filter(node => node.type === "li");
  assert.match(text(rows[0]), new RegExp(password));
  assert.doesNotMatch(text(rows[1]), /Initial password/);
  assert.equal(nodes(tree).filter(node => node.type === "code").length, 1);
  assert.doesNotMatch(text(tree), /invitation|resend/i);
  h.render(false);
  assert.doesNotMatch(text(h.render()), new RegExp(password));
});
test("login and route registration no longer offer invitation setup", () => {
  const auth = readFileSync(new URL("../module4-observability/src/routes/auth.tsx", import.meta.url), "utf8");
  const routes = readFileSync(new URL("../module4-observability/src/routeTree.gen.ts", import.meta.url), "utf8");
  assert.doesNotMatch(auth, /invitation|setup-account/);
  assert.doesNotMatch(routes, /setup-account/);
  assert.equal(existsSync(new URL("../module4-observability/src/routes/setup-account.tsx", import.meta.url)), false);
});
