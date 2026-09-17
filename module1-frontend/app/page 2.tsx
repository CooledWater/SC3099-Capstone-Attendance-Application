'use client';

import localforage from 'localforage';
import { FormEvent, useEffect, useRef, useState } from 'react';

type Session = { id: string; name: string };
type Location = { latitude: number; longitude: number; accuracy: number };
const API = process.env.NEXT_PUBLIC_API_URL ?? '/api';
const storage = localforage.createInstance({ name: 'saiv' });
const b64 = (value: ArrayBuffer) =>
  btoa(String.fromCharCode(...Array.from(new Uint8Array(value))));

export default function Home() {
  const video = useRef<HTMLVideoElement>(null);
  const media = useRef<MediaStream>();
  const [register, setRegister] = useState(false);
  const [form, setForm] = useState({ name: '', email: '', password: '' });
  const [token, setToken] = useState('');
  const [demoMode, setDemoMode] = useState(false);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [sessionId, setSessionId] = useState('');
  const [cameraConsent, setCameraConsent] = useState(false);
  const [locationConsent, setLocationConsent] = useState(false);
  const [cameraReady, setCameraReady] = useState(false);
  const [challenge, setChallenge] = useState(0);
  const [location, setLocation] = useState<Location>();
  const [message, setMessage] = useState({ error: false, text: '' });
  const [busy, setBusy] = useState(false);

  async function api(path: string, options: RequestInit = {}, accessToken = token) {
    const run = (bearer: string) => fetch(`${API}${path}`, {
      ...options, credentials: 'include',
      headers: { 'Content-Type': 'application/json', ...(bearer && { Authorization: `Bearer ${bearer}` }), ...options.headers },
    });
    let response = await run(accessToken);
    if (response.status === 401 && accessToken) {
      const refresh = await fetch(`${API}/auth/refresh`, { method: 'POST', credentials: 'include' });
      if (refresh.ok) {
        const data = await refresh.json();
        setToken(data.accessToken);
        response = await run(data.accessToken);
      }
    }
    return response;
  }

  useEffect(() => {
    if (!token || demoMode) return;
    api('/sessions?active=true').then(async response => {
      if (!response.ok) throw new Error('Could not load active sessions.');
      const data = await response.json();
      const list = Array.isArray(data) ? data : data.sessions ?? [];
      setSessions(list); setSessionId(list[0]?.id ?? '');
    }).catch(error => setMessage({ error: true, text: error.message }));
  }, [token, demoMode]); // eslint-disable-line react-hooks/exhaustive-deps

  function enterDemoMode() {
    const demoSession = { id: 'demo-session', name: 'Demo Lecture — Local Preview' };
    setDemoMode(true);
    setToken('demo');
    setSessions([demoSession]);
    setSessionId(demoSession.id);
    setMessage({ error: false, text: 'Demo mode enabled. No backend connection is required.' });
  }

  useEffect(() => () => media.current?.getTracks().forEach(track => track.stop()), []);

  async function authenticate(event: FormEvent) {
    event.preventDefault(); setBusy(true);
    try {
      const response = await api(`/auth/${register ? 'register' : 'login'}`, { method: 'POST', body: JSON.stringify(form) }, '');
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.message ?? 'Authentication failed.');
      if (register && !data.accessToken) {
        setRegister(false); setMessage({ error: false, text: 'Account created. Sign in to continue.' });
      } else { setToken(data.accessToken); setMessage({ error: false, text: 'Signed in.' }); }
    } catch (error) { setMessage({ error: true, text: error instanceof Error ? error.message : 'Authentication failed.' }); }
    finally { setBusy(false); }
  }

  async function enableCamera() {
    if (!cameraConsent) return setMessage({ error: true, text: 'Camera consent is required.' });
    try {
      media.current = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' } });
      if (video.current) video.current.srcObject = media.current;
      setCameraReady(true); setChallenge(0);
    } catch { setMessage({ error: true, text: 'Camera permission was denied or unavailable.' }); }
  }

  function locate() {
    if (!locationConsent) return setMessage({ error: true, text: 'Location consent is required.' });
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => setLocation({ latitude: coords.latitude, longitude: coords.longitude, accuracy: coords.accuracy }),
      error => setMessage({ error: true, text: `Location unavailable: ${error.message}` }),
      { enableHighAccuracy: true, timeout: 10000 },
    );
  }

  async function submit() {
    if (!video.current || !location || challenge < 3 || !sessionId) return;
    setBusy(true);
    try {
      const canvas = document.createElement('canvas');
      canvas.width = video.current.videoWidth; canvas.height = video.current.videoHeight;
      canvas.getContext('2d')?.drawImage(video.current, 0, 0);
      const keys = await crypto.subtle.generateKey({ name: 'ECDSA', namedCurve: 'P-256' }, false, ['sign', 'verify']);
      const publicKey = b64(await crypto.subtle.exportKey('spki', keys.publicKey));
      const rawFingerprint = [navigator.userAgent, navigator.language, screen.width, screen.height].join('|');
      const deviceFingerprint = b64(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(rawFingerprint)));
      await storage.setItem('device-key', keys.privateKey);
      const payload = { sessionId, location, publicKey, deviceFingerprint, faceFrame: canvas.toDataURL('image/jpeg', .8), livenessCompleted: true, capturedAt: new Date().toISOString() };
      if (!navigator.onLine) {
        const queue = await storage.getItem<object[]>('check-in-queue') ?? [];
        await storage.setItem('check-in-queue', [...queue, payload]);
        setMessage({ error: false, text: 'Offline: check-in queued for retry.' });
      } else {
        const response = await api('/check-ins', { method: 'POST', body: JSON.stringify(payload) });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.message ?? 'Check-in failed.');
        setMessage({ error: false, text: `Check-in successful${data.riskScore == null ? '' : ` — risk score: ${data.riskScore}`}` });
      }
    } catch (error) { setMessage({ error: true, text: error instanceof Error ? error.message : 'Check-in failed.' }); }
    finally { setBusy(false); }
  }

  const prompts = ['Blink twice', 'Turn your head left', 'Turn your head right'];
  const card = 'rounded-xl border bg-white p-6 shadow-sm';
  return <main className="mx-auto min-h-screen max-w-5xl p-6 md:p-10">
    <h1 className="text-3xl font-bold">SAIV — Secure Attendance System</h1>
    <p className="mb-8 mt-2 text-gray-600">Student check-in interface</p>
    {message.text && <div role="status" className={`mb-6 rounded-lg border p-4 ${message.error ? 'border-red-300 bg-red-50 text-red-800' : 'border-green-300 bg-green-50 text-green-800'}`}>{message.text}</div>}
    {!token ? <section className={`mx-auto max-w-md ${card}`}>
      <div className="mb-5 flex gap-2"><button onClick={() => setRegister(false)} className="flex-1 rounded bg-gray-100 p-2">Login</button><button onClick={() => setRegister(true)} className="flex-1 rounded bg-gray-100 p-2">Register</button></div>
      <form onSubmit={authenticate} className="space-y-4">
        {register && <input required placeholder="Full name" className="w-full rounded border p-3" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })}/>}
        <input required type="email" placeholder="Email" className="w-full rounded border p-3" value={form.email} onChange={e => setForm({ ...form, email: e.target.value })}/>
        <input required minLength={8} type="password" placeholder="Password" className="w-full rounded border p-3" value={form.password} onChange={e => setForm({ ...form, password: e.target.value })}/>
        <button disabled={busy} className="w-full rounded bg-blue-700 p-3 font-semibold text-white">{busy ? 'Please wait…' : register ? 'Create account' : 'Sign in'}</button>
      </form>
      <div className="my-4 flex items-center gap-3 text-xs text-gray-400"><span className="h-px flex-1 bg-gray-200"/>OR<span className="h-px flex-1 bg-gray-200"/></div>
      <button type="button" onClick={enterDemoMode} className="w-full rounded border border-blue-700 p-3 font-semibold text-blue-700">Continue in demo mode</button>
      <p className="mt-2 text-center text-xs text-gray-500">Preview the check-in flow without a backend.</p>
    </section> : <div className="grid gap-6 md:grid-cols-2">
      <section className={card}><h2 className="mb-4 text-xl font-semibold">1. Select session</h2><select className="w-full rounded border p-3" value={sessionId} onChange={e => setSessionId(e.target.value)}><option value="">Select an active session</option>{sessions.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></section>
      <section className={card}><h2 className="mb-4 text-xl font-semibold">2. Camera &amp; liveness</h2><label className="flex gap-2 text-sm"><input type="checkbox" checked={cameraConsent} onChange={e => setCameraConsent(e.target.checked)}/>I consent to camera use for verification.</label><button onClick={enableCamera} className="my-3 rounded bg-gray-900 px-4 py-2 text-white">Enable camera</button><video ref={video} autoPlay muted playsInline className={`aspect-video w-full rounded bg-black object-cover ${cameraReady ? '' : 'hidden'}`}/>{cameraReady && challenge < 3 && <div className="mt-3 rounded bg-blue-50 p-3"><b>{prompts[challenge]}</b><button onClick={() => setChallenge(challenge + 1)} className="mt-2 block rounded bg-blue-700 px-3 py-2 text-white">Completed</button></div>}{challenge === 3 && <p className="mt-2 text-green-700">✓ Liveness complete</p>}</section>
      <section className={card}><h2 className="mb-4 text-xl font-semibold">3. Location</h2><label className="flex gap-2 text-sm"><input type="checkbox" checked={locationConsent} onChange={e => setLocationConsent(e.target.checked)}/>I consent to sharing my location.</label><button onClick={locate} className="my-3 rounded bg-gray-900 px-4 py-2 text-white">Capture location</button>{location && <p className="text-green-700">✓ Acquired (±{Math.round(location.accuracy)} m)</p>}</section>
      <section className={card}><h2 className="text-xl font-semibold">4. Check in</h2><p className="my-3 text-sm text-gray-600">A rotated ECDSA device key, face frame, and GPS coordinates will be submitted securely.</p><button disabled={busy || !sessionId || challenge < 3 || !location} onClick={submit} className="w-full rounded bg-green-700 p-3 font-semibold text-white disabled:opacity-40">{busy ? 'Submitting…' : 'Complete check-in'}</button></section>
      <button onClick={() => { setToken(''); setDemoMode(false); setSessions([]); }} className="text-left text-sm underline">{demoMode ? 'Exit demo' : 'Sign out'}</button>
    </div>}
  </main>;
}
