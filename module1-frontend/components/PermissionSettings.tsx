'use client';
import { useState } from 'react';
import { updateConsent } from '@/lib/api/auth';
import type { User } from '@/types/api';

type Permission = 'camera' | 'location';
export function PermissionSettings({ user, demo, onChange }: { user: User; demo: boolean; onChange: (user: User) => void }) {
  const [page, setPage] = useState<'profile' | 'settings' | Permission>('profile');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const camera = user.camera_consent === true;
  const location = user.geolocation_consent === true;
  async function toggle(permission: Permission) {
    const nextCamera = permission === 'camera' ? !camera : camera;
    const nextLocation = permission === 'location' ? !location : location;
    setSaving(true); setError('');
    try {
      const updated = demo ? { ...user, camera_consent: nextCamera, geolocation_consent: nextLocation } : await updateConsent(nextCamera, nextLocation);
      onChange(updated);
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not save settings. Please retry.'); }
    finally { setSaving(false); }
  }
  const detail = page === 'camera' || page === 'location';
  const title = page === 'camera' ? 'Camera' : 'Location';
  const enabled = page === 'camera' ? camera : location;
  return <section className={`privacy-settings${page === 'profile' ? ' profile-settings-entry' : ''}`} aria-label="Privacy settings">
    {page === 'profile' ? <button className="settings-row" onClick={() => setPage('settings')}><span className="settings-icon neutral" aria-hidden="true"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="m9 3-.6 2.2-2 .9-2-.7-2 3.4 1.5 1.6v2.3l-1.5 1.6 2 3.4 2-.7 2 .9L9 20.2h4l.6-2.2 2-.9 2 .7 2-3.4-1.5-1.6v-2.3l1.5-1.6-2-3.4-2 .7-2-.9L13 3Z"/><circle cx="11" cy="11.6" r="3"/></svg></span><span>Settings</span><span className="settings-chevron" aria-hidden="true">›</span></button> : <>
      <div className="settings-heading"><button aria-label={detail ? 'Back to settings' : 'Back to profile'} onClick={() => { setPage(detail ? 'settings' : 'profile'); setError(''); }}>‹ {detail ? 'Settings' : 'Profile'}</button><h2>{detail ? title : 'Settings'}</h2></div>
      {!detail ? <><p className="settings-caption">PRIVACY & PERMISSIONS</p><div className="settings-group">{(['camera', 'location'] as const).map(permission => <button className="settings-row" key={permission} onClick={() => setPage(permission)}><span className={`settings-icon ${permission}`} aria-hidden="true">{permission === 'camera' ? '▣' : '⌖'}</span><span>{permission === 'camera' ? 'Camera' : 'Location'}</span><small>{(permission === 'camera' ? camera : location) ? 'Allowed' : 'Blocked'}</small><span className="settings-chevron" aria-hidden="true">›</span></button>)}</div><p className="settings-note">Choose what CCDS Attendance can use for verification.</p></> : <>
        <div className="settings-group"><div className="settings-row"><span>Allow {title.toLowerCase()} verification</span><button type="button" role="switch" aria-checked={enabled} aria-label={`Allow ${title.toLowerCase()} verification`} disabled={saving} className="ios-switch" onClick={() => void toggle(page as Permission)}><span/></button></div></div>
        <p className="settings-note">{page === 'camera' ? 'Your camera is used only during identity and liveness verification.' : 'Your precise location is collected only for your check-in.'} When disabled, the app will not collect {page === 'camera' ? 'camera images' : 'your location'} and check-in is blocked.</p>
        <p className="settings-note">This saves your consent for your account. Browser permission is separate: to revoke it too, open this app’s site settings in your browser and block {title.toLowerCase()} access. Enabling this switch does not override a browser block.</p>
        <p className="settings-status" role="status">{saving ? 'Saving…' : enabled ? `${title} verification allowed` : `${title} verification blocked`}</p>
      </>}
      {error && <p className="inline-error" role="alert">{error}</p>}
    </>}
  </section>;
}
