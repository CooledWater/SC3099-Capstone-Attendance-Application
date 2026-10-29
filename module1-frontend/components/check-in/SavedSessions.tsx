'use client';
import { formatSingaporeDateTime, parseApiDateTime } from '@/lib/time';
import { AppLogo } from '@/components/AppLogo';
import { useEffect, useState } from 'react';
import { sessionAvailableOffline, type CachedActiveSessions } from '@/lib/offline/sessionCache';

const statusLabels = { approved: 'Attendance confirmed', flagged: 'Submitted for review', rejected: 'Check-in rejected', appealed: 'Appeal submitted', pending: 'Verification pending' };

export function SavedSessions({ snapshot, online, loading, onRetry, onExit }: {
  snapshot: CachedActiveSessions | null; online: boolean; loading: boolean;
  onRetry: () => void; onExit: () => void;
}) {
  const [now, setNow] = useState(Date.now);
  const [selectedId, setSelectedId] = useState('');
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 10000);
    return () => window.clearInterval(timer);
  }, []);
  const sessions = (snapshot?.sessions ?? []).filter(session => sessionAvailableOffline(session, now))
    .sort((a, b) => Number(!!b.attendance) - Number(!!a.attendance) || parseApiDateTime(b.attendance?.checked_in_at ?? b.scheduled_start).getTime()
      - parseApiDateTime(a.attendance?.checked_in_at ?? a.scheduled_start).getTime());
  const selected = sessions.find(session => session.id === selectedId) ?? sessions[0];
  const attendance = selected?.attendance;
  return <div className="app-shell offline-page">
    <header className="topbar"><div className="logo"><AppLogo size={44}/><span>CCDS Attendance</span></div><button className="button secondary" onClick={onExit}>Sign out</button></header>
    <main className="dashboard">
      <section className="welcome"><div><span className="eyebrow">STUDENT ATTENDANCE · READ-ONLY</span><h1>Saved sessions</h1><p>Choose a saved session to view your latest check-in result.</p></div><span className="offline-status"><i/> Offline</span></section>
      <div className="alert warning offline-summary" role="status" aria-live="polite">
        <b>{online ? 'Connection unavailable — saved sessions only' : 'You are offline — saved sessions only'}</b>
        <span>Saved statuses may have changed. Check-in and appeals require internet; nothing will be submitted or queued offline.</span>
        {snapshot && <span>Last saved: {formatSingaporeDateTime(snapshot.cachedAt)}. Saved details remain available until each session ends.</span>}
      </div>
      {selected ? <div className="content-grid">
        <section className="session-card">
          <div className="session-heading"><span className="status-badge">SAVED SESSION</span></div>
          <label className="select-label">Saved session<select aria-label="Saved session" value={selected.id} onChange={event => setSelectedId(event.target.value)}>{sessions.map(session => <option key={session.id} value={session.id}>{session.course_code ? `${session.course_code} — ` : ''}{session.name}</option>)}</select></label>
          <h2>{selected.name}</h2>
          <div className="session-meta"><span>◷ {formatSingaporeDateTime(selected.scheduled_start)}</span><span>⌖ {selected.venue_name ?? 'Venue unavailable'}</span></div>
          <p>Session ends: {formatSingaporeDateTime(selected.scheduled_end)}</p>
        </section>
        <section className="verification-card" aria-label="Saved check-in result">
          {attendance ? <div className={`result ${attendance.status}`}>
            <div className="result-icon">{attendance.status === 'approved' ? '✓' : attendance.status === 'flagged' ? '!' : attendance.status === 'pending' ? '…' : attendance.status === 'appealed' ? '…' : '×'}</div>
            <span className="eyebrow">SAVED CHECK-IN RESULT</span>
            <h2>{statusLabels[attendance.status]}</h2>
            <p>{attendance.status === 'approved' ? 'You are checked in.' : attendance.status === 'appealed' ? 'Your appeal is awaiting instructor review.' : attendance.status === 'flagged' ? 'Your attendance was recorded and requires instructor review.' : attendance.status === 'pending' ? 'Your submission is still being processed.' : 'Your attendance could not be verified.'} This is your last saved result.</p>
            <dl><div><dt>Check-in time</dt><dd>{formatSingaporeDateTime(attendance.checked_in_at)}</dd></div><div><dt>Risk score</dt><dd>{typeof attendance.risk_score === 'number' && Number.isFinite(attendance.risk_score) ? attendance.risk_score.toFixed(2) : 'Not saved'}</dd></div></dl>
          </div> : <div className="step-content"><span className="eyebrow">SAVED CHECK-IN RESULT</span><h2>No saved check-in result</h2><p>{attendance === null ? 'You had not checked in when this session was last synced.' : 'A check-in result has not been saved for this session.'} Reconnect to check your latest attendance.</p></div>}
        </section>
      </div> : <div className="empty" role="status"><h2>{loading ? 'Loading saved information…' : 'No recent saved sessions'}</h2><p>No recent sessions are available for offline viewing. Saved information is removed from this view when the session ends. Connect to load your latest sessions and attendance.</p></div>}
      <div className="offline-actions"><button className="button primary" disabled={loading} onClick={onRetry}>{loading ? 'Connecting…' : 'Retry connection'}</button>
        <button className="button secondary" onClick={onExit}>Sign out and clear saved sessions</button></div>
    </main>
  </div>;
}
