import type { AuthTokens } from '@/types/api';

const configuredBase = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000/api/v1';
export const API_BASE = configuredBase.replace(/\/$/, '');
// Kept only to remove refresh tokens stored by older frontend versions.
const REFRESH_KEY = 'saiv_refresh_token';
let accessToken = '';

export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); }
}

export function setAccessToken(token: string) { accessToken = token; }
export function clearTokens() { accessToken = ''; sessionStorage.removeItem(REFRESH_KEY); }

async function parseError(response: Response) {
  const body = await response.json().catch(() => ({}));
  const detail = body.detail ?? body.message;
  return typeof detail === 'string' ? detail : 'The request could not be completed.';
}

export function isConnectivityError(error: unknown): boolean {
  return error instanceof TypeError || (error instanceof ApiError && error.status === 408);
}

export async function refreshAccessToken(throwOnUnavailable = false) {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 3000);
  try {
    const response = await fetch(`${API_BASE}/auth/refresh`, {
      method: 'POST', credentials: 'include', signal: controller.signal,
    });
    if (!response.ok) {
      clearTokens();
      if (throwOnUnavailable && response.status !== 401 && response.status !== 403) {
        throw new ApiError('Could not restore your session.', response.status);
      }
      return false;
    }
    const tokens = await response.json() as AuthTokens;
    setAccessToken(tokens.access_token);
    return true;
  } catch (error) {
    clearTokens();
    if (throwOnUnavailable) throw error;
    return false;
  } finally { window.clearTimeout(timeout); }
}

export async function apiRequest<T>(path: string, options: RequestInit = {}, retry401 = true, timeoutMs = 15000): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      ...options, credentials: 'include', signal: controller.signal,
      headers: { 'Content-Type': 'application/json', ...(accessToken && { Authorization: `Bearer ${accessToken}` }), ...options.headers },
    });
    if (response.status === 401 && retry401 && await refreshAccessToken()) return apiRequest<T>(path, options, false, timeoutMs);
    if (!response.ok) throw new ApiError(await parseError(response), response.status);
    if (response.status === 204) return undefined as T;
    return response.json() as Promise<T>;
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw new ApiError('The server took too long to respond.', 408);
    throw error;
  } finally { window.clearTimeout(timeout); }
}
