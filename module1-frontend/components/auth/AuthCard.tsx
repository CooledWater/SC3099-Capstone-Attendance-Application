'use client';

import { FormEvent, useState } from 'react';
import { login, register } from '@/lib/api/auth';
import type { User } from '@/types/api';

export function AuthCard({ onAuthenticated, onDemo }: { onAuthenticated: (user: User) => void; onDemo: () => void }) {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [form, setForm] = useState({ fullName: '', email: '', password: '' });
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');

  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setMessage('');
    try {
      if (mode === 'register') {
        await register(form.fullName.trim(), form.email.trim(), form.password);
        setMode('login'); setMessage('Account created. Sign in to continue.');
      } else onAuthenticated(await login(form.email.trim(), form.password));
    } catch (error) { setMessage(error instanceof Error ? error.message : 'Authentication failed.'); }
    finally { setBusy(false); }
  }

  return <main className="auth-shell">
    <section className="auth-brand" aria-label="SAIV introduction">
      <div className="brand-mark">S</div><span className="eyebrow">SAIV STUDENT</span>
      <h1>Attendance you can trust.</h1>
      <p>Secure identity and presence verification, designed with your privacy in mind.</p>
      <ul><li>Biometric frames are processed for verification, not retained on this device.</li><li>Your precise location is collected only when you check in.</li><li>Every request is reviewed by the attendance service.</li></ul>
    </section>
    <section className="auth-panel">
      <div className="auth-card">
        <span className="eyebrow">WELCOME</span><h2>{mode === 'login' ? 'Sign in to your account' : 'Create your student account'}</h2>
        <div className="tabs" role="tablist" aria-label="Authentication mode">
          {(['login', 'register'] as const).map(value => <button role="tab" aria-selected={mode === value} key={value} onClick={() => { setMode(value); setMessage(''); }} className={mode === value ? 'active' : ''}>{value === 'login' ? 'Sign in' : 'Register'}</button>)}
        </div>
        {message && <div className="alert" role="status">{message}</div>}
        <form onSubmit={submit} className="form-stack">
          {mode === 'register' && <label>Full name<input required autoComplete="name" value={form.fullName} onChange={e => setForm({ ...form, fullName: e.target.value })}/></label>}
          <label>Email address<input required type="email" autoComplete="email" value={form.email} onChange={e => setForm({ ...form, email: e.target.value })}/></label>
          <label>Password<input required minLength={8} type="password" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} value={form.password} onChange={e => setForm({ ...form, password: e.target.value })}/><small>Minimum 8 characters</small></label>
          <button className="button primary" disabled={busy}>{busy ? 'Please wait…' : mode === 'login' ? 'Sign in securely' : 'Create account'}</button>
        </form>
        {process.env.NEXT_PUBLIC_ENABLE_DEMO_MODE !== 'false' && <><div className="divider"><span>or preview locally</span></div><button className="button secondary" onClick={onDemo}>Continue in demo mode</button></>}
      </div>
    </section>
  </main>;
}

