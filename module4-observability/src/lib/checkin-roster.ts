import { api } from "./api";
import type { RawCheckIn } from "./attendance";

export type Verification = RawCheckIn["status"];
export type Attendance = "present" | "absent";
export type RosterEntry = {
  student_id: string;
  student_name: string;
  student_email: string;
  checkin_id: string | null;
  checked_in_at: string | null;
  attendance: Attendance;
  status: Verification | null;
  risk_score: number | null;
};
export type SessionAttendance = {
  session_id: string;
  course_id: string;
  session_status: string;
  expected: number;
  items: RosterEntry[];
  summary: Record<Attendance, number> & {
    attendance_rate: number;
    verification: Record<Verification, number>;
  };
};
export type RosterSession = {
  id: string;
  course_id: string;
  name: string;
  scheduled_start: string;
  scheduled_end: string;
  status: string;
};
export type RiskFactor = {
  type?: string;
  signal_type?: string;
  severity?: string;
  weight?: number;
};
export type CheckInDetails = RawCheckIn & {
  course_id: string;
  student_id: string;
  risk_factors?: (RiskFactor | string)[];
  appeal_reason: string | null;
  review_notes: string | null;
};
export type FlaggedCheckIn = RawCheckIn & {
  risk_factors: (RiskFactor | string)[];
  appeal_reason?: string | null;
};
export const attendanceLabels: Record<Attendance, string> = {
  present: "Present",
  absent: "Absent",
};

// Consume every page before filtering locally. AbortSignal belongs to the
// query's course/session key so navigation cannot display a stale response.
async function allPages<T>(path: string, signal?: AbortSignal): Promise<T[]> {
  const items: T[] = [];
  while (true) {
    const page = await api.request<{ items: T[]; total: number }>(
      `${path}&limit=100&offset=${items.length}`,
      { signal: signal ?? null },
    );
    items.push(...page.items);
    if (!page.items.length || items.length >= page.total) return items;
  }
}
export async function fetchCourseSessions(course: string, signal?: AbortSignal) {
  const rows = await allPages<RosterSession>(
    `/sessions/?course_id=${encodeURIComponent(course)}`,
    signal,
  );
  return rows
    .filter(
      (row) => row.course_id === course && (row.status === "active" || row.status === "closed"),
    )
    .sort((a, b) => Date.parse(b.scheduled_start) - Date.parse(a.scheduled_start));
}
export const fetchSessionAttendance = (session: string, signal?: AbortSignal) =>
  api.request<SessionAttendance>(`/sessions/${encodeURIComponent(session)}/attendance`, {
    signal: signal ?? null,
  });
export const fetchFlaggedSession = (course: string, session: string, signal?: AbortSignal) =>
  allPages<FlaggedCheckIn>(
    `/checkins/flagged?course_id=${encodeURIComponent(course)}&session_id=${encodeURIComponent(session)}`,
    signal,
  );

export function filterRoster(
  rows: RosterEntry[],
  search: string,
  attendance: string,
  verification: string[],
  flaggedIds?: Set<string>,
) {
  const term = search.trim().toLocaleLowerCase();
  return rows
    .filter(
      (row) =>
        (!term || `${row.student_name} ${row.student_email}`.toLocaleLowerCase().includes(term)) &&
        (attendance === "all" || row.attendance === attendance) &&
        (!verification.length || verification.includes(row.status ?? "none")) &&
        (!flaggedIds ||
          !verification.length ||
          !verification.every((value) => value === "flagged" || value === "appealed") ||
          (!!row.checkin_id && flaggedIds.has(row.checkin_id))),
    )
    .sort((a, b) => {
      if (!a.checked_in_at)
        return b.checked_in_at ? 1 : a.student_name.localeCompare(b.student_name);
      if (!b.checked_in_at) return -1;
      return (
        Date.parse(b.checked_in_at) - Date.parse(a.checked_in_at) ||
        a.student_name.localeCompare(b.student_name)
      );
    });
}

export function factorLabel(type: string) {
  const known: Record<string, string> = {
    geo_out_of_bounds: "Outside permitted location",
    geo_accuracy_low: "Low location accuracy",
    impossible_travel: "Impossible travel",
    device_unknown: "Unknown device",
    device_emulator: "Device emulator",
    device_rooted: "Rooted device",
    attestation_failed: "Device attestation failed",
    vpn_detected: "VPN detected",
    proxy_detected: "Proxy detected",
    tor_detected: "Tor detected",
    suspicious_ip: "Suspicious IP address",
    liveness_failed: "Liveness check failed",
    liveness_low_confidence: "Low liveness confidence",
    face_match_failed: "Face match failed",
    face_match_low_confidence: "Low face match confidence",
    replay_suspected: "Suspected replay",
    deepfake_suspected: "Suspected deepfake",
    rapid_succession: "Rapid submissions",
    unusual_time: "Unusual time",
    pattern_anomaly: "Unusual pattern",
  };
  return (
    known[type] ??
    (type.replace(/[_-]+/g, " ").replace(/^./, (c) => c.toUpperCase()) || "Unknown factor")
  );
}

export const reviewCheckIn = (id: string, status: "approved" | "rejected", notes: string) =>
  api.request<{ id: string; status: Verification }>(`/checkins/${encodeURIComponent(id)}/review`, {
    method: "POST",
    body: JSON.stringify({ status, review_notes: notes.trim() || null }),
  });
