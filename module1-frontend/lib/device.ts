import { apiRequest } from './api/client';

export type RegisteredDevice = {
  id: string; device_fingerprint: string; device_name: string | null; platform: string | null;
  browser_fingerprint?: string | null; shared_browser?: boolean; browser_identity_verified?: boolean;
  is_trusted: boolean; is_active: boolean; first_seen_at: string; last_seen_at: string; total_checkins: number;
};
type Identity = { privateKey: CryptoKey; publicKey: string; fingerprint: string };
const BROWSER_KEY = 'browser-installation-v1';
let pendingIdentity: Promise<Identity> | undefined;
const toBase64 = (value: ArrayBuffer) => btoa(String.fromCharCode(...Array.from(new Uint8Array(value))));
function database(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open('saiv-device-keys', 1);
    request.onupgradeneeded = () => request.result.createObjectStore('identities');
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(new Error('Device storage is unavailable. Enable browser storage and retry.'));
  });
}
async function loadIdentity(userId: string): Promise<Identity> {
  if (!crypto?.subtle) throw new Error('Device registration requires HTTPS or localhost.');
  const db = await database();
  try {
    const existing = await new Promise<Identity | undefined>((resolve, reject) => {
      const request = db.transaction('identities').objectStore('identities').get(BROWSER_KEY);
      request.onsuccess = () => resolve(request.result); request.onerror = () => reject(request.error);
    });
    if (existing) return existing;
    // Adopt the first signed-in account's old key to retain that registration.
    // All subsequent accounts use the same application-scoped browser key.
    const legacy = await new Promise<Identity | undefined>((resolve, reject) => {
      const request = db.transaction('identities').objectStore('identities').get(userId);
      request.onsuccess = () => resolve(request.result); request.onerror = () => reject(request.error);
    });
    let identity = legacy;
    if (!identity) {
      const keys = await crypto.subtle.generateKey({ name: 'ECDSA', namedCurve: 'P-256' }, false, ['sign', 'verify']);
      const der = await crypto.subtle.exportKey('spki', keys.publicKey);
      const fingerprint = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', der)), byte => byte.toString(16).padStart(2, '0')).join('');
      identity = { privateKey: keys.privateKey, publicKey: `-----BEGIN PUBLIC KEY-----\n${toBase64(der).match(/.{1,64}/g)!.join('\n')}\n-----END PUBLIC KEY-----`, fingerprint };
    }
    // add rather than put: concurrent tabs must converge on one stored key.
    await new Promise<void>((resolve, reject) => {
      const transaction = db.transaction('identities', 'readwrite');
      transaction.objectStore('identities').add(identity, BROWSER_KEY);
      transaction.oncomplete = () => resolve(); transaction.onabort = () => reject(transaction.error);
    }).catch(async () => {
      const winner = await new Promise<Identity>((resolve, reject) => {
        const request = db.transaction('identities').objectStore('identities').get(BROWSER_KEY);
        request.onsuccess = () => request.result ? resolve(request.result) : reject(new Error('Device identity could not be saved'));
        request.onerror = () => reject(request.error);
      });
      identity = winner;
    });
    return identity!;
  } finally { db.close(); }
}
export function getDeviceIdentity(userId: string) {
  if (!pendingIdentity) {
    pendingIdentity = loadIdentity(userId);
    void pendingIdentity.catch(() => { pendingIdentity = undefined; });
  }
  return pendingIdentity;
}
export const browserFingerprint = (device: RegisteredDevice) => device.browser_fingerprint ?? device.device_fingerprint;
export const listDevices = () => apiRequest<RegisteredDevice[]>('/devices/my-devices');
export const changeDevice = (id: string, changes: { device_name?: string; is_active?: boolean }) => apiRequest<RegisteredDevice>(`/devices/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify(changes) });
export const removeDevice = (id: string) => apiRequest<void>(`/devices/${encodeURIComponent(id)}`, { method: 'DELETE' });
export async function registerCurrentDevice(userId: string) {
  const identity = await getDeviceIdentity(userId);
  const ua = navigator.userAgent;
  const platform = /iPhone|iPad|iPod/.test(ua) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1) ? 'ios' : /Android/.test(ua) ? 'android' : 'web';
  const browser = /Edg\//.test(ua) ? 'Edge' : /Chrome|CriOS/.test(ua) ? 'Chrome' : /Firefox|FxiOS/.test(ua) ? 'Firefox' : /Safari/.test(ua) ? 'Safari' : 'Browser';
  const devices = await listDevices();
  if (devices.filter(item => item.is_active).length > 2) throw new Error('Your account has more than two active devices. Disable extra devices in Profile → My devices before checking in.');
  const existing = devices.find(item => browserFingerprint(item) === identity.fingerprint);
  if (existing?.browser_identity_verified) return existing;
  const challenge = await apiRequest<{ challenge_id: string; challenge: string }>('/devices/registration-challenges', {
    method: 'POST', body: JSON.stringify({ device_fingerprint: identity.fingerprint, public_key: identity.publicKey }),
  });
  const signature = await crypto.subtle.sign({ name: 'ECDSA', hash: 'SHA-256' }, identity.privateKey, new TextEncoder().encode(challenge.challenge));
  return apiRequest<RegisteredDevice>('/devices/register', { method: 'POST', body: JSON.stringify({ device_fingerprint: identity.fingerprint, public_key: identity.publicKey, registration_challenge_id: challenge.challenge_id, registration_signature: toBase64(signature), device_name: `${platform === 'ios' ? 'iPhone / iPad' : platform === 'android' ? 'Android' : 'Computer'} · ${browser}`, platform, browser }) });
}
export async function createDeviceProof(userId: string, sessionId: string) {
  const device = await registerCurrentDevice(userId);
  if (!device.is_active) throw new Error('This device is disabled. Enable it under Profile → My devices.');
  const identity = await getDeviceIdentity(userId);
  const challenge = await apiRequest<{ challenge_id: string; challenge: string }>('/devices/challenges', { method: 'POST', body: JSON.stringify({ device_fingerprint: identity.fingerprint, session_id: sessionId }) });
  const signature = await crypto.subtle.sign({ name: 'ECDSA', hash: 'SHA-256' }, identity.privateKey, new TextEncoder().encode(challenge.challenge));
  return { device_fingerprint: identity.fingerprint, device_challenge_id: challenge.challenge_id, device_signature: toBase64(signature) };
}
