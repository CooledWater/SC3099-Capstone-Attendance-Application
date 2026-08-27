'use client';

import { useCallback, useState } from 'react';

export type GeoPoint = { latitude: number; longitude: number; accuracy: number };
export type GeolocationState = 'idle' | 'requesting' | 'ready' | 'denied' | 'unavailable' | 'timeout' | 'unsupported';

export function useGeolocation() {
  const [state, setState] = useState<GeolocationState>('idle');
  const [point, setPoint] = useState<GeoPoint>();
  const request = useCallback(() => {
    if (!navigator.geolocation || !window.isSecureContext) { setState('unsupported'); return; }
    setState('requesting'); setPoint(undefined);
    navigator.geolocation.getCurrentPosition(({ coords }) => {
      setPoint({ latitude: coords.latitude, longitude: coords.longitude, accuracy: coords.accuracy }); setState('ready');
    }, error => setState(error.code === error.PERMISSION_DENIED ? 'denied' : error.code === error.TIMEOUT ? 'timeout' : 'unavailable'), {
      enableHighAccuracy: true, timeout: 12000, maximumAge: 0,
    });
  }, []);
  const reset = useCallback(() => { setState('idle'); setPoint(undefined); }, []);
  return { state, point, request, reset };
}
