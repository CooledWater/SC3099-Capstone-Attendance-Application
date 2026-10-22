'use client';
import { useEffect, useRef, useState } from 'react';

const THRESHOLD = 100;

export function PullToRefresh({ busy }: { busy: boolean }) {
  const [standalone, setStandalone] = useState(false);
  useEffect(() => {
    const display = window.matchMedia('(display-mode: standalone)');
    const changed = () => setStandalone(display.matches || (navigator as Navigator & { standalone?: boolean }).standalone === true);
    changed();
    display.addEventListener('change', changed);
    return () => display.removeEventListener('change', changed);
  }, []);
  return standalone ? <PwaRefreshControls busy={busy}/> : null;
}

export function PwaRefreshControls({ busy }: { busy: boolean }) {
  const [distance, setDistance] = useState(0);
  const [refreshing, setRefreshing] = useState(false);
  const refreshingRef = useRef(false);

  function refresh() {
    if (busy || refreshingRef.current) return;
    refreshingRef.current = true;
    setRefreshing(true);
    // Session restoration uses the existing HttpOnly refresh cookie after reload.
    window.location.reload();
  }

  useEffect(() => {
    let start: { x: number; y: number } | null = null;
    let pull = 0;
    const reset = () => { start = null; pull = 0; setDistance(0); };
    const begin = (event: TouchEvent) => {
      reset();
      if (busy || refreshingRef.current || event.touches.length !== 1 || window.scrollY > 0) return;
      // Do not take over form controls or nested scrollable panels.
      let target = event.target instanceof Element ? event.target : null;
      if (target?.closest('input, textarea, select, button, a, video, [role="dialog"]')) return;
      while (target && target !== document.documentElement) {
        if (target.scrollHeight > target.clientHeight && /auto|scroll/.test(getComputedStyle(target).overflowY)) return;
        target = target.parentElement;
      }
      const touch = event.touches[0]!;
      start = { x: touch.clientX, y: touch.clientY };
    };
    const move = (event: TouchEvent) => {
      if (!start) return;
      if (busy || event.touches.length !== 1 || window.scrollY > 0) { reset(); return; }
      const touch = event.touches[0]!;
      const dy = touch.clientY - start.y;
      if (dy < 0 || Math.abs(touch.clientX - start.x) > Math.abs(dy)) { reset(); return; }
      if (event.cancelable) event.preventDefault();
      pull = Math.min(dy, 160);
      setDistance(pull);
    };
    const end = () => {
      const shouldRefresh = pull >= THRESHOLD;
      reset();
      if (shouldRefresh) refresh();
    };
    document.documentElement.classList.add('custom-pull-refresh');
    document.addEventListener('touchstart', begin, { passive: true });
    document.addEventListener('touchmove', move, { passive: false });
    document.addEventListener('touchend', end);
    document.addEventListener('touchcancel', reset);
    return () => {
      document.documentElement.classList.remove('custom-pull-refresh');
      document.removeEventListener('touchstart', begin);
      document.removeEventListener('touchmove', move);
      document.removeEventListener('touchend', end);
      document.removeEventListener('touchcancel', reset);
    };
  }, [busy]);

  if (!distance && !refreshing) return null;
  return <div className="refresh-toolbar" role="status" aria-live="polite">
    {refreshing ? 'Refreshing…' : distance >= THRESHOLD ? 'Release to refresh' : 'Pull down to refresh'}
  </div>;
}
