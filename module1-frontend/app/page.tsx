'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import { AuthCard } from '@/components/auth/AuthCard';
import { StudentDashboard } from '@/components/check-in/StudentDashboard';
import { SavedSessions } from '@/components/check-in/SavedSessions';
import { PullToRefresh } from '@/components/PullToRefresh';
import { PwaUpdates } from '@/components/PwaUpdates';
import { AppLogo } from '@/components/AppLogo';
import { MyDevices } from '@/components/MyDevices';
import { registerCurrentDevice } from '@/lib/device';
import { PermissionSettings } from '@/components/PermissionSettings';
import { PwaInstall } from '@/components/PwaInstall';
import { getMe, logout } from '@/lib/api/auth';
import { ApiError, clearTokens, refreshAccessToken } from '@/lib/api/client';
import { clearOfflineSessions, getCachedActiveSessions, getOfflineAccount, setOfflineAccount, type CachedActiveSessions } from '@/lib/offline/sessionCache';
import type { User } from '@/types/api';

const demoUser: User = { id: 'demo-student', email: 'student@demo.local', full_name: 'Alex Tan', role: 'student' };

export default function Home() {
  const [user, setUser] = useState<User>();
  const [demo, setDemo] = useState(false);
  const [restoring, setRestoring] = useState(true);
  const [offlineView, setOfflineView] = useState(false);
  const [online, setOnline] = useState(true);
  const [snapshot, setSnapshot] = useState<CachedActiveSessions | null>(null);
  const [retry, setRetry] = useState(0);
  const [profileOpen, setProfileOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [deviceError, setDeviceError] = useState('');
  const [deviceRetry, setDeviceRetry] = useState(0);
  useEffect(() => {
    if (!user || demo || !online) return;
    let active = true;
    setDeviceError('');
    void registerCurrentDevice(user.id).then(device => { if (active && !device.is_active) setDeviceError('This device is disabled. Enable it under Profile → My devices before checking in.'); }).catch(cause => { if (active) setDeviceError(cause instanceof Error ? cause.message : 'Device registration failed.'); });
    return () => { active = false; };
  }, [user, demo, online, deviceRetry]);
  const signedOut = useRef(false);
  const authenticated = useCallback((account: User) => {
    signedOut.current = false;
    try { sessionStorage.removeItem('saiv.student.signed-out'); } catch { /* Storage is optional. */ }
    setOfflineAccount(account.id);
    setOfflineView(false);
    setSnapshot(null);
    setUser(account);
  }, []);

  useEffect(() => {
    const standalone = window.matchMedia('(display-mode: standalone)').matches
      || (navigator as Navigator & { standalone?: boolean }).standalone === true;
    if (standalone && window.location.pathname === '/') window.location.replace('/attendance');
  }, []);

  useEffect(() => {
    const changed = () => setOnline(navigator.onLine);
    changed();
    window.addEventListener('online', changed);
    window.addEventListener('offline', changed);
    return () => { window.removeEventListener('online', changed); window.removeEventListener('offline', changed); };
  }, []);

  useEffect(() => {
    if (user) return;
    try { signedOut.current = signedOut.current || sessionStorage.getItem('saiv.student.signed-out') === 'true'; } catch { /* Storage is optional. */ }
    if (signedOut.current) { setRestoring(false); return; }
    let cancelled = false;
    setRestoring(true);
    async function showSaved() {
      const owner = getOfflineAccount();
      const saved = owner ? await getCachedActiveSessions(owner).catch(() => null) : null;
      if (!cancelled) { setSnapshot(saved); setOfflineView(true); }
    }
    async function restore() {
      try {
        if (!navigator.onLine) { await showSaved(); return; }
        if (await refreshAccessToken(true)) {
          const account = await getMe();
          if (!cancelled) authenticated(account);
        } else {
          await clearOfflineSessions().catch(() => undefined);
          if (!cancelled) { setOfflineView(false); setSnapshot(null); }
        }
      } catch (error) {
        if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
          await clearOfflineSessions().catch(() => undefined);
          if (!cancelled) { setOfflineView(false); setSnapshot(null); }
        } else await showSaved();
      } finally { if (!cancelled) setRestoring(false); }
    }
    void restore();
    return () => { cancelled = true; };
  }, [user, online, retry, authenticated]);

  async function signOut() {
    signedOut.current = true;
    try { sessionStorage.setItem('saiv.student.signed-out', 'true'); } catch { /* Storage is optional. */ }
    // Remove offline access before waiting for a backend logout request.
    await clearOfflineSessions().catch(() => undefined);
    if (navigator.onLine && !demo) await logout();
    else clearTokens();
    setProfileOpen(false); setDemo(false); setOfflineView(false); setSnapshot(null); setUser(undefined); setBusy(false);
  }

  return <>{user && deviceError && <div className="pwa-banner" role="alert"><span>Device registration: {deviceError}</span><button className="button" onClick={() => setDeviceRetry(value => value + 1)}>Retry</button></div>}<PullToRefresh busy={busy || restoring}/><PwaUpdates busy={busy || restoring}/><section hidden={!user || !profileOpen || offlineView} className="profile-screen">
    <button className="button secondary" onClick={() => setProfileOpen(false)}>← Back to check-in</button>
    <div className="profile-card"><AppLogo size={80}/><h1>Your profile</h1>
      {user && <dl><dt>Name</dt><dd>{user.full_name}</dd><dt>Email</dt><dd>{user.email}</dd><dt>Account</dt><dd>{demo ? 'Demo student' : user.role}</dd></dl>}
      {!demo && <p><a className="button primary" href="/dashboard" target="_blank" rel="noopener noreferrer">Open dashboard in browser ↗</a></p>}
      {user && <PermissionSettings user={user} demo={demo} onChange={setUser}/>}
      {user && <MyDevices userId={user.id} demo={demo} visible={profileOpen} onRegistered={() => setDeviceError('')}/>}
      <PwaInstall busy={busy || restoring}/>
    </div>
  </section>{
    offlineView ? <SavedSessions snapshot={snapshot} online={online} loading={restoring} onRetry={() => setRetry(value => value + 1)} onExit={() => void signOut()}/>
    : restoring && !user ? <main className="loading-screen"><AppLogo size={72}/><p>Preparing your secure session…</p></main>
    : !user ? <AuthCard onAuthenticated={authenticated} onDemo={() => { setDemo(true); setUser(demoUser); }}/>
    : <div hidden={profileOpen}><StudentDashboard user={user} demo={demo} onLogout={signOut} onBusyChange={setBusy} profileOpen={profileOpen} registrationError={deviceError} onOpenProfile={() => setProfileOpen(true)}/></div>
  }</>;
}
