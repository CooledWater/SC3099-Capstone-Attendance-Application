'use client';

import { useEffect, useRef, useState } from 'react';

type InstallPrompt = Event & {
  prompt(): Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
};

export function PwaInstall({ busy }: { busy: boolean }) {
  const [ready, setReady] = useState(false);
  const [installed, setInstalled] = useState(false);
  const [prompt, setPrompt] = useState<InstallPrompt>();
  const [pending, setPending] = useState(false);
  const [help, setHelp] = useState(false);
  const [message, setMessage] = useState('');
  const requesting = useRef(false);

  useEffect(() => {
    const display = window.matchMedia('(display-mode: standalone)');
    const changed = () => setInstalled(display.matches || (navigator as Navigator & { standalone?: boolean }).standalone === true);
    const available = (event: Event) => {
      event.preventDefault();
      setPrompt(event as InstallPrompt);
      setMessage('');
    };
    const completed = () => { setInstalled(true); setPrompt(undefined); };
    changed(); setReady(true);
    display.addEventListener('change', changed);
    window.addEventListener('beforeinstallprompt', available);
    window.addEventListener('appinstalled', completed);
    return () => {
      display.removeEventListener('change', changed);
      window.removeEventListener('beforeinstallprompt', available);
      window.removeEventListener('appinstalled', completed);
    };
  }, []);

  async function install() {
    if (busy || requesting.current) return;
    if (!prompt) { setHelp(value => !value); return; }
    const event = prompt;
    setPrompt(undefined); // A browser installation event can only be used once.
    requesting.current = true; setPending(true); setMessage('');
    try {
      await event.prompt();
      const choice = await event.userChoice;
      if (choice.outcome === 'accepted') setMessage('Installation requested. Your browser will finish adding the app.');
      else setMessage('Installation cancelled. You can keep using the website or install later from the browser menu.');
    } catch {
      setMessage('The installation prompt could not open. Use the browser instructions below.');
      setHelp(true);
    } finally { requesting.current = false; setPending(false); }
  }

  if (!ready || installed) return null;
  return <aside className="install-panel" aria-label="App installation">
    <div className="install-bar"><div><b>Add attendance to your home screen</b><p>Use the app on your phone or computer.</p></div>
      <button className="button" disabled={busy || pending} onClick={() => void install()} aria-expanded={prompt ? undefined : help} aria-controls={prompt ? undefined : 'install-help'}>{pending ? 'Opening installation…' : prompt ? 'Install app' : 'How to install'}</button></div>
    {busy && <p>Finish your current check-in before installing.</p>}
    {message && <p role="status">{message}</p>}
    {help && <div id="install-help" className="install-help">
      <p><b>iPhone or iPad:</b> open this website in Safari, tap Share, then Add to Home Screen and confirm Add.</p>
      <p><b>Android:</b> open the browser menu and choose Install app or Add to Home screen, if offered.</p>
      <p><b>Laptop or desktop:</b> in Chrome or Edge, use the address-bar install icon or the browser menu&apos;s installation option. Safari on supported Macs offers File → Add to Dock.</p>
      <p>If installation is unavailable, use the website normally. Installation requires your confirmation; camera and location permissions are requested separately when checking in.</p>
    </div>}
  </aside>;
}
