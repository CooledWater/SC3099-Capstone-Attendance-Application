import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { test } from 'node:test';
import vm from 'node:vm';

const ts = createRequire(new URL('../module1-frontend/package.json', import.meta.url))('typescript');
const jsx = (type, props, key) => ({ type, props, key });

// Exercise the real component handlers with isolated hooks and API transports.
// Camera/model accuracy and actual browser rendering are covered separately.
function mount(path, name, props, imports) {
  const slots = [], dependencies = [], cleanups = [];
  let cursor = 0, effects = [], tree;
  const react = {
    useState(initial) {
      const i = cursor++;
      if (!(i in slots)) slots[i] = typeof initial === 'function' ? initial() : initial;
      return [slots[i], value => { slots[i] = typeof value === 'function' ? value(slots[i]) : value; }];
    },
    useReducer(reducer, initial) {
      const [value, set] = react.useState(initial);
      return [value, action => set(previous => reducer(previous, action))];
    },
    useRef(initial) { return react.useState(() => ({ current: initial }))[0]; },
    useMemo(calculate) { return calculate(); },
    useEffect(effect, values) {
      const i = cursor++;
      if (!dependencies[i] || !values || values.some((value, index) => value !== dependencies[i][index])) {
        dependencies[i] = values;
        effects.push(() => { cleanups[i]?.(); cleanups[i] = effect(); });
      }
    },
  };
  const context = {
    exports: {}, navigator: { onLine: true },
    window: { addEventListener() {}, removeEventListener() {} },
    require: module => module === 'react' ? react : module === 'react/jsx-runtime'
      ? { jsx, jsxs: jsx, Fragment: 'fragment' } : imports[module] ?? {},
  };
  const compiled = ts.transpileModule(readFileSync(new URL(`../${path}`, import.meta.url), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  vm.runInNewContext(compiled, context);
  function render() {
    cursor = 0;
    tree = context.exports[name](props);
    const pending = effects; effects = [];
    pending.forEach(effect => effect());
    return tree;
  }
  async function settle() {
    for (let i = 0; i < 8; i++) { render(); await new Promise(resolve => setImmediate(resolve)); }
  }
  function* descendants(node) {
    if (!node || typeof node !== 'object') return;
    if (Array.isArray(node)) { for (const child of node) yield* descendants(child); return; }
    yield node;
    yield* descendants(node.props?.children);
  }
  const nodes = (node = tree) => descendants(node);
  function content(node) {
    if (node == null || typeof node === 'boolean') return '';
    if (Array.isArray(node)) return node.map(content).join('');
    return typeof node === 'object' ? content(node.props?.children) : String(node);
  }
  const text = (node = tree) => content(node);
  function find(predicate) {
    const found = [...nodes()].find(predicate);
    assert.ok(found, `Expected UI element: ${predicate}`);
    return found;
  }
  const button = label => find(node => node.type === 'button' && text(node) === label);
  const input = label => {
    const parent = find(node => node.type === 'label' && text(node).trim().startsWith(label));
    return [...nodes(parent)].find(node => node.type === 'input' || node.type === 'select');
  };
  return { render, settle, find, button, input, text, nodes };
}

function instructor() {
  const requests = [];
  const view = mount('module4-observability/src/components/dashboard/SessionsPanel.tsx', 'SessionsPanel', {
    rows: [], canCreate: true, currentUserId: 'instructor',
  }, {
    '@tanstack/react-query': {
      useQuery: ({ queryKey }) => ({ isSuccess: true, data: queryKey[0] === 'courses'
        ? [{ id: 'course', code: 'SC3099', instructor_id: 'instructor' }] : [] }),
      useQueryClient: () => ({ invalidateQueries() {} }),
    },
    '@/lib/api': { api: { request: async (path, options) => { requests.push({ path, body: JSON.parse(options.body) }); } } },
    '@/lib/time': {
      parseSingaporeDateTimeLocal: value => new Date(`${value}+08:00`),
      toSingaporeDateTimeLocal: value => new Date(value).toISOString().slice(0, 16),
    },
    '@/lib/session-calendar': { mondayOf: () => 0 },
    './SessionCalendar': { SessionCalendar: 'SessionCalendar' },
    sonner: { toast: { success() {}, error(message) { assert.fail(message); } } },
  });
  view.render();
  const change = (label, value) => { view.input(label).props.onChange({ target: { value } }); view.render(); };
  const open = () => { view.button('New session').props.onClick(); view.render(); };
  const allowPhoto = checked => { view.input('Allow single photo check-in').props.onChange({ target: { checked } }); view.render(); };
  const submit = async () => {
    change('Venue', 'Lecture Hall'); change('Starts at', '2099-06-01T10:00');
    await view.find(node => node.type === 'form').props.onSubmit({ preventDefault() {} });
    view.render();
  };
  return { ...view, requests, open, allowPhoto, submit };
}

for (const allowPhoto of [false, true]) {
  test(`instructor creation sends require_motion_check=${!allowPhoto}`, async () => {
    const view = instructor(); view.open();
    assert.equal(view.input('Allow single photo check-in').props.checked, false);
    view.allowPhoto(allowPhoto); await view.submit();
    assert.equal(view.requests.length, 1);
    assert.equal(view.requests[0].path, '/sessions/');
    assert.equal(view.requests[0].body.require_motion_check, !allowPhoto);
    view.open();
    assert.equal(view.input('Allow single photo check-in').props.checked, false);
  });
}

test('cancel/reopen and calendar creation reset the checkbox to unchecked', () => {
  const view = instructor(); view.open(); view.allowPhoto(true);
  view.button('Cancel').props.onClick(); view.render(); view.open();
  assert.equal(view.input('Allow single photo check-in').props.checked, false);
  view.allowPhoto(true);
  view.button('Calendar').props.onClick(); view.render();
  view.find(node => node.type === 'SessionCalendar').props.onCreate(Date.now() + 86400000);
  view.render();
  assert.equal(view.input('Allow single photo check-in').props.checked, false);
});

function verification(session, initiallyEnrolled = true) {
  const completed = [], calls = [];
  const frames = [{ image: 'sequence-frame', timestamp_ms: 0 }];
  const face = { guidance: 'Face centred', ready: true, recording: false, frames: [], blinks: 0,
    cancel() { face.frames = []; face.recording = false; },
    start() { face.frames = frames; face.blinks = 2; },
  };
  const view = mount('module1-frontend/components/check-in/FaceVerification.tsx', 'FaceVerification', {
    session: { id: 'session', ...session }, videoRef: { current: null }, cameraReady: true,
    capture: () => 'captured-photo', demo: false, onComplete: value => completed.push(value),
  }, {
    '@/features/camera/useFaceGuidance': { useFaceGuidance: () => face },
    '@/lib/api/auth': { getMe: async () => ({ face_enrolled: initiallyEnrolled, geolocation_consent: true }), updateConsent: async () => {} },
    '@/lib/api/checkins': {
      enrollFace: async image => { calls.push(['enroll', image]); },
      startMotion: async id => { calls.push(['start', id]); return { challenge_id: 'challenge', expires_at: new Date(Date.now() + 60000).toISOString() }; },
      verifyMotion: async (id, submitted) => { calls.push(['verify', id, submitted]); return { passed: true, verification_id: 'proof' }; },
    },
  });
  return { ...view, completed, calls };
}

for (const requireMotion of [false, undefined]) {
  test(`photo policy ${requireMotion} submits a photo without motion even when liveness is required`, async () => {
    const view = verification({ require_motion_check: requireMotion, require_liveness_check: true });
    await view.settle();
    assert.ok(view.text().includes('Capture your check-in photo'));
    assert.equal([...view.nodes()].filter(node => node.type === 'input' && node.props.type === 'checkbox').length, 0);
    view.button('Capture image').props.onClick(); view.render();
    view.button('Use this photo').props.onClick();
    assert.equal(view.completed[0].liveness_challenge_response, 'captured-photo');
    assert.equal(view.completed[0].motion_verification_id, undefined);
    assert.equal(view.calls.length, 0);
  });
}

test('motion policy shows only the two-blink flow and returns the server proof', async () => {
  const view = verification({ require_motion_check: true, require_liveness_check: false });
  await view.settle();
  assert.ok(view.text().includes('Blink twice'));
  assert.ok(!view.text().includes('Capture image'));
  assert.equal([...view.nodes()].filter(node => node.type === 'input').length, 0);
  await view.button('Start challenge').props.onClick(); view.render();
  await view.button('Verify this sequence').props.onClick();
  assert.equal(view.calls[0][0], 'start'); assert.equal(view.calls[1][0], 'verify');
  assert.equal(view.calls[1][2][0].image, 'sequence-frame');
  assert.equal(view.completed[0].motion_verification_id, 'proof');
  assert.equal(view.completed[0].liveness_challenge_response, undefined);
});

for (const requireMotion of [false, true]) {
  test(`one-time enrollment remains separate from attendance in ${requireMotion ? 'motion' : 'photo'} mode`, async () => {
    const view = verification({ require_motion_check: requireMotion, require_face_match: true }, false);
    await view.settle();
    assert.ok(view.text().includes('Set up face verification'));
    view.button('Capture image').props.onClick(); view.render();
    view.button('Confirm enrollment').props.onClick(); await view.settle();
    assert.equal(view.calls[0][0], 'enroll');
    assert.equal(view.completed.length, 0);
    assert.ok(view.text().includes(requireMotion ? 'Blink twice' : 'Capture your check-in photo'));
  });
}

async function student(requireMotion) {
  const submitted = [];
  const session = { id: 'session', name: 'Lecture', require_motion_check: requireMotion };
  const camera = { state: 'idle', stop() { camera.state = 'idle'; }, start() {}, capture() {} };
  const geo = { state: 'idle', point: undefined, reset() { geo.state = 'idle'; geo.point = undefined; } };
  const view = mount('module1-frontend/components/check-in/StudentDashboard.tsx', 'StudentDashboard', {
    user: { id: 'student', full_name: 'Student', email: 'student@example.test' }, demo: false,
    onLogout() {}, onBusyChange() {}, onOpenProfile() {},
  }, {
    './FaceVerification': { FaceVerification: 'FaceVerification' },
    '@/lib/time': { singaporeGreeting: () => 'morning', formatSingaporeDateTime: value => value },
    '@/features/camera/useCamera': { useCamera: () => camera },
    '@/features/geolocation/useGeolocation': { useGeolocation: () => geo },
    '@/lib/api/checkins': {
      getActiveSessions: async () => [session], getMySessionCheckIn: async () => undefined,
      submitCheckIn: async payload => { submitted.push(payload); return { id: 'checkin', status: 'approved', risk_score: 0 }; },
    },
    '@/lib/api/auth': { updateConsent: async () => {} },
    '@/lib/device': { createDeviceFingerprint: async () => 'device' },
    '@/lib/api/client': { ApiError: class extends Error {}, isConnectivityError: () => false },
    '@/lib/offline/sessionCache': { cacheActiveSessions: async () => {} },
  });
  await view.settle();
  camera.state = 'ready'; geo.state = 'ready'; geo.point = { latitude: 1, longitude: 103, accuracy: 10 };
  await view.settle();
  const complete = evidence => { view.find(node => node.type === 'FaceVerification').props.onComplete(evidence); view.render(); };
  return { ...view, submitted, session, camera, complete };
}

for (const requireMotion of [false, true]) {
  test(`review submits only matching ${requireMotion ? 'motion' : 'photo'} evidence`, async () => {
    const view = await student(requireMotion);
    const evidence = requireMotion ? { motion_verification_id: 'proof' } : { liveness_challenge_response: 'photo' };
    view.complete(evidence);
    assert.equal(view.button('Submit check-in').props.disabled, false);
    await view.button('Submit check-in').props.onClick();
    assert.equal(view.submitted.length, 1);
    assert.equal(view.submitted[0].motion_verification_id, evidence.motion_verification_id);
    assert.equal(view.submitted[0].liveness_challenge_response, evidence.liveness_challenge_response);
  });

  for (const evidence of [{}, { motion_verification_id: 'proof', liveness_challenge_response: 'photo' },
    requireMotion ? { liveness_challenge_response: 'photo' } : { motion_verification_id: 'proof' }]) {
    test(`review blocks missing/mixed/wrong evidence in ${requireMotion ? 'motion' : 'photo'} mode: ${JSON.stringify(evidence)}`, async () => {
      const view = await student(requireMotion); view.complete(evidence);
      assert.equal(view.button('Submit check-in').props.disabled, true);
      await view.button('Submit check-in').props.onClick();
      assert.equal(view.submitted.length, 0);
    });
  }
}

test('a changed session policy clears previously captured evidence', async () => {
  const view = await student(false);
  view.complete({ liveness_challenge_response: 'photo' });
  assert.equal(view.button('Submit check-in').props.disabled, false);
  view.session.require_motion_check = true;
  await view.settle();
  assert.equal(view.camera.state, 'idle');
  assert.ok(!view.text().includes('Photo captured for server verification'));
  assert.ok(!view.text().includes('Submit check-in'));
  assert.equal(view.submitted.length, 0);
});

test('stopping the camera prevents submission of an already captured photo', async () => {
  const view = await student(false);
  view.complete({ liveness_challenge_response: 'photo' });
  view.camera.state = 'idle';
  await view.settle();
  assert.equal(view.button('Submit check-in').props.disabled, true);
  await view.button('Submit check-in').props.onClick();
  assert.equal(view.submitted.length, 0);
});
