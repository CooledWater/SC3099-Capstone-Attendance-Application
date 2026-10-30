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
  appealed_at?: string | null;
  reviewed_at?: string | null;
  liveness_score?: number | null;
  face_match_score?: number | null;
  latitude?: number | null;
  longitude?: number | null;
  session_id: string;
  session_name?: string | null;
  course_code?: string | null;
  course_id?: string | null;
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
  saved_expected_attendance?: number | null;
  is_active: boolean;
  geofence_lat: number | null;
  geofence_lng: number | null;
  geofence_radius_m: number;
  courses: { code: string; name: string } | null;
};
export type CourseRow = {
  semester_start_date?: string | null;
  id: string;
  code: string;
  name: string;
  instructor_id?: string | null;
};
export type AdminOverview = {
  active_sessions: number;
  total_checkins_today: number;
  flagged_count: number;
  appealed_count: number;
  high_risk_checkins_today: number;
  high_risk_threshold: number;
  approval_rate: number;
  timezone: string;
};
export type EnrollmentRow = {
  course_id: string;
  course_code: string;
  course_name: string;
  semester?: string;
  instructor_name?: string | null;
  enrolled_at?: string;
};
export type ApiSession = {
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
  saved_expected_attendance?: number | null;
  status: SessionRow["status"];
  venue_latitude?: number | null;
  venue_longitude?: number | null;
  geofence_radius_meters?: number | null;
};

export type CheckInDetail = RawCheckIn & {
  device_id?: string | null;
  verified_at?: string | null;
  location_accuracy_meters?: number | null;
  distance_from_venue_meters?: number | null;
  liveness_passed?: boolean | null;
  liveness_challenge_type?: string | null;
  face_match_passed?: boolean | null;
  qr_code_verified?: boolean | null;
  reviewed_by_id?: string | null;
  review_notes?: string | null;
  appeal_reason?: string | null;
};

export async function fetchSessions() {
  const items: ApiSession[] = [];
  while (true) {
    const result = await api.request<{ items: ApiSession[]; total?: number }>(
      `/sessions/?limit=100${items.length ? `&offset=${items.length}` : ""}`,
    );
    items.push(...result.items);
    if (!result.items.length || result.total == null || items.length >= result.total) break;
  }
  return items.map(toSessionRow);
}

export async function fetchMySessions(
  options: {
    startDate?: string;
    endDate?: string;
    courseId?: string;
    signal?: AbortSignal;
  } = {},
) {
  const result: ApiSession[] = [];
  const limit = 100;
  let offset = 0;
  while (true) {
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    if (options.startDate) params.set("start_date", options.startDate);
    if (options.endDate) params.set("end_date", options.endDate);
    if (options.courseId && options.courseId !== "all") params.set("course_id", options.courseId);
    const page = await api.request<ApiSession[]>(`/sessions/my-sessions?${params}`, {
      signal: options.signal ?? null,
    });
    result.push(...page);
    offset += page.length;
    if (page.length < limit) return result;
  }
}

export function fetchCheckInDetail(checkInId: string, signal?: AbortSignal) {
  return api.request<CheckInDetail>(`/checkins/${encodeURIComponent(checkInId)}`, {
    signal: signal ?? null,
  });
}

export function toSessionRow(s: ApiSession): SessionRow {
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
    saved_expected_attendance: s.saved_expected_attendance ?? null,
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
  const groups: RawCheckIn[][] = [];
  let next = 0;
  // Leave database capacity available for interactive actions such as creating sessions.
  await Promise.all(
    Array.from({ length: Math.min(2, sessions.length) }, async () => {
      while (next < sessions.length) {
        const session = sessions[next++]!;
        const items = await api.request<RawCheckIn[]>(`/checkins/session/${session.id}`);
        groups.push(
          items
            .filter((item) => item.session_id === session.id)
            .map((item) => ({
              ...item,
              session_name: session.courses?.name ?? null,
              course_code: session.courses?.code ?? null,
            })),
        );
      }
    }),
  );
  return groups.flat().sort((a, b) => Date.parse(b.checked_in_at) - Date.parse(a.checked_in_at));
}
export async function fetchCheckIns() {
  const sessions = new Map((await fetchSessions()).map((session) => [session.id, session]));
  const items: RawCheckIn[] = [];
  let offset = 0;
  while (true) {
    const page = await api.request<{ items: RawCheckIn[]; total: number }>(
      `/checkins/?limit=50&offset=${offset}`,
    );
    items.push(...page.items);
    offset += page.items.length;
    if (!page.items.length || offset >= page.total) break;
  }
  return items
    .filter((item) => sessions.has(item.session_id))
    .map((item) => {
      const session = sessions.get(item.session_id)!;
      return {
        ...item,
        session_name: session.courses?.name ?? null,
        course_code: session.courses?.code ?? null,
      };
    })
    .sort((a, b) => Date.parse(b.checked_in_at) - Date.parse(a.checked_in_at));
}
export const HISTORY_PAGE_SIZE = 50;
export function fetchMyCheckInsPage(
  sessionId = "all",
  offset = 0,
  courseId = "all",
  signal?: AbortSignal,
  sessionName = "",
  statuses: string[] = [],
) {
  const params = new URLSearchParams({ limit: String(HISTORY_PAGE_SIZE), offset: String(offset) });
  if (sessionId !== "all") params.set("session_id", sessionId);
  if (courseId !== "all") params.set("course_id", courseId);
  if (sessionName.trim()) params.set("session_name", sessionName.trim());
  if (statuses.length) params.set("status", statuses.join(","));
  return api.request<RawCheckIn[]>(`/checkins/my-checkins?${params}`, { signal: signal ?? null });
}
export async function fetchMyCheckIns() {
  const rows: RawCheckIn[] = [];
  while (true) {
    const page = await fetchMyCheckInsPage("all", rows.length);
    rows.push(...page);
    if (page.length < HISTORY_PAGE_SIZE) return rows;
  }
}
export async function fetchCourses() {
  const items: CourseRow[] = [];
  let total = Infinity;
  while (items.length < total) {
    const page = await api.request<{ items: CourseRow[]; total: number }>(
      `/courses/?limit=100&offset=${items.length}`,
    );
    items.push(...page.items);
    total = page.total;
    if (!page.items.length) break;
  }
  return items;
}
export const fetchAdminOverview = (days = 30, signal?: AbortSignal) =>
  api.request<AdminOverview>(`/stats/overview?days=${days}`, { signal: signal ?? null });
export const fetchMyEnrollments = () => api.request<EnrollmentRow[]>("/enrollments/my-enrollments");
export async function fetchMyAssignedCourses(options: { signal?: AbortSignal } = {}) {
  const items: CourseRow[] = [];
  while (true) {
    const page = await api.request<{ items: CourseRow[]; total: number }>(
      `/courses/my-courses?limit=100&offset=${items.length}`,
      { signal: options.signal ?? null },
    );
    items.push(...page.items);
    if (!page.items.length || items.length >= page.total) return items;
  }
}

export function toRows(list: RawCheckIn[]): CheckInRow[] {
  return list.map((c) => ({
    id: c.id,
    student: c.student_name ?? "You",
    email: c.student_email ?? c.student_id ?? "—",
    course: c.course_code ?? "—",
    courseId: c.course_id ?? "",
    sessionId: c.session_id,
    sessionName: c.session_name ?? "Unnamed session",
    room: "—",
    time: c.checked_in_at,
    status: c.status,
    appealedAt: c.appealed_at ?? null,
    reviewedAt: c.reviewed_at ?? null,
    risk: c.risk_score ?? 0,
    riskScore: c.risk_score ?? 0,
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
      r.risk.toFixed(2),
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
