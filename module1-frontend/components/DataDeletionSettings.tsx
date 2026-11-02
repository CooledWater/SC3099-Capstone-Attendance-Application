'use client';
import { useEffect, useState } from 'react';
import { apiRequest } from '@/lib/api/client';
import { formatSingaporeDateTime } from '@/lib/time';

type DeletionStatus = { scheduled_deletion_at: string | null };
const path = '/users/me/deletion-request';
export function DataDeletionSettings() {
  const [status, setStatus] = useState<DeletionStatus>();
  const [password, setPassword] = useState('');
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
    event.preventDefault(); setBusy(true); setError('');
    try {
      setStatus(await apiRequest<DeletionStatus>(path, { method: status?.scheduled_deletion_at ? 'DELETE' : 'POST', body: JSON.stringify({ password }) }));
      setPassword('');
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not update deletion request.'); }
    finally { setBusy(false); }
  }
  return <div>
    <p className="settings-note">Request removal of your account data after 30 days. Your attendance, devices, face template and course enrollments will be removed, and your account will be anonymised and disabled. Required audit records are retained.</p>
    {status?.scheduled_deletion_at ? <p className="settings-status" role="status">Deletion scheduled for {formatSingaporeDateTime(status.scheduled_deletion_at)}. You can cancel before that date.</p> : status && <p className="settings-status">No data deletion is scheduled. You can continue using your account during the 30-day period.</p>}
    <form className="form-stack" onSubmit={event => void submit(event)}>
      <label>Confirm your current password<input required type="password" autoComplete="current-password" value={password} onChange={event => setPassword(event.target.value)} disabled={busy}/></label>
      <button className="button secondary" disabled={busy || !status || !password}>{busy ? 'Please wait…' : status?.scheduled_deletion_at ? 'Cancel deletion request' : 'Request data deletion in 30 days'}</button>
    </form>
    {error && <p className="inline-error" role="alert">{error}</p>}
  </div>;
}
