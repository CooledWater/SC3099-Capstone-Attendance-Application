'use client';
import { useEffect, useRef, useState } from 'react';

export function PwaUpdates({ busy }: { busy: boolean }) {
  const cleanupUpdate = useRef<(() => void)>();
  const [waiting, setWaiting] = useState<ServiceWorker>();
  const [message, setMessage] = useState('');
  const [updating, setUpdating] = useState(false);
  const [online, setOnline] = useState(true);
  useEffect(() => {
    if (!('serviceWorker' in navigator)) return;
    setOnline(navigator.onLine);
    if (process.env.NODE_ENV !== 'production') {
      void navigator.serviceWorker.getRegistrations().then(items => items
        .filter(item => item.active?.scriptURL === `${location.origin}/sw.js`)
        .forEach(item => void item.unregister()));
      return;
    }
    let active = true;
    let registration: ServiceWorkerRegistration | undefined;
    let installing: ServiceWorker | null = null;
    const stateChanged = () => {
      if (!active) return;
      setWaiting(registration?.waiting?.state === 'installed' ? registration.waiting : undefined);
      if (installing?.state === 'redundant') setMessage('Offline setup could not finish. Reconnect and retry.');
    };
    const updateFound = () => {
      installing?.removeEventListener('statechange', stateChanged);
      installing = registration?.installing ?? null;
      installing?.addEventListener('statechange', stateChanged);
    };
    const check = () => {
      setOnline(navigator.onLine);
      if (navigator.onLine && !document.hidden) void registration?.update().catch(() => undefined);
    };
    void navigator.serviceWorker.register('/sw.js', { updateViaCache: 'none' }).then(result => {
      if (!active) return;
      registration = result;
      if (result.waiting?.state === 'installed') setWaiting(result.waiting);
      result.addEventListener('updatefound', updateFound);
      updateFound();
    }).catch(() => { if (active) setMessage('Offline setup is unavailable. Connect to the internet and reopen the app to retry.'); });
    window.addEventListener('online', check);
    window.addEventListener('offline', check);
    document.addEventListener('visibilitychange', check);
    return () => {
      active = false;
      cleanupUpdate.current?.();
      registration?.removeEventListener('updatefound', updateFound);
      installing?.removeEventListener('statechange', stateChanged);
      window.removeEventListener('online', check);
      window.removeEventListener('offline', check);
      document.removeEventListener('visibilitychange', check);
    };
  }, []);

  function update() {
    if (!waiting || busy || updating || !navigator.onLine) return;
    setMessage(''); setUpdating(true);
    let finished = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const cleanup = () => {
      waiting.removeEventListener('statechange', changed);
      navigator.serviceWorker.removeEventListener('controllerchange', changed);
      if (timer !== undefined) clearTimeout(timer);
    };
    const changed = () => {
      if (finished) return;
      if (waiting.state === 'activated') {
        finished = true; cleanup(); location.reload();
      } else if (waiting.state === 'redundant') {
        finished = true; cleanup(); setUpdating(false); setWaiting(undefined);
        setMessage('Update failed. Reopen the app to retry.');
      }
    };
    cleanupUpdate.current = () => { finished = true; cleanup(); };
    waiting.addEventListener('statechange', changed);
    navigator.serviceWorker.addEventListener('controllerchange', changed);
    timer = setTimeout(() => {
      if (finished) return;
      finished = true; cleanup(); setUpdating(false);
      setMessage('The update is taking longer than expected. Close other app windows, then try again.');
    }, 15000);
    // Activation can finish between rendering the banner and clicking it.
    changed();
    if (!finished) {
      try { waiting.postMessage({ type: 'SKIP_WAITING' }); changed(); }
      catch {
        finished = true; cleanup(); setUpdating(false);
        setMessage('The update could not start. Reopen the app to retry.');
      }
    }
  }
  if (!waiting && !message) return null;
  return <aside className="pwa-banner" role="status" aria-live="polite">
    <span>{message || (waiting ? !online ? 'Update available. Reconnect before updating.' : busy ? 'Update available. Finish your check-in before updating.' : 'Update available. Reload to use the latest app version.' : '')}</span>
    {waiting && <button className="button" disabled={busy || updating || !online} onClick={update}>{updating ? 'Updating…' : 'Update and reload'}</button>}
  </aside>;
}
