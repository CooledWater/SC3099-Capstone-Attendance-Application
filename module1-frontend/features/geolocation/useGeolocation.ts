'use client';

import { useCallback, useEffect, useState } from 'react';

export type GeoPoint = { latitude: number; longitude: number; accuracy: number };
export type GeolocationState = 'idle' | 'requesting' | 'ready' | 'denied' | 'unavailable' | 'timeout' | 'unsupported';
export type BrowserPermissionState = PermissionState | 'checking' | 'unsupported';

export function useGeolocation() {
  const [state, setState] = useState<GeolocationState>('idle');
  const [point, setPoint] = useState<GeoPoint>();
  const [permissionState, setPermissionState] = useState<BrowserPermissionState>('checking');
  const request = useCallback(async () => {
    if (!navigator.geolocation || !window.isSecureContext) { setState('unsupported'); return; }

    if (navigator.permissions?.query) {
      try {
        const permission = await navigator.permissions.query({ name: 'geolocation' });
        setPermissionState(permission.state);
        if (permission.state === 'denied') { setState('denied'); return; }
      } catch {
        setPermissionState('unsupported');
      }
    }

    setState('requesting'); setPoint(undefined);
    navigator.geolocation.getCurrentPosition(({ coords }) => {
      setPermissionState('granted');
      setPoint({ latitude: coords.latitude, longitude: coords.longitude, accuracy: coords.accuracy }); setState('ready');
    }, error => {
      if (error.code === error.PERMISSION_DENIED) setPermissionState('denied');
      setState(error.code === error.PERMISSION_DENIED ? 'denied' : error.code === error.TIMEOUT ? 'timeout' : 'unavailable');
    }, {
      enableHighAccuracy: true, timeout: 12000, maximumAge: 0,
    });
  }, []);
  const reset = useCallback(() => { setState('idle'); setPoint(undefined); }, []);

  useEffect(() => {
    if (!navigator.permissions?.query) { setPermissionState('unsupported'); return; }

    let active = true;
    let permission: PermissionStatus | undefined;
    const applyPermission = () => {
      if (!active || !permission) return;
      setPermissionState(permission.state);
      if (permission.state === 'denied') {
        setPoint(undefined);
        setState('denied');
      } else if (permission.state === 'prompt') {
        setPoint(undefined);
        setState('idle');
      } else {
        setState(current => current === 'denied' ? 'idle' : current);
      }
    };

    navigator.permissions.query({ name: 'geolocation' })
      .then(result => {
        if (!active) return;
        permission = result;
        permission.addEventListener('change', applyPermission);
        applyPermission();
      })
      .catch(() => { if (active) setPermissionState('unsupported'); });

    return () => {
      active = false;
      permission?.removeEventListener('change', applyPermission);
    };
  }, []);

  return { state, point, permissionState, request, reset };
}
