import type { AuthTokens } from '@/types/api';

const configuredBase = process.env.NEXT_PUBLIC_API_URL ?? '/api/v1';
export const API_BASE = configuredBase.replace(/\/$/, '');
// Kept only to remove refresh tokens stored by older frontend versions.
const REFRESH_KEY = 'saiv_refresh_token';
let accessToken = '';
let authEpoch = 0;
let refreshInFlight: Promise<boolean> | undefined;
let refreshController: AbortController | undefined;

export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); }
}

export function setAccessToken(token: string) {
  authEpoch++; refreshController?.abort(); refreshInFlight = undefined; accessToken = token;
}
export function clearTokens() {
  authEpoch++; refreshController?.abort(); refreshInFlight = undefined; accessToken = '';
  try { sessionStorage.removeItem(REFRESH_KEY); } catch { /* Storage is optional. */ }
}

async function parseError(response: Response) {
  const body = await response.json().catch(() => ({}));
  const detail = body.detail ?? body.message;
  return typeof detail === 'string' ? detail : 'The request could not be completed.';
}

export function isConnectivityError(error: unknown): boolean {
  return error instanceof TypeError || (error instanceof ApiError && [408, 502, 503, 504].includes(error.status));
}

async function refreshSession(): Promise<boolean> {
  const epoch = authEpoch;
  const controller = new AbortController();
  refreshController = controller;
  const timeout = window.setTimeout(() => controller.abort(), 3000);
  try {
    const response = await fetch(`${API_BASE}/auth/refresh`, {
      method: 'POST', credentials: 'include', signal: controller.signal,
    });
    if (epoch !== authEpoch) return false;
    if (!response.ok) {
      accessToken = '';
      if (response.status !== 401 && response.status !== 403) throw new ApiError('Could not restore your session.', response.status);
      return false;
    }
    const tokens = await response.json() as AuthTokens;
    if (epoch !== authEpoch) return false;
    accessToken = tokens.access_token;
    return true;
  } catch (error) {
    if (epoch !== authEpoch) return false;
    accessToken = '';
    throw error;
  } finally {
    window.clearTimeout(timeout);
    if (refreshController === controller) refreshController = undefined;
  }
}

export async function refreshAccessToken(throwOnUnavailable = false): Promise<boolean> {
  if (!refreshInFlight) {
    const pending = refreshSession();
    refreshInFlight = pending;
    void pending.finally(() => { if (refreshInFlight === pending) refreshInFlight = undefined; }).catch(() => undefined);
  }
  try { return await refreshInFlight; }
  catch (error) { if (throwOnUnavailable) throw error; return false; }
}

export async function apiRequest<T>(path: string, options: RequestInit = {}, retry401 = true, timeoutMs = 15000): Promise<T> {
  const epoch = authEpoch;
  const sentToken = accessToken;
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      ...options, credentials: 'include', signal: controller.signal,
      headers: { 'Content-Type': 'application/json', ...(accessToken && { Authorization: `Bearer ${accessToken}` }), ...options.headers },
    });
    if (epoch !== authEpoch) throw new ApiError('Your session changed. Please retry.', 401);
    if (response.status === 401 && retry401) {
      // A slower 401 may arrive after another request has already refreshed.
      const restored = (accessToken && sentToken !== accessToken) || await refreshAccessToken();
      if (epoch !== authEpoch) throw new ApiError('Your session changed. Please retry.', 401);
      if (restored) return apiRequest<T>(path, options, false, timeoutMs);
    }
    if (!response.ok) throw new ApiError(await parseError(response), response.status);
    if (response.status === 204) return undefined as T;
    return response.json() as Promise<T>;
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw new ApiError('The server took too long to respond.', 408);
    throw error;
  } finally { window.clearTimeout(timeout); }
}
