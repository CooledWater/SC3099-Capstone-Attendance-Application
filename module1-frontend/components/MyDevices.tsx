'use client';
import { useEffect, useState } from 'react';
import { browserFingerprint, getDeviceIdentity, listDevices, registerCurrentDevice, removeDevice, rotateDeviceKey, type RegisteredDevice } from '@/lib/device';
import { formatSingaporeDateTime } from '@/lib/time';
export function MyDevices({ userId, demo, visible, onRegistered }: { userId: string; demo: boolean; visible: boolean; onRegistered?: () => void }) {
  const [open, setOpen] = useState(false);
  const [devices, setDevices] = useState<RegisteredDevice[]>([]);
  const [fingerprint, setFingerprint] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function refresh() {
    setBusy(true); setError('');
    try {
      if (demo) { setDevices([]); return; }
      // Device management must remain accessible when registration is at its limit.
      setDevices((await listDevices()).filter(device => device.is_active));
      const identity = await getDeviceIdentity(userId);
      setFingerprint(identity.fingerprint);
      const current = await registerCurrentDevice(userId);
      setDevices((await listDevices()).filter(device => device.is_active));
      if (current.is_active) onRegistered?.();
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Devices could not be loaded.'); }
    finally { setBusy(false); }
  }
  useEffect(() => {
    if (!open || !visible) return;
    void refresh();
    // Refresh server trust each time this view is opened.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, visible, userId, demo]);
  async function renewKey() {
    setBusy(true); setError('');
    try { await rotateDeviceKey(userId); await refresh(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Security key could not be renewed.'); }
    finally { setBusy(false); }
  }
  async function remove(device: RegisteredDevice) {
    if (!window.confirm(`Remove ${device.device_name || 'this device'}? Check-in will be blocked on it. Contact an administrator if you need to register it again.`)) return;
    setBusy(true); setError('');
    try { await removeDevice(device.id); await refresh(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Device could not be removed.'); }
    finally { setBusy(false); }
  }
  return <section className="privacy-settings profile-settings-entry" aria-label="My devices">
    <button className="settings-row" aria-expanded={open} onClick={() => setOpen(value => !value)}><span>My devices</span><span className="settings-chevron" aria-hidden="true">{open ? '⌄' : '›'}</span></button>
    {open && <><p className="settings-note">You can have up to two active devices, including devices awaiting approval. Remove an existing device to make room for another. New devices await admin approval. You can check in while waiting, but your attendance will be flagged for review. A device name does not prove ownership.</p>
      <p className="settings-note" role="status">{devices.filter(device => device.is_active).length} / 2 active registrations</p>
      <button className="button secondary" disabled={busy} onClick={() => void refresh()}>{busy ? 'Loading…' : 'Refresh devices'}</button>
      {!demo && devices.some(device => device.is_active && browserFingerprint(device) === fingerprint) && <><button className="button secondary" disabled={busy} onClick={() => void renewKey()}>Renew this device’s security key</button><p className="settings-note">Keys renew automatically near their 90-day expiry. Renewal keeps your device registration and approval.</p></>}
      {error && <p className="inline-error" role="alert">{error}</p>}
      {!devices.length && !busy && !error && <p>No registered devices{demo ? ' in demo mode' : ''}.</p>}
      <div className="device-list">{devices.map(device => <article className="device-item" key={device.id}>
        <h3>{device.device_name || 'Browser'} {browserFingerprint(device) === fingerprint && <small> · This device</small>}</h3>
        <p>Approval reference: {browserFingerprint(device).slice(0, 16)}</p>
        <p className="device-trust">{device.is_trusted ? 'Admin approved' : 'Awaiting admin approval'}</p>
        {device.shared_browser && <p className="inline-error">This browser has been verified on multiple student accounts. Check-ins require review even if this registration is approved.</p>}
        <p>Last activity: {formatSingaporeDateTime(device.last_seen_at, { dateStyle: 'medium', timeStyle: 'short' })}<br/>{device.total_checkins} check-in attempts</p>
        <div className="offline-actions"><button className="button secondary" disabled={busy} onClick={() => void remove(device)}>Remove device</button></div>
      </article>)}</div>
    </>}
  </section>;
}
