import { apiRequest } from './api/client';

type PushConfig = { enabled: boolean; public_key: string | null };
export const getPushConfig = () => apiRequest<PushConfig>('/push/config');

export function pushSupported() {
  return window.isSecureContext && 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
}

// Shared with sw.js: no credentials or attendance details are stored here.
export async function pushOwner(userId?: string): Promise<string | undefined> {
  const db = await new Promise<IDBDatabase>((resolve, reject) => {
    const request = indexedDB.open('saiv-push', 1);
    request.onupgradeneeded = () => request.result.createObjectStore('settings');
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
  try {
    return await new Promise((resolve, reject) => {
      const writing = userId !== undefined;
      const transaction = db.transaction('settings', writing ? 'readwrite' : 'readonly');
      const store = transaction.objectStore('settings');
      const request = writing ? store.put(userId, 'owner') : store.get('owner');
      transaction.oncomplete = () => resolve(writing ? userId : request.result as string | undefined);
      transaction.onabort = () => reject(transaction.error);
      transaction.onerror = () => reject(transaction.error);
    });
  } finally { db.close(); }
}

async function registration() {
  const current = await navigator.serviceWorker.getRegistration('/');
  if (!current?.active) throw new Error('The app is updating. Reload it, then enable notifications.');
  return current;
}

export async function syncPush(userId: string) {
  if (!pushSupported()) return false;
  if (await pushOwner() !== userId) {
    await pushOwner('');
    return false;
  }
  const current = await navigator.serviceWorker.getRegistration('/');
  const subscription = await current?.pushManager.getSubscription();
  if (!subscription || Notification.permission !== 'granted') { await pushOwner(''); return false; }
  await apiRequest<void>('/push/subscriptions', { method: 'PUT', body: JSON.stringify(subscription.toJSON()) });
  return true;
}

export async function enablePush(userId: string) {
  // Called only by a button; Safari requires permission requests within a user gesture.
  const permission = await Notification.requestPermission();
  if (permission !== 'granted') throw new Error('Notifications are blocked. Allow them in your browser or device settings.');
  const config = await getPushConfig();
  if (!config.enabled || !config.public_key) throw new Error('Notifications are not configured yet. Please try again later.');
  const current = await registration();
  let subscription = await current.pushManager.getSubscription();
  const key = Uint8Array.from(atob(config.public_key.replace(/-/g, '+').replace(/_/g, '/')), char => char.charCodeAt(0));
  // A server key rotation requires a fresh browser subscription.
  if (subscription && (!subscription.options.applicationServerKey ||
      Array.from(new Uint8Array(subscription.options.applicationServerKey)).join() !== Array.from(key).join())) {
    await subscription.unsubscribe(); subscription = null;
  }
  subscription ??= await current.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: key });
  await apiRequest<void>('/push/subscriptions', { method: 'PUT', body: JSON.stringify(subscription.toJSON()) });
  await pushOwner(userId);
}

export async function disablePush() {
  // Hide any in-flight notification even if offline/server cleanup fails.
  await pushOwner('');
  if (!('serviceWorker' in navigator)) return;
  const current = await navigator.serviceWorker.getRegistration('/');
  const subscription = await current?.pushManager.getSubscription();
  const notifications = await current?.getNotifications();
  notifications?.forEach(notification => notification.close());
  if (!subscription) return;
  try {
    if (navigator.onLine) await apiRequest<void>('/push/subscriptions/remove', { method: 'POST', body: JSON.stringify({ endpoint: subscription.endpoint }) });
  } finally { await subscription.unsubscribe(); }
}
