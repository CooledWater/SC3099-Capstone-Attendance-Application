'use client';
import { useEffect, useState } from 'react';
import type { CachedActiveSessions } from '@/lib/offline/sessionCache';

export function SavedSessions({ snapshot, online, loading, onRetry, onExit }: {
  snapshot: CachedActiveSessions | null; online: boolean; loading: boolean;
  onRetry: () => void; onExit: () => void;
}) {
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 30000);
    return () => window.clearInterval(timer);
  }, []);
  const fresh = snapshot && now - snapshot.cachedAt.getTime() <= 15 * 60 * 1000;
  const sessions = fresh ? snapshot.sessions.filter(session => Date.parse(session.checkin_closes_at) >= now) : [];
  return <main className="dashboard">
    <section className="welcome"><div><span className="eyebrow">SAIV · READ-ONLY</span><h1>Saved sessions</h1></div></section>
    <div className="alert warning" role="status" aria-live="polite">
      <b>{online ? 'Connection unavailable — saved sessions only' : 'You are offline — saved sessions only'}</b>
      <span>Check your internet connection. Sign-in and attendance verification require internet. No attendance will be submitted or queued here.</span>
      {snapshot && <span>Last saved: {snapshot.cachedAt.toLocaleString()}. These details may have changed.</span>}
    </div>
    <div className="saved-session-list">{sessions.map(session => <section className="session-card" key={session.id}>
      <span className="eyebrow">{session.course_code ?? 'SAVED SESSION'}</span><h2>{session.name}</h2>
      <p>{session.venue_name ?? 'Venue unavailable'}</p>
      <p>Starts {new Date(session.scheduled_start).toLocaleString()}</p>
      <p>Saved check-in deadline: {new Date(session.checkin_closes_at).toLocaleString()}</p>
    </section>)}</div>
    {!sessions.length && <p>{loading ? 'Loading saved information…' : 'No recent saved sessions are available. Connect to the internet to load your sessions.'}</p>}
    <div className="offline-actions"><button className="button primary" disabled={loading} onClick={onRetry}>{loading ? 'Connecting…' : 'Retry connection'}</button>
      <button className="button" onClick={onExit}>Sign out and clear saved sessions</button></div>
  </main>;
}
