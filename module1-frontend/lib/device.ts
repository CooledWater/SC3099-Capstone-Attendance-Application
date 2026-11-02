import { apiRequest, ApiError } from './api/client';
import { parseApiDateTime } from './time';

export type RegisteredDevice = {
  id: string; device_fingerprint: string; device_name: string | null; platform: string | null;
  browser_fingerprint?: string | null; shared_browser?: boolean; browser_identity_verified?: boolean;
  public_key_created_at?: string | null; public_key_expires_at?: string | null;
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
    const pending = pendingIdentity;
    void pending.finally(() => { if (pendingIdentity === pending) pendingIdentity = undefined; }).catch(() => undefined);
  }
  return pendingIdentity;
}
export const browserFingerprint = (device: RegisteredDevice) => device.browser_fingerprint ?? device.device_fingerprint;
export const listDevices = () => apiRequest<RegisteredDevice[]>('/devices/my-devices');
export const changeDevice = (id: string, changes: { device_name?: string; is_active?: boolean }) => apiRequest<RegisteredDevice>(`/devices/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify(changes) });
export const removeDevice = (id: string) => apiRequest<void>(`/devices/${encodeURIComponent(id)}`, { method: 'DELETE' });
export async function registerCurrentDevice(userId: string) {
  await resumeKeyRotation(userId);
  const identity = await getDeviceIdentity(userId);
  const ua = navigator.userAgent;
  const platform = /iPhone|iPad|iPod/.test(ua) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1) ? 'ios' : /Android/.test(ua) ? 'android' : 'web';
  const browser = /Edg\//.test(ua) ? 'Edge' : /Chrome|CriOS/.test(ua) ? 'Chrome' : /Firefox|FxiOS/.test(ua) ? 'Firefox' : /Safari/.test(ua) ? 'Safari' : 'Browser';
  const devices = await listDevices();
  if (devices.filter(item => item.is_active).length > 2) throw new Error('Your account has more than two active devices. Remove extra devices in Profile → My devices before checking in.');
  const existing = devices.find(item => browserFingerprint(item) === identity.fingerprint);
  if (existing?.browser_identity_verified) {
    if (existing.is_active && existing.public_key_expires_at && parseApiDateTime(existing.public_key_expires_at).getTime() <= Date.now() + 7 * 86400000) {
      await rotateDeviceKey(userId);
      return (await listDevices()).find(item => item.id === existing.id)!;
    }
    return existing;
  }
  const challenge = await apiRequest<{ challenge_id: string; challenge: string }>('/devices/registration-challenges', {
    method: 'POST', body: JSON.stringify({ device_fingerprint: identity.fingerprint, public_key: identity.publicKey }),
  });
  const signature = await crypto.subtle.sign({ name: 'ECDSA', hash: 'SHA-256' }, identity.privateKey, new TextEncoder().encode(challenge.challenge));
  return apiRequest<RegisteredDevice>('/devices/register', { method: 'POST', body: JSON.stringify({ device_fingerprint: identity.fingerprint, public_key: identity.publicKey, registration_challenge_id: challenge.challenge_id, registration_signature: toBase64(signature), device_name: `${platform === 'ios' ? 'iPhone / iPad' : platform === 'android' ? 'Android' : 'Computer'} · ${browser}`, platform, browser }) });
}
export async function createDeviceProof(userId: string, sessionId: string) {
  const device = await registerCurrentDevice(userId);
  if (!device.is_active) throw new Error('This device registration has been removed or deactivated. Contact an administrator to reactivate it.');
  const identity = await getDeviceIdentity(userId);
  const challenge = await apiRequest<{ challenge_id: string; challenge: string }>('/devices/challenges', { method: 'POST', body: JSON.stringify({ device_fingerprint: identity.fingerprint, session_id: sessionId }) });
  const signature = await crypto.subtle.sign({ name: 'ECDSA', hash: 'SHA-256' }, identity.privateKey, new TextEncoder().encode(challenge.challenge));
  return { device_fingerprint: identity.fingerprint, device_challenge_id: challenge.challenge_id, device_signature: toBase64(signature) };
}


type PendingRotation = { userId: string; previous: Identity; next: Identity; challengeId: string; challenge: string };
const ROTATION_KEY = 'pending-signing-key-rotation-v1';
let rotationInFlight: Promise<void> | undefined;

async function storedRotation(): Promise<PendingRotation | undefined> {
  const db = await database();
  try { return await new Promise((resolve, reject) => {
    const request = db.transaction('identities').objectStore('identities').get(ROTATION_KEY);
    request.onsuccess = () => resolve(request.result); request.onerror = () => reject(request.error);
  }); } finally { db.close(); }
}

async function finishKeyRotation(pending: PendingRotation) {
  const sign = async (key: CryptoKey) => toBase64(await crypto.subtle.sign({ name: 'ECDSA', hash: 'SHA-256' }, key, new TextEncoder().encode(pending.challenge)));
  await apiRequest('/devices/key-rotation/complete', { method: 'POST', body: JSON.stringify({ challenge_id: pending.challengeId,
    old_signature: await sign(pending.previous.privateKey), new_signature: await sign(pending.next.privateKey) }) });
  const db = await database();
  try { await new Promise<void>((resolve, reject) => {
    const transaction = db.transaction('identities', 'readwrite');
    const store = transaction.objectStore('identities');
    const request = store.get(BROWSER_KEY);
    request.onsuccess = () => {
      const current = request.result as Identity;
      // A delayed response must never overwrite a newer key from another tab.
      if (current.publicKey === pending.previous.publicKey || current.publicKey === pending.next.publicKey) {
        store.put(pending.next, BROWSER_KEY);
        const stored = store.get(ROTATION_KEY);
        stored.onsuccess = () => { if (stored.result?.challengeId === pending.challengeId) store.delete(ROTATION_KEY); };
      }
    };
    transaction.oncomplete = () => resolve(); transaction.onabort = () => reject(transaction.error);
  }); } finally { db.close(); pendingIdentity = undefined; }
}

async function resumeKeyRotation(userId: string) {
  const pending = await storedRotation();
  if (!pending) return;
  if (pending.userId !== userId) throw new Error('Sign back into the account that started security-key renewal to finish it.');
  try { await finishKeyRotation(pending); }
  catch (error) {
    if (error instanceof ApiError && error.status === 409) {
      const db = await database();
      try { await new Promise<void>((resolve, reject) => {
        const transaction = db.transaction('identities', 'readwrite');
        const store = transaction.objectStore('identities');
        const current = store.get(ROTATION_KEY);
        current.onsuccess = () => { if (current.result?.challengeId === pending.challengeId) store.delete(ROTATION_KEY); };
        transaction.oncomplete = () => resolve(); transaction.onabort = () => reject(transaction.error);
      }); } finally { db.close(); }
    }
    throw error;
  }
}

export async function rotateDeviceKey(userId: string): Promise<void> {
  if (rotationInFlight) return rotationInFlight;
  const renew = async () => {
    if (await storedRotation()) { await resumeKeyRotation(userId); return; }
    const previous = await getDeviceIdentity(userId);
    const pair = await crypto.subtle.generateKey({ name: 'ECDSA', namedCurve: 'P-256' }, false, ['sign', 'verify']);
    const der = await crypto.subtle.exportKey('spki', pair.publicKey);
    const next: Identity = { privateKey: pair.privateKey, publicKey: `-----BEGIN PUBLIC KEY-----\n${toBase64(der).match(/.{1,64}/g)!.join('\n')}\n-----END PUBLIC KEY-----`, fingerprint: previous.fingerprint };
    const challenge = await apiRequest<{ challenge_id: string; challenge: string }>('/devices/key-rotation/challenges', {
      method: 'POST', body: JSON.stringify({ device_fingerprint: previous.fingerprint, new_public_key: next.publicKey }),
    });
    const pending: PendingRotation = { userId, previous, next, challengeId: challenge.challenge_id, challenge: challenge.challenge };
    // Save both non-exportable keys before changing the server: a dropped response is recoverable.
    const db = await database();
    let chosen: PendingRotation | undefined;
    try { await new Promise<void>((resolve, reject) => {
      const transaction = db.transaction('identities', 'readwrite');
      const store = transaction.objectStore('identities');
      const current = store.get(BROWSER_KEY);
      current.onsuccess = () => {
        if (current.result?.publicKey !== previous.publicKey) return;
        const existing = store.get(ROTATION_KEY);
        existing.onsuccess = () => {
          chosen = existing.result ?? pending;
          if (!existing.result) store.put(pending, ROTATION_KEY);
        };
      };
      transaction.oncomplete = () => resolve(); transaction.onabort = () => reject(transaction.error);
    }); } finally { db.close(); }
    if (chosen) await finishKeyRotation(chosen);
  };
  const operation = async () => {
    if ('locks' in navigator) await navigator.locks.request('saiv-browser-key-renewal', renew);
    else await renew();
  };
  rotationInFlight = operation();
  try { await rotationInFlight; } finally { rotationInFlight = undefined; }
}
