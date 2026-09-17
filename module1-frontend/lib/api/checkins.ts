import { apiRequest } from './client';
import type { CheckIn, CheckInRequest, Session } from '@/types/api';

export const getActiveSessions = () => apiRequest<Session[]>('/sessions/active');
export const submitCheckIn = (payload: CheckInRequest) =>
  apiRequest<CheckIn>('/checkins/', { method: 'POST', body: JSON.stringify(payload) });


export const enrollFace = (image: string) => apiRequest<{ face_enrolled: boolean }>('/users/me/face/enroll', { method: 'POST', body: JSON.stringify({ image }) });
export const startMotion = (session_id: string) => apiRequest<{ challenge_id: string; expires_at: string }>('/motion/challenges', { method: 'POST', body: JSON.stringify({ session_id }) });
export const verifyMotion = (id: string, frames: { image: string; timestamp_ms: number }[]) => apiRequest<{ passed: boolean; verification_id: string | null; blink_count: number }>(`/motion/challenges/${id}/verify`, { method: 'POST', body: JSON.stringify({ frames }) }, true, 55000);
