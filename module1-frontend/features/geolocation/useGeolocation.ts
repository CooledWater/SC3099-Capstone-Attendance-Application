'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';

export type GeoPoint = { latitude: number; longitude: number; accuracy: number };
export type GeolocationState = 'idle' | 'requesting' | 'ready' | 'denied' | 'unavailable' | 'timeout' | 'unsupported';
export type BrowserPermissionState = PermissionState | 'checking' | 'unsupported';

function integrationTestPoint(): GeoPoint | undefined {
  const raw = process.env.NEXT_PUBLIC_INTEGRATION_TEST_GEOLOCATION;
  if (!raw) return undefined;

  const [latitude, longitude, accuracy] = raw.split(',').map(Number);
  if (
    !Number.isFinite(latitude) || latitude < -90 || latitude > 90 ||
    !Number.isFinite(longitude) || longitude < -180 || longitude > 180 ||
    !Number.isFinite(accuracy) || accuracy < 0
  ) return undefined;

  return { latitude, longitude, accuracy };
}

export function useGeolocation() {
  const syntheticPoint = useMemo(integrationTestPoint, []);
  const [state, setState] = useState<GeolocationState>('idle');
  const [point, setPoint] = useState<GeoPoint>();
  const [permissionState, setPermissionState] = useState<BrowserPermissionState>('checking');
  const request = useCallback(async () => {
    if (syntheticPoint) {
      setState('requesting');
      setPoint(undefined);
      await Promise.resolve();
      setPermissionState('granted');
      setPoint(syntheticPoint);
      setState('ready');
      return;
    }

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
  }, [syntheticPoint]);
  const reset = useCallback(() => { setState('idle'); setPoint(undefined); }, []);

  useEffect(() => {
    if (syntheticPoint) { setPermissionState('granted'); return; }
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
  }, [syntheticPoint]);

  return { state, point, permissionState, request, reset };
}
