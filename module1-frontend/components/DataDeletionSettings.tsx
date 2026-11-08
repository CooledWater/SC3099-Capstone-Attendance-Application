'use client';
import { useEffect, useState } from 'react';
import { apiRequest, clearTokens } from '@/lib/api/client';
import { formatSingaporeDateTime } from '@/lib/time';

type DeletionStatus = { scheduled_deletion_at: string | null };
const path = '/users/me/deletion-request';
export function DataDeletionSettings({ onDeleted }: { onDeleted: () => void }) {
  const [status, setStatus] = useState<DeletionStatus>();
  const [password, setPassword] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    void apiRequest<DeletionStatus>(path).then(value => { if (active) setStatus(value); })
      .catch(cause => { if (active) setError(cause instanceof Error ? cause.message : 'Could not load deletion status.'); })
      .finally(() => { if (active) setBusy(false); });
    return () => { active = false; };
  }, []);
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!confirmed || busy) return;
    setBusy(true); setError('');
    try {
      await apiRequest<DeletionStatus>(path, { method: 'POST', body: JSON.stringify({ password }) });
      setPassword('');
      clearTokens();
      onDeleted();
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not delete your account.'); }
    finally { setBusy(false); }
  }
  return <div>
    <p className="settings-note">Deleting your account immediately signs you out and prevents further access. Your remaining personal data will be removed after 30 days, and your account record will be anonymised. Check-in records expire independently after 30 days. Required audit records are retained.</p>
    <p className="settings-note">You cannot cancel or restore your account through this app after confirming deletion.</p>
    {status?.scheduled_deletion_at && <p className="settings-status" role="status">An earlier data-cleanup request is scheduled for {formatSingaporeDateTime(status.scheduled_deletion_at)}. Confirming account deletion now closes access immediately and schedules personal-data cleanup 30 days from now.</p>}
    <form className="form-stack" onSubmit={event => void submit(event)}>
      <label>Confirm your current password<input required type="password" autoComplete="current-password" value={password} onChange={event => setPassword(event.target.value)} disabled={busy}/></label>
      <label className="deletion-confirmation"><input required type="checkbox" checked={confirmed} onChange={event => setConfirmed(event.target.checked)} disabled={busy}/> I understand that my account will close immediately and I will lose access.</label>
      <button className="button secondary" disabled={busy || !status || !password || !confirmed}>{busy ? 'Please wait…' : 'Delete my account'}</button>
    </form>
    {error && <p className="inline-error" role="alert">{error}</p>}
  </div>;
}
