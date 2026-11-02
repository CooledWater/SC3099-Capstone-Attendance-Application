import { parseApiDateTime } from '@/lib/time';
import type { CheckIn, Session } from '@/types/api';

const DATABASE_NAME = 'saiv-offline';
const DATABASE_VERSION = 2;
const SESSION_STORE = 'session-snapshots';
const ACTIVE_SESSIONS_KEY = 'active-sessions';
const OWNER_KEY = 'saiv-offline-owner';

// This account identifier enables read-only viewing; it never authenticates.
export function getOfflineAccount(): string | null {
  try { return localStorage.getItem(OWNER_KEY); } catch { return null; }
}

export function setOfflineAccount(userId: string): void {
  try { localStorage.setItem(OWNER_KEY, userId); } catch { /* Offline storage is optional. */ }
}

export type SavedAttendance = Pick<CheckIn, 'status' | 'checked_in_at'> & { risk_score?: number };
export type CachedSession = Session & { attendance?: SavedAttendance | null };

export function sessionAvailableOffline(session: Session, now = Date.now()): boolean {
  return session.status !== 'cancelled' && parseApiDateTime(session.scheduled_end).getTime() > now;
}

type SessionSnapshot = {
  key: string;
  cachedAt: number;
  sessions: CachedSession[];
};

export type CachedActiveSessions = {
  cachedAt: Date;
  sessions: CachedSession[];
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
      } else {
        request.transaction!.objectStore(SESSION_STORE).clear();
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error ?? new Error('Could not open IndexedDB'));
    request.onblocked = () => reject(new Error('IndexedDB upgrade was blocked'));
  });
}

function sanitizeSession(session: CachedSession): CachedSession {
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
    ...(session.attendance !== undefined && { attendance: session.attendance ? {
      status: session.attendance.status, checked_in_at: session.attendance.checked_in_at,
      ...(typeof session.attendance.risk_score === 'number' && Number.isFinite(session.attendance.risk_score)
        && session.attendance.risk_score >= 0 && session.attendance.risk_score <= 1
        && { risk_score: session.attendance.risk_score }),
    } : null }),
  };
}

export async function cacheActiveSessions(userId: string, sessions: CachedSession[]): Promise<void> {
  const database = await openDatabase();

  try {
    if (getOfflineAccount() !== userId) return;
    await new Promise<void>((resolve, reject) => {
      const transaction = database.transaction(SESSION_STORE, 'readwrite');
      const store = transaction.objectStore(SESSION_STORE);
      const key = `${ACTIVE_SESSIONS_KEY}:${userId}`;
      const request = store.get(key);
      request.onsuccess = () => {
        // Read and merge in one transaction: a status update cannot overwrite a
        // concurrent session refresh, and an empty active list retains unended sessions.
        if (getOfflineAccount() !== userId) return;
        const previous = request.result as SessionSnapshot | undefined;
        const merged = new Map((previous?.sessions ?? []).map(session => [session.id, sanitizeSession(session)]));
        for (const session of sessions) merged.set(session.id, { ...merged.get(session.id), ...sanitizeSession(session) });
        store.put({ key, cachedAt: Date.now(), sessions: Array.from(merged.values())
          .filter(session => sessionAvailableOffline(session))
          .sort((a, b) => parseApiDateTime(b.scheduled_start).getTime() - parseApiDateTime(a.scheduled_start).getTime())
          .slice(0, 100) } satisfies SessionSnapshot);
      };
      transaction.oncomplete = () => resolve();
      transaction.onerror = () => reject(transaction.error ?? new Error('Could not cache sessions'));
      transaction.onabort = () => reject(transaction.error ?? new Error('Caching sessions was aborted'));
    });
  } finally {
    database.close();
  }
}

export async function cacheSessionAttendance(userId: string, session: Session, result?: CheckIn): Promise<void> {
  await cacheActiveSessions(userId, [{ ...session, attendance: result ?? null }]);
}

export async function getCachedActiveSessions(userId: string): Promise<CachedActiveSessions | null> {
  const database = await openDatabase();

  try {
    const snapshot = await new Promise<SessionSnapshot | undefined>((resolve, reject) => {
      const transaction = database.transaction(SESSION_STORE, 'readonly');
      const request = transaction.objectStore(SESSION_STORE).get(`${ACTIVE_SESSIONS_KEY}:${userId}`);
      request.onsuccess = () => resolve(request.result as SessionSnapshot | undefined);
      request.onerror = () => reject(request.error ?? new Error('Could not read cached sessions'));
    });

    if (getOfflineAccount() !== userId || !snapshot || snapshot.cachedAt > Date.now()) return null;

    const now = Date.now();
    return {
      cachedAt: new Date(snapshot.cachedAt),
      sessions: snapshot.sessions.filter(session => sessionAvailableOffline(session, now)).map(sanitizeSession),
    };
  } finally {
    database.close();
  }
}

export async function clearOfflineSessions(): Promise<void> {
  try { localStorage.removeItem(OWNER_KEY); } catch { /* Storage may be disabled. */ }
  const database = await openDatabase();
  try {
    await new Promise<void>((resolve, reject) => {
      const transaction = database.transaction(SESSION_STORE, 'readwrite');
      transaction.objectStore(SESSION_STORE).clear();
      transaction.oncomplete = () => resolve();
      transaction.onerror = () => reject(transaction.error);
      transaction.onabort = () => reject(transaction.error);
    });
  } finally { database.close(); }
}
