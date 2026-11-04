import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { test } from 'node:test';
import vm from 'node:vm';

const ts = createRequire(new URL('../module1-frontend/package.json', import.meta.url))('typescript');
const context = { exports: {} };
vm.runInNewContext(ts.transpileModule(readFileSync(new URL('../module1-frontend/features/camera/motionChallenge.ts', import.meta.url), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText, context);
const { MotionProgress, yawDegrees } = context.exports;
const vectors = JSON.parse(readFileSync(new URL('./random-motion-vectors.json', import.meta.url), 'utf8'));

function matrix(yaw) {
  const c = Math.cos(yaw*Math.PI/180), s = Math.sin(yaw*Math.PI/180);
  return { rows: 4, columns: 4, data: [c, 0, -s, 0, 0, 1, 0, 0, s, 0, c, 0, 0, 0, -40, 1] };
}

for (const vector of vectors) {
  test(`browser temporal rules: ${vector.name}`, () => {
    const progress = new MotionProgress(vector.spec);
    for (const [timestamp, ear, yaw] of vector.samples) progress.update(ear, yawDegrees(matrix(yaw)), timestamp);
    assert.equal(progress.complete, vector.passed);
    if (vector.passed) {
      assert.equal(progress.blinks, vector.spec.blink_target);
      assert.equal(progress.step, 2);
      assert.equal(progress.turnPassed, true);
    }
  });
}

test('head direction uses unmirrored camera matrices; preview mirroring is CSS only', () => {
  assert.ok(Math.abs(yawDegrees(matrix(25))-25) < 1e-8);
  assert.ok(Math.abs(yawDegrees(matrix(-25))+25) < 1e-8);
  const styles = readFileSync(new URL('../module1-frontend/app/globals.css', import.meta.url), 'utf8');
  assert.match(styles, /camera-preview video\{[^}]*transform:scaleX\(-1\)/);
});

test('missing, malformed and non-finite pose cannot complete guidance', () => {
  for (const value of [undefined, { rows: 4, columns: 4, data: [] }, { rows: 4, columns: 4, data: Array(16).fill(NaN) }]) {
    assert.throws(() => yawDegrees(value), /tracking is unavailable/);
  }
  assert.throws(() => new MotionProgress({ ...vectors[0].spec, version: 1 }), /version changed/);
});
