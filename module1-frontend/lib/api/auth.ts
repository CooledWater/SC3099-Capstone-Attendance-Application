import { apiRequest, clearTokens, setAccessToken, storeRefreshToken } from './client';
import type { LoginResponse, User } from '@/types/api';

export async function login(email: string, password: string) {
  const result = await apiRequest<LoginResponse>('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) });
  setAccessToken(result.access_token); storeRefreshToken(result.refresh_token);
  return result.user;
}

export function register(fullName: string, email: string, password: string) {
  return apiRequest<User>('/auth/register', { method: 'POST', body: JSON.stringify({ full_name: fullName, email, password, role: 'student' }) });
}

export async function logout() {
  try { await apiRequest<void>('/auth/logout', { method: 'POST' }); } catch { /* Local logout must always succeed. */ }
  clearTokens();
}

export const getMe = () => apiRequest<User>('/users/me');
export const updateConsent = (camera: boolean, geolocation: boolean) =>
  apiRequest<User>('/users/me', { method: 'PUT', body: JSON.stringify({ camera_consent: camera, geolocation_consent: geolocation }) });

