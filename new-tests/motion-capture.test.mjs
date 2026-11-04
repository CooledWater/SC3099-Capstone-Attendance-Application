import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { test } from 'node:test';
import vm from 'node:vm';

const ts = createRequire(new URL('../module1-frontend/package.json', import.meta.url))('typescript');
const vectors = JSON.parse(readFileSync(new URL('./random-motion-vectors.json', import.meta.url), 'utf8'));
function compiled(path) {
  return ts.transpileModule(readFileSync(new URL(`../${path}`, import.meta.url), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
}

async function mount() {
  let time = 0, cursor = 0, enabled = true, detection, closed = false;
  const slots = [], effects = [], timers = new Map();
  let timerId = 0;
  const react = {
    useState(initial) {
      const index = cursor++;
      if (!(index in slots)) slots[index] = initial;
      return [slots[index], value => { slots[index] = value; }];
    },
    useRef(initial) {
      const index = cursor++;
      if (!(index in slots)) slots[index] = { current: initial };
      return slots[index];
    },
    useEffect(effect, deps) {
      const index = cursor++;
      if (!effects[index] || deps.some((value, position) => value !== effects[index].deps[position])) {
        effects[index]?.cleanup?.();
        effects[index] = { deps, cleanup: effect() };
      }
    },
  };
  const video = { current: { readyState: 2, videoWidth: 480, videoHeight: 480, currentTime: 1 } };
  const policyContext = { exports: {} };
  vm.runInNewContext(compiled('module1-frontend/features/camera/motionChallenge.ts'), policyContext);
  const context = {
    exports: {}, performance: { now: () => time },
    setTimeout: callback => { timers.set(++timerId, callback); return timerId; },
    clearTimeout: id => timers.delete(id),
    document: { createElement: () => ({ getContext: () => ({ drawImage() {} }), toDataURL: () => 'data:image/jpeg;base64,FRAME' }) },
    require: name => name === 'react' ? react : name === './motionChallenge' ? policyContext.exports : {
      FilesetResolver: { forVisionTasks: async () => ({}) },
      FaceLandmarker: { createFromOptions: async (files, options) => {
        assert.equal(options.outputFacialTransformationMatrixes, true);
        return { detectForVideo: () => detection, close: () => { closed = true; } };
      } },
    },
  };
  function output(ear = .3, yaw = 0, faces = 1) {
    const face = Array.from({ length: 478 }, () => ({ x: .5, y: .5, z: 0 }));
    for (const ids of [[33,160,158,133,153,144], [362,385,387,263,373,380]]) {
      for (let index = 0; index < ids.length; index++) face[ids[index]] = {
        x: index === 0 ? .3 : index === 3 ? .4 : .35,
        y: index === 1 || index === 2 ? .5-ear*.05 : index === 4 || index === 5 ? .5+ear*.05 : .5, z: 0,
      };
    }
    const c = Math.cos(yaw*Math.PI/180), s = Math.sin(yaw*Math.PI/180);
    return { faceLandmarks: Array(faces).fill(face), facialTransformationMatrixes: [{ rows: 4, columns: 4,
      data: [c,0,-s,0,0,1,0,0,s,0,c,0,0,0,-40,1] }] };
  }
  detection = output();
  vm.runInNewContext(compiled('module1-frontend/features/camera/useFaceGuidance.ts'), context);
  function render() { cursor = 0; return context.exports.useFaceGuidance(video, enabled); }
  render(); await new Promise(resolve => setImmediate(resolve));
  function tick(delta, next) {
    time += delta;
    if (next) { detection = next; video.current.currentTime++; }
    const [id, callback] = timers.entries().next().value;
    timers.delete(id); callback();
    return render();
  }
  return { render, output, tick, disable() { enabled = false; return render(); },
    unmount() { effects.forEach(effect => effect?.cleanup?.()); assert.equal(closed, true); assert.equal(timers.size, 0); } };
}

test('real capture hook records both actions and discards frames on retry/disable', async () => {
  const view = await mount();
  let hook = view.render();
  assert.equal(hook.ready, true, JSON.stringify({ error: hook.error, guidance: hook.guidance }));
  const vector = vectors.find(value => value.name === '2-right-head_turn');
  hook.start(vector.spec, new Date(Date.now()+60000).toISOString());
  for (const [, ear, yaw] of vector.samples) {
    hook = view.tick(80, view.output(ear, yaw));
    if (hook.frames.length) break;
  }
  assert.equal(hook.error, '');
  assert.equal(hook.completedSteps, 2);
  assert.equal(hook.blinks, 2);
  assert.ok(hook.frames.length >= 15);
  assert.equal(hook.recording, false);
  hook.cancel(); hook = view.render();
  assert.equal(hook.frames.length, 0);
  hook.start(vector.spec, new Date(Date.now()+60000).toISOString());
  hook = view.disable(); hook = view.render();
  assert.equal(hook.recording, false);
  assert.equal(hook.frames.length, 0);
  view.unmount();
});

for (const failure of ['frozen', 'multiple_faces', 'missing_pose']) {
  test(`real capture hook discards interrupted attempts: ${failure}`, async () => {
    const view = await mount();
    view.render().start(vectors[0].spec, new Date(Date.now()+60000).toISOString());
    const output = view.output(.3, 0, failure === 'multiple_faces' ? 2 : 1);
    if (failure === 'missing_pose') output.facialTransformationMatrixes = [];
    const hook = view.tick(failure === 'frozen' ? 400 : 80, failure === 'frozen' ? null : output);
    assert.ok(hook.error);
    assert.equal(hook.recording, false);
    assert.equal(hook.frames.length, 0);
    view.unmount();
  });
}
