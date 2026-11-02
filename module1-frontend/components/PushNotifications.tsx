'use client';
import { useEffect, useState } from 'react';
import { disablePush, enablePush, getPushConfig, pushSupported, syncPush } from '@/lib/push';

export function PushNotifications({ userId }: { userId: string }) {
  const [enabled, setEnabled] = useState(false);
  const [available, setAvailable] = useState(false);
  const [busy, setBusy] = useState(true);
  const [message, setMessage] = useState('');
  useEffect(() => {
    let active = true;
    async function refresh() {
      try {
        if (!pushSupported()) {
          if (active) setMessage('Use HTTPS and a browser that supports push notifications. On iPhone or iPad, add this app to your Home Screen and open it there.');
          return;
        }
        const config = await getPushConfig();
        const subscribed = await syncPush(userId);
        if (active) { setAvailable(config.enabled); setEnabled(subscribed); setMessage(config.enabled ? '' : 'Notifications are not configured yet.'); }
      } catch (error) { if (active) setMessage(error instanceof Error ? error.message : 'Could not load notification settings.'); }
      finally { if (active) setBusy(false); }
    }
    void refresh();
    window.addEventListener('online', refresh);
    return () => { active = false; window.removeEventListener('online', refresh); };
  }, [userId]);

  async function toggle() {
    setBusy(true); setMessage('');
    try {
      if (enabled) await disablePush();
      else await enablePush(userId);
      setEnabled(!enabled);
    } catch (error) { setMessage(error instanceof Error ? error.message : 'Could not update notification settings.'); }
    finally { setBusy(false); }
  }
  return <div aria-label="Attendance notifications">
    <p className="settings-note">Receive a push notification on this device when an instructor, TA or admin approves your flagged or appealed attendance, even when the app is closed. Notifications stop when you sign out.</p>
    <p role="status">{enabled ? 'Notifications enabled on this device.' : 'Notifications are off on this device.'}</p>
    <div className="settings-group"><div className="settings-row"><span>Allow attendance notifications</span><button type="button" role="switch" aria-label="Allow attendance notifications" aria-checked={enabled} className="ios-switch" disabled={busy || (!available && !enabled)} onClick={() => void toggle()}><span/></button></div></div>
    {busy && <p className="settings-status" role="status">Updating notification settings…</p>}
    {message && <p className="settings-note" role="status">{message}</p>}
  </div>;
}
