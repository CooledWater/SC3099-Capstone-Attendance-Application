import { api } from "@/lib/api";
import type { CheckInRow } from "@/components/dashboard/AttendanceTable";
import { parseApiDateTime } from "@/lib/time";

export type RawCheckIn = {
  id: string;
  student_name?: string;
  student_email?: string;
  student_id?: string;
  checked_in_at: string;
  status: "approved" | "flagged" | "rejected" | "pending" | "appealed";
  risk_score: number;
  liveness_score?: number | null;
  face_match_score?: number | null;
  latitude?: number | null;
  longitude?: number | null;
  session_id: string;
  session_name?: string | null;
  course_code?: string | null;
};
export type SessionRow = {
  id: string;
  course_id: string;
  instructor_id: string | null;
  name: string;
  status: "scheduled" | "active" | "closed" | "cancelled";
  starts_at: string;
  ends_at: string;
  actual_start?: string | null;
  actual_end?: string | null;
  checkin_opens_at: string;
  checkin_closes_at: string;
  room: string;
  expected_attendance: number;
  is_active: boolean;
  geofence_lat: number | null;
  geofence_lng: number | null;
  geofence_radius_m: number;
  courses: { code: string; name: string } | null;
};
export type ActiveSession = {
  id: string;
  course_id: string;
  name: string;
  course_code?: string | null;
  course_name?: string | null;
  venue_name?: string | null;
  checkin_closes_at: string;
};
export type CourseRow = {
  semester_start_date?: string | null;
  id: string;
  code: string;
  name: string;
  instructor_id?: string | null;
};
export type EnrollmentRow = {
  course_id: string;
  course_code: string;
  course_name: string;
};
type ApiSession = {
  id: string;
  course_id: string;
  instructor_id?: string | null;
  name: string;
  course_code?: string | null;
  course_name?: string | null;
  scheduled_start: string;
  scheduled_end: string;
  actual_start?: string | null;
  actual_end?: string | null;
  checkin_opens_at: string;
  checkin_closes_at: string;
  venue_name?: string | null;
  total_enrolled?: number;
  status: SessionRow["status"];
  venue_latitude?: number | null;
  venue_longitude?: number | null;
  geofence_radius_meters?: number | null;
};

export async function fetchSessions() {
  const result = await api.request<{ items: ApiSession[] }>("/sessions/?limit=100");
  return result.items.map(toSessionRow);
}

function toSessionRow(s: ApiSession): SessionRow {
  return {
    id: s.id,
    course_id: s.course_id,
    instructor_id: s.instructor_id ?? null,
    name: s.name,
    status: s.status,
    starts_at: s.scheduled_start,
    ends_at: s.scheduled_end,
    actual_start: s.actual_start ?? null,
    actual_end: s.actual_end ?? null,
    checkin_opens_at: s.checkin_opens_at,
    checkin_closes_at: s.checkin_closes_at,
    room: s.venue_name ?? "Not set",
    expected_attendance: s.total_enrolled ?? 0,
    is_active: s.status === "active",
    geofence_lat: s.venue_latitude ?? null,
    geofence_lng: s.venue_longitude ?? null,
    geofence_radius_m: s.geofence_radius_meters ?? 100,
    courses:
      s.course_code || s.course_name
        ? { code: s.course_code ?? "—", name: s.course_name ?? "Course" }
        : null,
  };
}

export async function fetchSessionsForCourses(courseIds: string[]) {
  if (courseIds.length === 0) return [];

  const responses = await Promise.all(
    courseIds.map((courseId) =>
      api.request<{ items: ApiSession[] }>(
        `/sessions/?course_id=${encodeURIComponent(courseId)}&limit=100`,
      ),
    ),
  );
  const sessions = new Map<string, ApiSession>();
  responses.forEach((response) => {
    response.items.forEach((session) => {
      if (courseIds.includes(session.course_id)) sessions.set(session.id, session);
    });
  });
  return [...sessions.values()].map(toSessionRow);
}

export async function fetchCheckInsForSessions(sessions: SessionRow[]) {
  const groups = await Promise.all(
    sessions.map(async (session) => {
      const items = await api.request<RawCheckIn[]>(`/checkins/session/${session.id}`);
      return items
        .filter((item) => item.session_id === session.id)
        .map((item) => ({
          ...item,
          session_name: session.courses?.name ?? null,
          course_code: session.courses?.code ?? null,
        }));
    }),
  );
  return groups.flat().sort((a, b) => Date.parse(b.checked_in_at) - Date.parse(a.checked_in_at));
}
export async function fetchCheckIns() {
  return fetchCheckInsForSessions(await fetchSessions());
}
export const fetchMyCheckIns = () => api.request<RawCheckIn[]>("/checkins/my-checkins?limit=100");
export async function fetchCourses() {
  const items: CourseRow[] = [];
  let total = Infinity;
  while (items.length < total) {
    const page = await api.request<{ items: CourseRow[]; total: number }>(`/courses/?limit=100&offset=${items.length}`);
    items.push(...page.items);
    total = page.total;
    if (!page.items.length) break;
  }
  return items;
}
export const fetchMyEnrollments = () => api.request<EnrollmentRow[]>("/enrollments/my-enrollments");
export const fetchActiveSessions = () => api.request<ActiveSession[]>("/sessions/active");
export async function fetchMyAssignedCourses() {
  return (await api.request<{ items: CourseRow[] }>("/courses/my-courses?limit=100")).items;
}

export function toRows(list: RawCheckIn[]): CheckInRow[] {
  return list.map((c) => ({
    id: c.id,
    student: c.student_name ?? "You",
    email: c.student_email ?? c.student_id ?? "—",
    course: c.course_code ?? "—",
    courseId: "",
    sessionId: c.session_id,
    room: "—",
    time: c.checked_in_at,
    status: c.status,
    risk: Math.round((c.risk_score ?? 0) * 100),
    liveness: c.liveness_score ?? 0,
    faceMatch: c.face_match_score ?? 0,
    lat: c.latitude ?? null,
    lng: c.longitude ?? null,
  }));
}
export function trendOf(rows: CheckInRow[]): [string, number][] {
  const buckets = new Map<string, number>();
  rows.forEach((r) => {
    const hour = new Intl.DateTimeFormat("en-GB", {
      timeZone: "Asia/Singapore",
      hour: "2-digit",
      hourCycle: "h23",
    }).format(parseApiDateTime(r.time));
    const key = `${hour}:00`;
    buckets.set(key, (buckets.get(key) ?? 0) + 1);
  });
  return [...buckets.entries()].sort((a, b) => a[0].localeCompare(b[0]));
}
export const statusText: Record<CheckInRow["status"], string> = {
  approved: "Approved",
  flagged: "Flagged",
  rejected: "Rejected",
  pending: "Pending",
  appealed: "Appealed",
};
export function submitCheckInAppeal(checkInId: string, appealReason: string) {
  return api.request<{
    id: string;
    status: "appealed";
    appeal_reason: string;
    appealed_at: string;
  }>(`/checkins/${encodeURIComponent(checkInId)}/appeal`, {
    method: "POST",
    body: JSON.stringify({ appeal_reason: appealReason }),
  });
}
export function checkInsToCsv(rows: CheckInRow[]) {
  const header = [
    "Check-in ID",
    "Student ID",
    "Session ID",
    "Timestamp",
    "Verification Status",
    "Risk Score",
    "Liveness Score",
    "Face Match Score",
    "Latitude",
    "Longitude",
  ];
  const esc = (v: string) => `"${v.replace(/"/g, '""')}"`;
  const lines = rows.map((r) =>
    [
      r.id,
      r.email,
      r.sessionId,
      parseApiDateTime(r.time).toISOString(),
      statusText[r.status],
      String(r.risk),
      String(r.liveness),
      String(r.faceMatch),
      r.lat == null ? "" : r.lat.toFixed(6),
      r.lng == null ? "" : r.lng.toFixed(6),
    ]
      .map(esc)
      .join(","),
  );
  return "\uFEFF" + [header.map(esc).join(","), ...lines].join("\n");
}
export function downloadCsv(name: string, contents: string) {
  const url = URL.createObjectURL(new Blob([contents], { type: "text/csv;charset=utf-8" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = `${name}-${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}
