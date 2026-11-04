'use client';
// Render captured previews locally; never send them to an image optimizer.
/* eslint-disable @next/next/no-img-element */
import { useEffect, useRef, useState } from 'react';
import { useFaceGuidance } from '@/features/camera/useFaceGuidance';
import { enrollFace, startMotion, verifyMotion } from '@/lib/api/checkins';
import { getMe } from '@/lib/api/auth';
import type { CheckInRequest, Session, MotionChallenge } from '@/types/api';

export type FaceEvidence = Pick<CheckInRequest, 'liveness_challenge_response' | 'motion_verification_id'>;
export function FaceVerification({ videoRef, capture, cameraReady, session, demo, onComplete }: {
  videoRef: React.RefObject<HTMLVideoElement>; capture: () => string; cameraReady: boolean;
  session: Session; demo: boolean; onComplete: (evidence: FaceEvidence) => void;
}) {
  const face = useFaceGuidance(videoRef, cameraReady);
  const [enrolled, setEnrolled] = useState<boolean | null>(demo ? true : null);
  const [photo, setPhoto] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [challenge, setChallenge] = useState<MotionChallenge>();
  const motion = session.require_motion_check === true;
  const active = useRef(true);
  const captureEpoch = useRef(0);
  const needEnrollment = !enrolled && (motion || session.require_face_match);
  useEffect(() => {
    active.current = true;
    if (!demo) getMe().then(user => { if (active.current) setEnrolled(!!user.face_enrolled); }).catch(() => { if (active.current) setError('Could not load face enrollment. Reload to retry.'); });
    return () => { active.current = false; captureEpoch.current += 1; };
  }, [demo]);
  useEffect(() => {
    if (!cameraReady) { captureEpoch.current += 1; setPhoto(''); setChallenge(undefined); }
  }, [cameraReady]);

  async function enroll() {
    setBusy(true); setError('');
    try {
      // Verify saved consent without re-enabling permissions during enrollment.
      const me = await getMe();
      if (!me.camera_consent || !me.geolocation_consent) throw new Error('Camera and location verification are blocked. Enable them in Profile settings.');
      await enrollFace(photo);
      if (active.current) { setEnrolled(true); setPhoto(''); }
    } catch (cause) { if (active.current) setError(cause instanceof Error ? cause.message : 'Enrollment failed'); }
    finally { if (active.current) setBusy(false); }
  }
  async function start() {
    const epoch = captureEpoch.current;
    setError(''); setBusy(true); face.cancel(); setChallenge(undefined);
    try {
      if (demo) {
        const bits = crypto.getRandomValues(new Uint8Array(1))[0];
        face.start({ version: 2, blink_target: bits & 1 ? 1 : 2,
          turn_direction: bits & 2 ? 'left' : 'right', first_action: bits & 4 ? 'blink' : 'head_turn' },
        new Date(Date.now() + 180000).toISOString());
        return;
      }
      const me = await getMe(); if (!me.camera_consent || !me.geolocation_consent) throw new Error('Camera and location verification are blocked. Enable them in Profile settings.');
      const next = await startMotion(session.id);
      if (active.current && epoch === captureEpoch.current) {
        if (next.action !== 'random_motion' || next.max_duration_ms !== 8000 || next.max_frames !== 120) {
          throw new Error('Challenge version changed. Reload and start again.');
        }
        face.start(next.challenge, next.expires_at); setChallenge(next);
      }
    } catch (cause) { if (active.current) setError(cause instanceof Error ? cause.message : 'Could not start challenge'); }
    finally { if (active.current) setBusy(false); }
  }
  async function submitSequence() {
    const epoch = captureEpoch.current;
    if (!demo && (!challenge || !Number.isFinite(Date.parse(challenge.expires_at)) || Date.parse(challenge.expires_at) <= Date.now())) {
      face.cancel(); setChallenge(undefined); setError('Challenge expired. Start again.'); return;
    }
    setBusy(true); setError('');
    try {
      if (demo) { face.cancel(); onComplete({}); return; }
      const result = await verifyMotion(challenge!.challenge_id, face.frames);
      if (!active.current || epoch !== captureEpoch.current) return;
      face.cancel(); setChallenge(undefined);
      if (!result.passed || !result.verification_id || result.challenge_version !== 2
        || !result.turn_passed || result.completed_steps !== 2) {
        throw new Error('The server could not verify your face and requested actions. Please retry.');
      }
      onComplete({ motion_verification_id: result.verification_id });
    } catch (cause) {
      if (active.current) { face.cancel(); setChallenge(undefined); setError(cause instanceof Error ? cause.message : 'Verification failed; retry'); }
    } finally { if (active.current) setBusy(false); }
  }
  function takePhoto() {
    try { setPhoto(capture()); setError(''); } catch (cause) { setError(cause instanceof Error ? cause.message : 'Capture failed'); }
  }
  return <div className="step-content">
    <h2>{needEnrollment ? 'Set up face verification' : motion ? 'Follow the motion challenge' : 'Capture your check-in photo'}</h2>
    {needEnrollment && <p>Enroll once so future check-ins can match your face. Review your photo before confirming.</p>}
    <p role="status" aria-live="polite">{face.guidance}</p>
    {(error || face.error) && <div className="inline-error" role="alert">{error || face.error}</div>}
    {enrolled === null ? <p>Checking enrollment…</p> : needEnrollment || !motion ? <>
      {photo ? <><img src={`data:image/jpeg;base64,${photo}`} alt="Captured face for review" style={{ width: '100%', maxHeight: 300, objectFit: 'contain', borderRadius: 12 }}/><button className="button" disabled={busy} onClick={() => setPhoto('')}>Retake</button><button className="button primary" disabled={busy || !cameraReady} onClick={() => needEnrollment ? void enroll() : onComplete({ liveness_challenge_response: photo })}>{busy ? 'Enrolling…' : needEnrollment ? 'Confirm enrollment' : 'Use this photo'}</button></>
      : <button className="button primary" disabled={!cameraReady || busy} onClick={takePhoto}>Capture image</button>}
    </> : <>
      <p>Each attempt asks you to blink and turn your head in a random order. Follow each prompt and finish facing the camera.</p>
      <p role="status" aria-live="polite">{face.instruction || 'Start when your face is centred.'}</p>
      <p aria-live="polite">{face.completedSteps || 0} / 2 actions completed{face.frames.length ? ' — sequence ready for verification' : ''}</p>
      {face.recording && <p>{face.blinks} blink(s) detected · {face.remainingSeconds}s remaining</p>}
      {face.frames.length > 0 && <img src={`data:image/jpeg;base64,${face.frames[0].image}`} alt="First frame of captured motion sequence" style={{ width: '100%', maxHeight: 200, objectFit: 'contain' }}/>}
      {face.frames.length ? <><button className="button" disabled={busy} onClick={() => { face.cancel(); setChallenge(undefined); }}>Retry</button><button className="button primary" disabled={busy || !cameraReady} onClick={submitSequence}>{busy ? 'Verifying sequence…' : 'Verify this sequence'}</button></> : <button className="button primary" disabled={busy || face.recording || !face.ready} onClick={start}>{busy ? 'Starting…' : face.recording ? 'Capturing…' : 'Start challenge'}</button>}
      {face.recording && <button className="button" onClick={() => { face.cancel(); setChallenge(undefined); }}>Cancel capture</button>}
    </>}
  </div>;
}
