export type User = {
  id: string;
  email: string;
  full_name: string;
  role: 'student' | 'ta' | 'instructor' | 'admin';
  camera_consent?: boolean;
  geolocation_consent?: boolean;
};

export type AuthTokens = { access_token: string; refresh_token: string; token_type: 'bearer' };
export type LoginResponse = AuthTokens & { user: User };

export type Session = {
  id: string;
  course_code?: string;
  name: string;
  status: 'scheduled' | 'active' | 'closed' | 'cancelled';
  scheduled_start: string;
  scheduled_end: string;
  checkin_opens_at: string;
  checkin_closes_at: string;
  venue_name?: string;
};

export type CheckInRequest = {
  session_id: string;
  latitude: number;
  longitude: number;
  location_accuracy_meters: number;
  device_fingerprint: string;
  liveness_challenge_response?: string;
};

export type CheckIn = {
  id: string;
  session_id: string;
  status: 'pending' | 'approved' | 'flagged' | 'rejected';
  checked_in_at: string;
  risk_score: number;
  liveness_passed?: boolean;
};

