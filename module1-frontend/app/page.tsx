'use client';
import { useEffect, useState } from 'react';
import { AuthCard } from '@/components/auth/AuthCard';
import { StudentDashboard } from '@/components/check-in/StudentDashboard';
import { getMe, logout } from '@/lib/api/auth';
import { refreshAccessToken } from '@/lib/api/client';
import type { User } from '@/types/api';

const demoUser: User = { id: 'demo-student', email: 'student@demo.local', full_name: 'Alex Tan', role: 'student' };

export default function Home() {
  const [user, setUser] = useState<User>();
  const [demo, setDemo] = useState(false);
  const [restoring, setRestoring] = useState(true);
  useEffect(() => {
    refreshAccessToken().then(ok => ok ? getMe().then(setUser).catch(() => undefined) : undefined).finally(() => setRestoring(false));
    if ('serviceWorker' in navigator) {
      if (process.env.NODE_ENV === 'production') navigator.serviceWorker.register('/sw.js').catch(() => undefined);
      else navigator.serviceWorker.getRegistrations().then(items => items.forEach(item => item.unregister()));
    }
  }, []);
  if (restoring) return <main className="loading-screen"><div className="brand-mark">S</div><p>Preparing your secure session…</p></main>;
  if (!user) return <AuthCard onAuthenticated={setUser} onDemo={() => { setDemo(true); setUser(demoUser); }}/>;
  return <StudentDashboard user={user} demo={demo} onLogout={async () => { if (!demo) await logout(); setDemo(false); setUser(undefined); }}/>;
}
