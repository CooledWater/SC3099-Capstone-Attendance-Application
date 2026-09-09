import type { Session } from '@/types/api';

const DATABASE_NAME = 'saiv-offline';
const DATABASE_VERSION = 1;
const SESSION_STORE = 'session-snapshots';
const ACTIVE_SESSIONS_KEY = 'active-sessions';
const SNAPSHOT_MAX_AGE_MS = 15 * 60 * 1000;

type SessionSnapshot = {
  key: typeof ACTIVE_SESSIONS_KEY;
  cachedAt: number;
  sessions: Session[];
};

export type CachedActiveSessions = {
  cachedAt: Date;
  sessions: Session[];
};

function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof window === 'undefined' || !('indexedDB' in window)) {
      reject(new Error('IndexedDB is unavailable'));
      return;
    }

    const request = window.indexedDB.open(DATABASE_NAME, DATABASE_VERSION);
    request.onupgradeneeded = () => {
      if (!request.result.objectStoreNames.contains(SESSION_STORE)) {
        request.result.createObjectStore(SESSION_STORE, { keyPath: 'key' });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error ?? new Error('Could not open IndexedDB'));
    request.onblocked = () => reject(new Error('IndexedDB upgrade was blocked'));
  });
}

function sanitizeSession(session: Session): Session {
  return {
    id: session.id,
    course_code: session.course_code,
    name: session.name,
    status: session.status,
    scheduled_start: session.scheduled_start,
    scheduled_end: session.scheduled_end,
    checkin_opens_at: session.checkin_opens_at,
    checkin_closes_at: session.checkin_closes_at,
    venue_name: session.venue_name,
  };
}

export async function cacheActiveSessions(sessions: Session[]): Promise<void> {
  const database = await openDatabase();

  try {
    await new Promise<void>((resolve, reject) => {
      const transaction = database.transaction(SESSION_STORE, 'readwrite');
      transaction.objectStore(SESSION_STORE).put({
        key: ACTIVE_SESSIONS_KEY,
        cachedAt: Date.now(),
        sessions: sessions.map(sanitizeSession),
      } satisfies SessionSnapshot);
      transaction.oncomplete = () => resolve();
      transaction.onerror = () => reject(transaction.error ?? new Error('Could not cache sessions'));
      transaction.onabort = () => reject(transaction.error ?? new Error('Caching sessions was aborted'));
    });
  } finally {
    database.close();
  }
}

export async function getCachedActiveSessions(): Promise<CachedActiveSessions | null> {
  const database = await openDatabase();

  try {
    const snapshot = await new Promise<SessionSnapshot | undefined>((resolve, reject) => {
      const transaction = database.transaction(SESSION_STORE, 'readonly');
      const request = transaction.objectStore(SESSION_STORE).get(ACTIVE_SESSIONS_KEY);
      request.onsuccess = () => resolve(request.result as SessionSnapshot | undefined);
      request.onerror = () => reject(request.error ?? new Error('Could not read cached sessions'));
    });

    if (!snapshot || Date.now() - snapshot.cachedAt > SNAPSHOT_MAX_AGE_MS) return null;

    const now = Date.now();
    return {
      cachedAt: new Date(snapshot.cachedAt),
      sessions: snapshot.sessions.filter(session => {
        const closesAt = Date.parse(session.checkin_closes_at);
        return Number.isFinite(closesAt) && closesAt >= now;
      }),
    };
  } finally {
    database.close();
  }
}
