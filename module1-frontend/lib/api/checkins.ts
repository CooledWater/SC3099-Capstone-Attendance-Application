import { apiRequest } from './client';
import type { CheckIn, CheckInRequest, Session } from '@/types/api';

export const getActiveSessions = () => apiRequest<Session[]>('/sessions/active', {}, true, 6000);
export async function getRecentSessionSnapshot() {
  const now = Date.now();
  const query = new URLSearchParams({ start_date: new Date(now - 86400000).toISOString(), end_date: new Date(now + 60000).toISOString(), limit: '100' });
  const [sessions, checkins] = await Promise.all([
    apiRequest<Session[]>(`/sessions/my-sessions?${query}`, {}, true, 6000),
    apiRequest<CheckIn[]>('/checkins/my-checkins?limit=100', {}, true, 6000),
  ]);
  return { sessions, checkins };
}

export const getMySessionCheckIn = async (sessionId: string): Promise<CheckIn | undefined> => {
  const records = await apiRequest<CheckIn[]>(`/checkins/my-checkins?session_id=${encodeURIComponent(sessionId)}&limit=1`, {}, true, 6000);
  return records.find(record => record.session_id === sessionId);
};
export const submitCheckIn = (payload: CheckInRequest) =>
  apiRequest<CheckIn>('/checkins/', { method: 'POST', body: JSON.stringify(payload) });


export const enrollFace = (image: string) => apiRequest<{ face_enrolled: boolean }>('/users/me/face/enroll', { method: 'POST', body: JSON.stringify({ image }) });
export const startMotion = (session_id: string) => apiRequest<{ challenge_id: string; expires_at: string }>('/motion/challenges', { method: 'POST', body: JSON.stringify({ session_id }) });
export const verifyMotion = (id: string, frames: { image: string; timestamp_ms: number }[]) => apiRequest<{ passed: boolean; verification_id: string | null; blink_count: number }>(`/motion/challenges/${id}/verify`, { method: 'POST', body: JSON.stringify({ frames }) }, true, 55000);
