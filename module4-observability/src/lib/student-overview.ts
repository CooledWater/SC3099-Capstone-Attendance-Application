import { api } from "./api";

export type StudentCourse = { id: string; code: string; name: string; semester: string };
export type TodaySession = { id: string; course_id: string; course_code: string; name: string; venue_name: string | null; scheduled_start: string; scheduled_end: string; status: string };
export type StudentOverview = {
  as_of: string;
  courses?: StudentCourse[];
  period?: { start: string | null; end: string; error: string | null };
  attendance?: { course_id: string | null; approved: number; eligible: number; percentage: number | null; unresolved: number };
  today?: { date: string; start: string; end: string; total: number; active: number; upcoming: number; completed: number; sessions: TodaySession[] };
  flagged?: { total: number; flagged: number; appealed: number };
};
export function fetchStudentOverview(section: "attendance" | "today" | "flagged", courseId: string, signal?: AbortSignal) {
  const params = new URLSearchParams({ section });
  if (section === "attendance" && courseId) params.set("course_id", courseId);
  return api.request<StudentOverview>(`/stats/my-overview?${params}`, { signal: signal ?? null });
}
