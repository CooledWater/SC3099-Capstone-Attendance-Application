import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import vm from "node:vm";

const require = createRequire(new URL("../module4-observability/package.json", import.meta.url));
const ts = require("typescript");
const context = { exports: {} };
vm.runInNewContext(ts.transpileModule(
  readFileSync(new URL("../module4-observability/src/lib/course-label.ts", import.meta.url), "utf8"),
  { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } },
).outputText, context);
export const courseLabels = context.exports;
