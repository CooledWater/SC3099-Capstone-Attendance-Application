import { api } from "@/lib/api";
import type { CheckInRow } from "@/components/dashboard/AttendanceTable";

export type RawCheckIn = {
  id: string;
  student_name?: string;
  student_email?: string;
  student_id?: string;
  checked_in_at: string;
  status: "approved" | "flagged" | "rejected" | "pending";
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
  starts_at: string;
  room: string;
  expected_attendance: number;
  is_active: boolean;
  geofence_lat: number | null;
  geofence_lng: number | null;
  geofence_radius_m: number;
  courses: { code: string; name: string } | null;
};
type ApiSession = {
  id: string;
  course_id: string;
  course_code?: string | null;
  course_name?: string | null;
  scheduled_start: string;
  venue_name?: string | null;
  total_enrolled?: number;
  status: string;
  venue_latitude?: number | null;
  venue_longitude?: number | null;
  geofence_radius_meters?: number | null;
};

export async function fetchSessions() {
  const result = await api.request<{ items: ApiSession[] }>("/sessions/?limit=100");
  return result.items.map((s): SessionRow => ({
    id: s.id,
    course_id: s.course_id,
    starts_at: s.scheduled_start,
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
  }));
}

export async function fetchCheckIns() {
  const sessions = await fetchSessions();
  const groups = await Promise.all(
    sessions.map(async (session) => {
      const items = await api.request<RawCheckIn[]>(`/checkins/session/${session.id}`);
      return items.map((item) => ({
        ...item,
        session_id: session.id,
        session_name: session.courses?.name ?? null,
        course_code: session.courses?.code ?? null,
      }));
    }),
  );
  return groups.flat().sort((a, b) => Date.parse(b.checked_in_at) - Date.parse(a.checked_in_at));
}
export const fetchMyCheckIns = () => api.request<RawCheckIn[]>("/checkins/my-checkins?limit=100");
export async function fetchCourses() {
  return (
    await api.request<{ items: { id: string; code: string; name: string }[] }>(
      "/courses/?limit=100",
    )
  ).items;
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
    status: c.status === "approved" ? "approved" : c.status === "flagged" ? "flagged" : "no_show",
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
    const d = new Date(r.time);
    const key = `${String(d.getHours()).padStart(2, "0")}:00`;
    buckets.set(key, (buckets.get(key) ?? 0) + 1);
  });
  return [...buckets.entries()].sort((a, b) => a[0].localeCompare(b[0]));
}
export const statusText: Record<CheckInRow["status"], string> = {
  approved: "Approved",
  flagged: "Flagged",
  no_show: "Not approved",
};
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
      new Date(r.time).toISOString(),
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
