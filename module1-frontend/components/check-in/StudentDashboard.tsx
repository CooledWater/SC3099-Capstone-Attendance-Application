'use client';

import { useEffect, useReducer, useState } from 'react';
import { useCamera } from '@/features/camera/useCamera';
import { useGeolocation } from '@/features/geolocation/useGeolocation';
import { getActiveSessions, submitCheckIn } from '@/lib/api/checkins';
import { updateConsent } from '@/lib/api/auth';
import { createDeviceFingerprint } from '@/lib/device';
import type { CheckIn, Session, User } from '@/types/api';

type Phase = 'camera' | 'location' | 'liveness' | 'review' | 'submitting' | 'result';
type Flow = { phase: Phase; challenge: number; result?: CheckIn };
type Action = { type: 'phase'; phase: Phase } | { type: 'challenge' } | { type: 'result'; result: CheckIn } | { type: 'reset' };
const initialFlow: Flow = { phase: 'camera', challenge: 0 };
function reducer(state: Flow, action: Action): Flow {
  if (action.type === 'reset') return initialFlow;
  if (action.type === 'phase') return { ...state, phase: action.phase };
  if (action.type === 'challenge') return { ...state, challenge: Math.min(3, state.challenge + 1), phase: state.challenge >= 2 ? 'review' : 'liveness' };
  return { ...state, phase: 'result', result: action.result };
}

const demoSession: Session = { id: 'demo-session', course_code: 'SC3099', name: 'Capstone Project Seminar', status: 'active', scheduled_start: new Date().toISOString(), scheduled_end: new Date(Date.now() + 5400000).toISOString(), checkin_opens_at: new Date().toISOString(), checkin_closes_at: new Date(Date.now() + 1800000).toISOString(), venue_name: 'Innovation Lab' };

export function StudentDashboard({ user, demo, onLogout }: { user: User; demo: boolean; onLogout: () => void }) {
  const [flow, dispatch] = useReducer(reducer, initialFlow);
  const [sessions, setSessions] = useState<Session[]>(demo ? [demoSession] : []);
  const [selectedId, setSelectedId] = useState(demo ? demoSession.id : '');
  const [cameraConsent, setCameraConsent] = useState(false);
  const [locationConsent, setLocationConsent] = useState(false);
  const [notice, setNotice] = useState('');
  const [online, setOnline] = useState(true);
  const camera = useCamera(); const geo = useGeolocation();
  const selected = sessions.find(item => item.id === selectedId);

  useEffect(() => { if (!demo) getActiveSessions().then(list => { setSessions(list); setSelectedId(list[0]?.id ?? ''); }).catch(error => setNotice(error.message)); }, [demo]);
  useEffect(() => {
    const update = () => setOnline(navigator.onLine);
    update(); window.addEventListener('online', update); window.addEventListener('offline', update);
    return () => { window.removeEventListener('online', update); window.removeEventListener('offline', update); };
  }, []);
  useEffect(() => { if (camera.state === 'ready') dispatch({ type: 'phase', phase: 'location' }); }, [camera.state]);
  useEffect(() => { if (geo.state === 'ready') dispatch({ type: 'phase', phase: 'liveness' }); }, [geo.state]);

  async function completeCheckIn() {
    if (!selected || !geo.point) return;
    dispatch({ type: 'phase', phase: 'submitting' }); setNotice('');
    if (demo) {
      await new Promise(resolve => window.setTimeout(resolve, 700));
      camera.stop(); dispatch({ type: 'result', result: { id: 'demo-checkin', session_id: selected.id, status: 'approved', checked_in_at: new Date().toISOString(), risk_score: .08, liveness_passed: true } }); return;
    }
    try {
      await updateConsent(cameraConsent, locationConsent);
      const result = await submitCheckIn({ session_id: selected.id, latitude: geo.point.latitude, longitude: geo.point.longitude, location_accuracy_meters: geo.point.accuracy, device_fingerprint: await createDeviceFingerprint(), liveness_challenge_response: camera.capture() });
      camera.stop(); dispatch({ type: 'result', result });
    } catch (error) { dispatch({ type: 'phase', phase: 'review' }); setNotice(error instanceof Error ? error.message : 'Check-in failed.'); }
  }

  const cameraProblem = camera.state === 'denied' ? 'Camera access is blocked. Allow it in your browser site settings, then retry.' : camera.state === 'unsupported' ? 'Camera access requires HTTPS or localhost and a supported browser.' : camera.state === 'unavailable' ? 'No usable camera was found. Check that another app is not using it.' : '';
  const geoProblem = geo.state === 'denied' ? 'Location access is blocked. Allow precise location in site settings, then retry.' : geo.state === 'timeout' ? 'Location timed out. Move near a window and retry.' : geo.state === 'unsupported' ? 'Location requires HTTPS or localhost and a supported browser.' : geo.state === 'unavailable' ? 'Your location could not be determined. Please retry.' : '';
  const prompts = ['Blink naturally twice', 'Slowly turn your head left', 'Slowly turn your head right'];
  const status = flow.result?.status;

  return <div className="app-shell">
    <header className="topbar"><a className="logo" href="#"><span className="brand-mark small">S</span><span>SAIV</span></a><div className="account"><span><b>{user.full_name}</b><small>{demo ? 'Demo student' : user.email}</small></span><button onClick={() => { camera.stop(); onLogout(); }}>Sign out</button></div></header>
    <main className="dashboard">
      <section className="welcome"><div><span className="eyebrow">STUDENT CHECK-IN</span><h1>Good {new Date().getHours() < 12 ? 'morning' : new Date().getHours() < 18 ? 'afternoon' : 'evening'}, {user.full_name.split(' ')[0]}</h1><p>Complete the verification steps while your session is open.</p></div><span className="online"><i/> {online ? 'Online' : 'Offline — check-in unavailable'}</span></section>
      {notice && <div className="alert danger" role="alert"><b>Unable to continue</b><span>{notice}</span></div>}
      {!online && <div className="alert warning" role="status"><b>You are offline</b><span>Attendance cannot be queued because it must be verified in real time.</span></div>}

      <div className="content-grid">
        <section className="session-card">
          <div className="session-heading"><span className="status-badge"><i/> CHECK-IN OPEN</span><span>Closes {selected ? new Date(selected.checkin_closes_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '—'}</span></div>
          {sessions.length ? <><label className="select-label">Active session<select value={selectedId} onChange={e => { setSelectedId(e.target.value); dispatch({ type: 'reset' }); }} disabled={flow.phase === 'submitting'}>{sessions.map(item => <option key={item.id} value={item.id}>{item.course_code ? `${item.course_code} — ` : ''}{item.name}</option>)}</select></label><h2>{selected?.name}</h2><div className="session-meta"><span>◷ {selected && new Date(selected.scheduled_start).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span><span>⌖ {selected?.venue_name ?? 'Venue unavailable'}</span></div></> : <div className="empty"><h2>No active sessions</h2><p>When an enrolled session opens, it will appear here.</p></div>}
        </section>

        <section className="verification-card">
          <div className="stepper" aria-label="Check-in progress">{['Camera', 'Location', 'Verify', 'Submit'].map((label, index) => { const active = ['camera','location','liveness','review'].indexOf(flow.phase); return <div className={index <= active || flow.phase === 'result' ? 'done' : ''} key={label}><span>{index < active || flow.phase === 'result' ? '✓' : index + 1}</span><small>{label}</small></div>; })}</div>

          {flow.phase === 'camera' && <div className="step-content"><span className="eyebrow">STEP 1 OF 4</span><h2>Camera access</h2><p>We use a temporary camera frame to verify identity and liveness. Raw images are sent to the attendance service for immediate processing and are not saved on this device.</p><label className="consent"><input type="checkbox" checked={cameraConsent} onChange={e => setCameraConsent(e.target.checked)}/><span><b>I consent to camera verification</b><small>You can stop the camera at any time.</small></span></label>{cameraProblem && <div className="inline-error">{cameraProblem}</div>}<button className="button primary" disabled={!cameraConsent || camera.state === 'requesting'} onClick={camera.start}>{camera.state === 'requesting' ? 'Requesting access…' : cameraProblem ? 'Retry camera' : 'Allow camera access'}</button></div>}

          {camera.state === 'ready' && <div className="camera-preview"><video ref={camera.videoRef} autoPlay muted playsInline/><span>Camera active</span></div>}
          {flow.phase === 'location' && <div className="step-content"><span className="eyebrow">STEP 2 OF 4</span><h2>Confirm your location</h2><p>Your precise coordinates and accuracy are sent to the backend, which decides whether you are within the venue.</p><label className="consent"><input type="checkbox" checked={locationConsent} onChange={e => setLocationConsent(e.target.checked)}/><span><b>I consent to location verification</b><small>Location is collected only for this check-in.</small></span></label>{geoProblem && <div className="inline-error">{geoProblem}</div>}<button className="button primary" disabled={!locationConsent || geo.state === 'requesting'} onClick={geo.request}>{geo.state === 'requesting' ? 'Finding your location…' : geoProblem ? 'Retry location' : 'Share precise location'}</button></div>}
          {flow.phase === 'liveness' && <div className="step-content"><span className="eyebrow">STEP 3 OF 4</span><h2>Liveness challenge</h2><p>Follow the prompt while keeping your face centred. The backend—not this page—makes the final verification decision.</p><div className="challenge"><span>{flow.challenge + 1} / 3</span><b>{prompts[flow.challenge]}</b></div><button className="button primary" onClick={() => dispatch({ type: 'challenge' })}>Capture this step</button></div>}
          {(flow.phase === 'review' || flow.phase === 'submitting') && <div className="step-content"><span className="eyebrow">STEP 4 OF 4</span><h2>Ready to check in</h2><div className="readiness"><span>✓ Camera ready</span><span>✓ Location captured {geo.point && `(±${Math.round(geo.point.accuracy)} m)`}</span><span>✓ Challenge interaction captured</span></div>{geo.point && geo.point.accuracy > 100 && <div className="inline-error">Location accuracy is low. The backend may flag or reject this attempt.</div>}<button className="button primary" disabled={flow.phase === 'submitting' || (!online && !demo)} onClick={completeCheckIn}>{flow.phase === 'submitting' ? 'Verifying securely…' : 'Submit check-in'}</button></div>}
          {flow.phase === 'result' && <div className={`result ${status}`}><div className="result-icon">{status === 'approved' ? '✓' : status === 'flagged' ? '!' : status === 'pending' ? '…' : '×'}</div><span className="eyebrow">CHECK-IN RESULT</span><h2>{status === 'approved' ? 'Attendance confirmed' : status === 'flagged' ? 'Submitted for review' : status === 'pending' ? 'Verification pending' : 'Check-in rejected'}</h2><p>{status === 'approved' ? 'You are checked in. You may now close this page.' : status === 'flagged' ? 'Your attendance was recorded and requires instructor review.' : status === 'pending' ? 'Your submission is still being processed.' : 'Your attendance could not be verified. Contact your instructor if you believe this is incorrect.'}</p><dl><div><dt>Time</dt><dd>{flow.result && new Date(flow.result.checked_in_at).toLocaleTimeString()}</dd></div><div><dt>Risk score</dt><dd>{flow.result?.risk_score.toFixed(2)}</dd></div></dl></div>}
        </section>
      </div>
    </main>
  </div>;
}
