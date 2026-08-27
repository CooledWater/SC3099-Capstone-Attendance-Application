import type { AuthTokens } from '@/types/api';

const configuredBase = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000/api/v1';
export const API_BASE = configuredBase.replace(/\/$/, '');
const REFRESH_KEY = 'saiv_refresh_token';
let accessToken = '';

export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); }
}

export function setAccessToken(token: string) { accessToken = token; }
export function storeRefreshToken(token: string) { sessionStorage.setItem(REFRESH_KEY, token); }
export function clearTokens() { accessToken = ''; sessionStorage.removeItem(REFRESH_KEY); }

async function parseError(response: Response) {
  const body = await response.json().catch(() => ({}));
  const detail = body.detail ?? body.message;
  return typeof detail === 'string' ? detail : 'The request could not be completed.';
}

export async function refreshAccessToken() {
  const refreshToken = sessionStorage.getItem(REFRESH_KEY);
  if (!refreshToken) return false;
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 3000);
  try {
    const response = await fetch(`${API_BASE}/auth/refresh`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: controller.signal,
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!response.ok) { clearTokens(); return false; }
    const tokens = await response.json() as AuthTokens;
    setAccessToken(tokens.access_token); storeRefreshToken(tokens.refresh_token);
    return true;
  } catch {
    clearTokens();
    return false;
  } finally { window.clearTimeout(timeout); }
}

export async function apiRequest<T>(path: string, options: RequestInit = {}, retry401 = true): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      ...options, signal: controller.signal,
      headers: { 'Content-Type': 'application/json', ...(accessToken && { Authorization: `Bearer ${accessToken}` }), ...options.headers },
    });
    if (response.status === 401 && retry401 && await refreshAccessToken()) return apiRequest<T>(path, options, false);
    if (!response.ok) throw new ApiError(await parseError(response), response.status);
    if (response.status === 204) return undefined as T;
    return response.json() as Promise<T>;
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw new ApiError('The server took too long to respond.', 408);
    throw error;
  } finally { window.clearTimeout(timeout); }
}
