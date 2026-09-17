'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

export type CameraState = 'idle' | 'requesting' | 'ready' | 'denied' | 'unavailable' | 'unsupported';
export type BrowserPermissionState = PermissionState | 'checking' | 'unsupported';

export function useCamera() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream>();
  const requestId = useRef(0);
  const [state, setState] = useState<CameraState>('idle');
  const [permissionState, setPermissionState] = useState<BrowserPermissionState>('checking');

  const stop = useCallback(() => {
    requestId.current += 1;
    streamRef.current?.getTracks().forEach(track => track.stop());
    streamRef.current = undefined;
    if (videoRef.current) videoRef.current.srcObject = null;
    setState('idle');
  }, []);

  const start = useCallback(async () => {
    const id = ++requestId.current;
    if (!navigator.mediaDevices?.getUserMedia || !window.isSecureContext) { setState('unsupported'); return; }

    if (navigator.permissions?.query) {
      try {
        const permission = await navigator.permissions.query({ name: 'camera' as PermissionName });
        if (id !== requestId.current) return;
        setPermissionState(permission.state);
        if (permission.state === 'denied') { setState('denied'); return; }
      } catch {
        setPermissionState('unsupported');
      }
    }

    if (id !== requestId.current) return;
    setState('requesting');
    try {
      streamRef.current?.getTracks().forEach(track => track.stop());
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: 'user' }, width: { ideal: 720 }, height: { ideal: 720 } }, audio: false });
      if (id !== requestId.current) { stream.getTracks().forEach(track => track.stop()); return; }
      streamRef.current = stream;
      stream.getVideoTracks().forEach(track => track.addEventListener('ended', () => {
        if (streamRef.current === stream) { stop(); setState('unavailable'); }
      }, { once: true }));
      if (videoRef.current) videoRef.current.srcObject = stream;
      setPermissionState('granted');
      setState('ready');
    } catch (error) {
      if (id !== requestId.current) return;
      const denied = error instanceof DOMException && (error.name === 'NotAllowedError' || error.name === 'SecurityError');
      if (denied) setPermissionState('denied');
      setState(denied ? 'denied' : 'unavailable');
    }
  }, [stop]);

  const capture = useCallback(() => {
    const video = videoRef.current;
    if (!video || state !== 'ready' || !video.videoWidth) throw new Error('The camera frame is not ready yet.');
    const canvas = document.createElement('canvas');
    const scale = Math.min(1, 720 / Math.max(video.videoWidth, video.videoHeight));
    canvas.width = Math.round(video.videoWidth * scale); canvas.height = Math.round(video.videoHeight * scale);
    const context = canvas.getContext('2d');
    if (!context) throw new Error('Image capture is unavailable in this browser.');
    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL('image/jpeg', .82).replace(/^data:image\/\w+;base64,/, '');
  }, [state]);

  useEffect(() => {
    if (state === 'ready' && videoRef.current && streamRef.current) videoRef.current.srcObject = streamRef.current;
  }, [state]);

  useEffect(() => stop, [stop]);
  useEffect(() => {
    if (!navigator.permissions?.query) { setPermissionState('unsupported'); return; }

    let active = true;
    let permission: PermissionStatus | undefined;
    const applyPermission = () => {
      if (!active || !permission) return;
      setPermissionState(permission.state);
      if (permission.state === 'denied') {
        stop();
        setState('denied');
      } else if (permission.state === 'prompt') {
        stop();
      } else {
        setState(current => current === 'denied' ? 'idle' : current);
      }
    };

    navigator.permissions.query({ name: 'camera' as PermissionName })
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
  }, [stop]);
  useEffect(() => {
    const handleVisibility = () => { if (document.hidden) stop(); };
    document.addEventListener('visibilitychange', handleVisibility);
    return () => document.removeEventListener('visibilitychange', handleVisibility);
  }, [stop]);

  return { videoRef, state, permissionState, start, stop, capture };
}
