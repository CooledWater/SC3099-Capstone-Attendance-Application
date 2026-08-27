import { apiRequest } from './client';
import type { CheckIn, CheckInRequest, Session } from '@/types/api';

export const getActiveSessions = () => apiRequest<Session[]>('/sessions/active');
export const submitCheckIn = (payload: CheckInRequest) =>
  apiRequest<CheckIn>('/checkins/', { method: 'POST', body: JSON.stringify(payload) });

