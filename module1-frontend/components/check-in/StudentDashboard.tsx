'use client';
import { formatSingaporeDateTime, singaporeGreeting } from '@/lib/time';
import { AppLogo } from '@/components/AppLogo';

import { useEffect, useReducer, useState } from 'react';
import { useCamera } from '@/features/camera/useCamera';
import { FaceVerification, type FaceEvidence } from './FaceVerification';
import { useGeolocation } from '@/features/geolocation/useGeolocation';
import { getActiveSessions, getMySessionCheckIn, submitCheckIn } from '@/lib/api/checkins';
import { createDeviceProof } from '@/lib/device';
import { ApiError, isConnectivityError } from '@/lib/api/client';
import { SavedSessions } from './SavedSessions';
import { cacheActiveSessions, getCachedActiveSessions, type CachedActiveSessions } from '@/lib/offline/sessionCache';
import type { CheckIn, Session, User } from '@/types/api';

type Phase = 'camera' | 'preparing' | 'liveness' | 'review' | 'submitting' | 'result';
type Flow = { phase: Phase; result?: CheckIn };
type Action = { type: 'phase'; phase: Phase } | { type: 'result'; result: CheckIn } | { type: 'reset' };
const initialFlow: Flow = { phase: 'camera' };
function reducer(state: Flow, action: Action): Flow {
  if (action.type === 'reset') return initialFlow;
  if (action.type === 'phase') return { ...state, phase: action.phase };
  return { ...state, phase: 'result', result: action.result };
}

const demoSession: Session = { id: 'demo-session', course_code: 'SC3099', name: 'Capstone Project Seminar', status: 'active', scheduled_start: new Date().toISOString(), scheduled_end: new Date(Date.now() + 5400000).toISOString(), checkin_opens_at: new Date().toISOString(), checkin_closes_at: new Date(Date.now() + 1800000).toISOString(), venue_name: 'Innovation Lab', require_motion_check: true };

export function StudentDashboard({ user, demo, onLogout, onBusyChange, onOpenProfile, profileOpen, registrationError }: { user: User; demo: boolean; profileOpen: boolean; registrationError?: string; onLogout: () => void | Promise<void>; onBusyChange: (busy: boolean) => void; onOpenProfile: () => void }) {
  const [flow, dispatch] = useReducer(reducer, initialFlow);
  const [sessions, setSessions] = useState<Session[]>(demo ? [demoSession] : []);
  const [selectedId, setSelectedId] = useState(demo ? demoSession.id : '');
  const cameraConsent = user.camera_consent === true;
  const locationConsent = user.geolocation_consent === true;
  const consentReady = cameraConsent && locationConsent;
  const [evidence, setEvidence] = useState<FaceEvidence>({});
  const [notice, setNotice] = useState('');
  const [online, setOnline] = useState(true);
  const [signingOut, setSigningOut] = useState(false);
  const [snapshot, setSnapshot] = useState<CachedActiveSessions | null>(null);
  const [readOnly, setReadOnly] = useState(false);
  const [loadingSessions, setLoadingSessions] = useState(true);
  const [attendance, setAttendance] = useState<{ key: string; error?: string }>();
  const [attendanceRetry, setAttendanceRetry] = useState(0);
  const selected = sessions.find(item => item.id === selectedId);
  const requiresMotion = selected?.require_motion_check === true;
  const attendanceKey = `${user.id}:${selectedId}:${requiresMotion}`;
  const attendanceReady = demo || (!!selectedId && attendance?.key === attendanceKey && !attendance.error);
  const evidenceReady = demo || (requiresMotion
    ? !!evidence.motion_verification_id && !evidence.liveness_challenge_response
    : !!evidence.liveness_challenge_response && !evidence.motion_verification_id);
  const [retry, setRetry] = useState(0);
  const camera = useCamera(); const geo = useGeolocation();
  const stopCamera = camera.stop;
  const resetLocation = geo.reset;
  const requestLocation = geo.request;



  useEffect(() => {
    if (demo) { setLoadingSessions(false); return; }
    let cancelled = false;
    setLoadingSessions(true);
    async function load() {
      try {
        if (!navigator.onLine) throw new TypeError('Offline');
        const list = await getActiveSessions();
        if (cancelled) return;
        setSessions(list);
        setSelectedId(previous => list.some(item => item.id === previous) ? previous : list[0]?.id ?? '');
        setSnapshot(null); setReadOnly(false); setNotice('');
        void cacheActiveSessions(user.id, list).catch(() => undefined);
      } catch (error) {
        if (cancelled) return;
        // HTTP authorization/server errors must never be disguised as cached success.
        if ((!(error instanceof ApiError) && !navigator.onLine) || isConnectivityError(error)) {
          const cached = await getCachedActiveSessions(user.id).catch(() => null);
          if (!cancelled) { setSnapshot(cached); setReadOnly(true); }
        } else {
          setSessions([]); setSelectedId(''); setSnapshot(null); setReadOnly(false);
          setNotice(error instanceof Error ? error.message : 'Sessions could not be loaded.');
        }
      } finally { if (!cancelled) setLoadingSessions(false); }
    }
    void load();
    return () => { cancelled = true; };
  }, [demo, user.id, online, retry]);
  useEffect(() => {
    if (demo || !selectedId || !online || readOnly) return;
    let cancelled = false;
    stopCamera(); resetLocation(); setEvidence({}); dispatch({ type: 'reset' });
    setAttendance(undefined);
    void getMySessionCheckIn(selectedId).then(result => {
      if (cancelled) return;
      if (result) dispatch({ type: 'result', result });
      setAttendance({ key: attendanceKey });
    }).catch(error => {
      if (!cancelled) setAttendance({ key: attendanceKey, error: error instanceof Error ? error.message : 'Could not load your attendance.' });
    });
    return () => { cancelled = true; };
  }, [demo, selectedId, user.id, attendanceKey, online, readOnly, attendanceRetry, stopCamera, resetLocation]);

  useEffect(() => {
    const update = () => setOnline(navigator.onLine);
    update(); window.addEventListener('online', update); window.addEventListener('offline', update);
    return () => { window.removeEventListener('online', update); window.removeEventListener('offline', update); };
  }, []);
  useEffect(() => { if (camera.state !== 'ready') setEvidence({}); }, [camera.state]);
  useEffect(() => {
    if (flow.phase === 'preparing' && camera.state === 'ready' && geo.state === 'ready' && geo.point
        && consentReady && !profileOpen && !registrationError && (demo || (online && !readOnly))) {
      dispatch({ type: 'phase', phase: 'liveness' });
    }
    // Revoked location or stopped camera must never leave stale evidence usable.
    if (['liveness', 'review'].includes(flow.phase) && (geo.state !== 'ready' || camera.state !== 'ready')) {
      setEvidence({}); dispatch({ type: 'phase', phase: 'preparing' });
    }
  }, [flow.phase, camera.state, geo.state, geo.point, consentReady, profileOpen, registrationError, demo, online, readOnly]);

  useEffect(() => {
    if (!demo && (!online || readOnly)) { stopCamera(); resetLocation(); setEvidence({}); dispatch({ type: 'reset' }); }
  }, [demo, online, readOnly, stopCamera, resetLocation]);
  useEffect(() => {
    onBusyChange(signingOut || camera.state === 'requesting' || camera.state === 'ready' || !['camera', 'result'].includes(flow.phase));
    return () => onBusyChange(false);
  }, [signingOut, camera.state, flow.phase, onBusyChange]);

  useEffect(() => {
    if (!consentReady || profileOpen || registrationError) {
      stopCamera(); resetLocation(); setEvidence({});
      if (flow.phase !== 'result') dispatch({ type: 'reset' });
    }
  }, [consentReady, profileOpen, registrationError, flow.phase, stopCamera, resetLocation]);

  function prepareCheckIn() {
    if (!consentReady || profileOpen || registrationError || !attendanceReady || !selected || (!demo && (!online || readOnly || loadingSessions))) return;
    setNotice(''); setEvidence({});
    stopCamera(); resetLocation();
    dispatch({ type: 'phase', phase: 'preparing' });
    // The user starts both APIs once; the browser controls any required prompts.
    void camera.start();
    void requestLocation();
  }

  function cancelPreparation() {
    stopCamera(); resetLocation(); setEvidence({}); dispatch({ type: 'reset' });
  }

  async function completeCheckIn() {
    if (!consentReady || profileOpen || registrationError || !attendanceReady || !evidenceReady || !cameraReady || !selected || !geo.point || (!demo && (!navigator.onLine || readOnly || loadingSessions))) return;
    dispatch({ type: 'phase', phase: 'submitting' }); setNotice('');
    if (demo) {
      await new Promise(resolve => window.setTimeout(resolve, 700));
      camera.stop(); dispatch({ type: 'result', result: { id: 'demo-checkin', session_id: selected.id, status: 'approved', checked_in_at: new Date().toISOString(), risk_score: .08, liveness_passed: true } }); return;
    }
    try {
      const result = await submitCheckIn({ session_id: selected.id, latitude: geo.point.latitude, longitude: geo.point.longitude, location_accuracy_meters: geo.point.accuracy, ...await createDeviceProof(user.id, selected.id), ...evidence });
      setEvidence({}); camera.stop(); dispatch({ type: 'result', result });
    } catch (error) { dispatch({ type: 'phase', phase: 'review' }); setNotice(error instanceof Error ? error.message : 'Check-in failed.'); }
  }

  async function handleLogout() {
    if (signingOut) return;
    setSigningOut(true);
    setEvidence({}); camera.stop();
    try { await onLogout(); }
    finally { setSigningOut(false); }
  }

  const cameraProblem = camera.state === 'denied' ? 'Camera access is blocked. Allow it in your browser site settings, then retry.' : camera.state === 'unsupported' ? 'Camera access requires HTTPS or localhost and a supported browser.' : camera.state === 'unavailable' ? 'No usable camera was found. Check that another app is not using it.' : '';
  const geoProblem = geo.state === 'denied' ? 'Location access is blocked. Allow precise location in site settings, then retry.' : geo.state === 'timeout' ? 'Location timed out. Move near a window and retry.' : geo.state === 'unsupported' ? 'Location requires HTTPS or localhost and a supported browser.' : geo.state === 'unavailable' ? 'Your location could not be determined. Please retry.' : '';
  const cameraReady = camera.state === 'ready';
  const status = flow.result?.status;

  if (!demo && (!online || readOnly)) return <SavedSessions snapshot={snapshot} online={online} loading={loadingSessions} onRetry={() => setRetry(value => value + 1)} onExit={() => void handleLogout()}/>;

  return <div className="app-shell">
    <header className="topbar"><a className="logo" href="#"><AppLogo size={44}/><span>CCDS Attendance</span></a><div className="account"><span><b>{user.full_name}</b><small>{demo ? 'Demo student' : user.email}</small></span><button disabled={signingOut || flow.phase === 'submitting'} onClick={onOpenProfile}>Profile</button><button disabled={signingOut} onClick={handleLogout}>{signingOut ? 'Signing out…' : 'Sign out'}</button></div></header>
    <main className="dashboard">
      <section className="welcome"><div><span className="eyebrow">STUDENT CHECK-IN</span><h1>Good {singaporeGreeting()}, {user.full_name.split(' ')[0]}</h1><p>Complete the verification steps while your session is open.</p></div><span className="online"><i/> {online ? 'Online' : 'Offline — check-in unavailable'}</span></section>
      {notice && <div className="alert danger" role="alert"><b>Unable to continue</b><span>{notice}</span></div>}
      {!online && <div className="alert warning" role="status"><b>You are offline</b><span>Attendance cannot be queued because it must be verified in real time.</span></div>}

      <div className="content-grid">
        <section className="session-card">
          <div className="session-heading"><span className="status-badge"><i/> CHECK-IN OPEN</span><span>Closes {selected ? formatSingaporeDateTime(selected.checkin_closes_at, { hour: '2-digit', minute: '2-digit' }) : '—'}</span></div>
          {sessions.length ? <><label className="select-label">Active session<select value={selectedId} onChange={e => { camera.stop(); resetLocation(); setEvidence({}); setSelectedId(e.target.value); dispatch({ type: 'reset' }); }} disabled={flow.phase === 'submitting'}>{sessions.map(item => <option key={item.id} value={item.id}>{item.course_code ? `${item.course_code} — ` : ''}{item.name}</option>)}</select></label><h2>{selected?.name}</h2><div className="session-meta"><span>◷ {selected && formatSingaporeDateTime(selected.scheduled_start, { hour: '2-digit', minute: '2-digit' })}</span><span>⌖ {selected?.venue_name ?? 'Venue unavailable'}</span></div></> : <div className="empty"><h2>No active sessions</h2><p>When an enrolled session opens, it will appear here.</p></div>}
        </section>

        <section className="verification-card">
          {!demo && (loadingSessions || (selectedId && !attendanceReady)) ? <div className="step-content" role="status">
            <h2>{attendance?.key === attendanceKey && attendance.error ? 'Attendance unavailable' : 'Checking your attendance…'}</h2>
            {attendance?.key === attendanceKey && attendance.error && <><p>{attendance.error}</p><button className="button" onClick={() => setAttendanceRetry(value => value + 1)}>Retry attendance check</button></>}
          </div> : <>

          {registrationError && flow.phase !== 'result' ? <div className="step-content" role="status"><h2>Device registration required</h2><p>{registrationError}</p><button className="button primary" onClick={onOpenProfile}>Manage devices in Profile</button></div> : !consentReady && flow.phase !== 'result' ? <div className="step-content" role="status"><h2>Permission required</h2><p>{!cameraConsent && !locationConsent ? 'Camera and location verification are' : !cameraConsent ? 'Camera verification is' : 'Location verification is'} blocked in your settings. Allow both to check in.</p><button className="button primary" onClick={onOpenProfile}>Open profile settings</button></div> : <>
          <div className="stepper" aria-label="Check-in progress">{['Prepare', 'Verify', 'Submit'].map((label, index) => { const active = flow.phase === 'camera' || flow.phase === 'preparing' ? 0 : flow.phase === 'liveness' ? 1 : 2; return <div className={index <= active || flow.phase === 'result' ? 'done' : ''} key={label}><span>{index < active || flow.phase === 'result' ? '✓' : index + 1}</span><small>{label}</small></div>; })}</div>

          {flow.phase === 'camera' && <div className="step-content"><span className="eyebrow">STEP 1 OF 3</span><h2>Ready to verify your attendance</h2><p>We’ll start your camera and obtain your current location, then continue to {requiresMotion ? 'the blink challenge' : 'your check-in photo'}. Your saved consent is remembered. Your browser may ask for access if needed.</p>{cameraProblem && <div className="inline-error">{cameraProblem}</div>}{geoProblem && <div className="inline-error">{geoProblem}</div>}<button className="button primary" disabled={!selected || loadingSessions || !consentReady} onClick={prepareCheckIn}>Proceed to check in</button></div>}

          {flow.phase === 'preparing' && <div className="step-content"><span className="eyebrow">STEP 1 OF 3</span><h2>Preparing your check-in</h2><p role="status" aria-live="polite">{cameraProblem || geoProblem ? 'Access needs your attention before verification can continue.' : 'Starting your camera and finding your current location…'}</p><div className="readiness"><span>{camera.state === 'ready' ? '✓ Camera ready' : 'Camera: waiting for access'}</span><span>{geo.state === 'ready' ? '✓ Current location ready' : 'Location: waiting for a fresh position'}</span></div>{cameraProblem && <div className="inline-error" role="alert">{cameraProblem}</div>}{geoProblem && <div className="inline-error" role="alert">{geoProblem}</div>}{(cameraProblem || geoProblem || camera.state === 'idle' || geo.state === 'idle') && <button className="button primary" onClick={prepareCheckIn}>Retry preparation</button>}<button className="button secondary" onClick={cancelPreparation}>Cancel</button></div>}
          {camera.state === 'ready' && <div className="camera-preview"><video ref={camera.videoRef} autoPlay muted playsInline/><span>Camera active</span></div>}
          {flow.phase === 'liveness' && selected && <>
            {cameraProblem && <div className="inline-error">{cameraProblem}</div>}
            {!cameraReady && <button className="button primary" onClick={camera.start}>Restart camera</button>}
            <FaceVerification key={`${selected.id}:${requiresMotion}`} videoRef={camera.videoRef} capture={camera.capture} cameraReady={cameraReady} session={selected} demo={demo} onComplete={value => { setEvidence(value); dispatch({ type: 'phase', phase: 'review' }); }}/>
          </>}
          {(flow.phase === 'review' || flow.phase === 'submitting') && <div className="step-content"><span className="eyebrow">STEP 3 OF 3</span><h2>Ready to check in</h2><button className="button" disabled={flow.phase === 'submitting'} onClick={() => { setEvidence({}); dispatch({ type: 'phase', phase: 'liveness' }); }}>Retake / repeat verification</button><div className="readiness"><span>{cameraReady ? '✓ Camera ready' : 'Camera stopped'}</span><span>✓ Location captured {geo.point && `(±${Math.round(geo.point.accuracy)} m)`}</span><span>{demo ? 'Demo capture complete' : evidenceReady ? requiresMotion ? '✓ Motion verified by server' : '✓ Photo captured for server verification' : 'Capture cleared — repeat verification'}</span></div>{geo.point && geo.point.accuracy > 100 && <div className="inline-error">Location accuracy is low. The backend may flag or reject this attempt.</div>}<button className="button primary" disabled={flow.phase === 'submitting' || !cameraReady || (!online && !demo) || !evidenceReady} onClick={completeCheckIn}>{flow.phase === 'submitting' ? 'Verifying securely…' : 'Submit check-in'}</button></div>}
          {flow.phase === 'result' && <div className={`result ${status}`}><div className="result-icon">{status === 'approved' ? '✓' : status === 'flagged' ? '!' : status === 'pending' ? '…' : '×'}</div><span className="eyebrow">CHECK-IN RESULT</span><h2>{status === 'approved' ? 'Attendance confirmed' : status === 'appealed' ? 'Appeal submitted' : status === 'flagged' ? 'Submitted for review' : status === 'pending' ? 'Verification pending' : 'Check-in rejected'}</h2><p>{status === 'approved' ? 'You are checked in. You may now close this page.' : status === 'appealed' ? 'Your appeal is awaiting instructor review.' : status === 'flagged' ? 'Your attendance was recorded and requires instructor review.' : status === 'pending' ? 'Your submission is still being processed.' : 'Your attendance could not be verified. Contact your instructor if you believe this is incorrect.'}</p><dl><div><dt>Check-in time</dt><dd>{flow.result && formatSingaporeDateTime(flow.result.checked_in_at, { timeStyle: 'medium' })}</dd></div><div><dt>Risk score</dt><dd>{flow.result?.risk_score.toFixed(2)}</dd></div></dl></div>}
          </>}
          </>}
        </section>
      </div>
    </main>
  </div>;
}
