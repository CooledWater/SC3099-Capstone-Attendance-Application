import { api } from "./api";
import { parseApiDateTime } from "./time";
import type { RosterSession, Verification } from "./checkin-roster";

export type SessionStats = {
  session_id: string;
  course_id: string;
  course_code: string;
  session_name: string;
  status: string;
  scheduled_start: string;
  scheduled_end: string;
  actual_end: string | null;
  checkin_opens_at: string;
  checkin_closes_at: string;
  server_time: string;
  timezone: string;
  submitted_count: number;
  expected_count: number;
  scored_count: number;
  average_risk_score: number;
  by_status: Record<Verification, number>;
  timeline_bucket_minutes: number;
  pre_opening_count: number;
  checkin_timeline: Array<{ minute: number; count: number }>;
  today: { date: string; total: number; breakdown: Record<string, number> };
  recent_review_activity: Array<{
    id: string;
    session_id: string;
    session_name: string;
    action: string;
    decision: string;
    previous_status: string | null;
    timestamp: string;
    student_name?: string | null;
  }>;
};

export async function fetchTaCourseSessions(courseId: string, signal: AbortSignal) {
  const rows: RosterSession[] = [];
  while (true) {
    const page = await api.request<{ items: RosterSession[]; total: number }>(
      `/sessions/?course_id=${encodeURIComponent(courseId)}&limit=100&offset=${rows.length}`,
      { signal },
    );
    rows.push(...page.items);
    if (!page.items.length || rows.length >= page.total) {
      return rows.filter((row) => row.course_id === courseId);
    }
  }
}

export function defaultTaSession(sessions: RosterSession[]) {
  const newest = (rows: RosterSession[]) =>
    [...rows].sort(
      (a, b) =>
        parseApiDateTime(b.scheduled_start).getTime() -
        parseApiDateTime(a.scheduled_start).getTime(),
    )[0];
  return (
    newest(sessions.filter((row) => row.status === "active")) ??
    newest(sessions.filter((row) => row.status === "closed")) ??
    [...sessions.filter((row) => row.status === "scheduled")].sort(
      (a, b) =>
        parseApiDateTime(a.scheduled_start).getTime() -
        parseApiDateTime(b.scheduled_start).getTime(),
    )[0] ??
    newest(sessions)
  );
}

export type TimelineBucket = {
  start: number;
  end: number;
  count: number | null;
  current: boolean;
  outsideWindow: boolean;
  preOpening: number;
};

export function sessionTimeline(stats: SessionStats): TimelineBucket[] {
  const start = parseApiDateTime(stats.checkin_opens_at).getTime();
  const now = parseApiDateTime(stats.server_time).getTime();
  const end = Math.min(
    parseApiDateTime(stats.checkin_closes_at).getTime(),
    parseApiDateTime(stats.scheduled_end).getTime(),
    stats.actual_end ? parseApiDateTime(stats.actual_end).getTime() : Infinity,
  );
  const step = stats.timeline_bucket_minutes * 60_000;
  if (![start, now, end, step].every(Number.isFinite) || step <= 0) return [];
  const recorded = new Map(stats.checkin_timeline.map((item) => [item.minute, item.count]));
  const last = Math.max(
    0,
    Math.ceil((end - start) / step) - 1,
    ...stats.checkin_timeline.map((item) =>
      Math.floor(item.minute / stats.timeline_bucket_minutes),
    ),
  );
  return Array.from({ length: last + 1 }, (_, index) => {
    const bucketStart = start + index * step;
    const count = recorded.get(index * stats.timeline_bucket_minutes);
    return {
      start: bucketStart,
      end: bucketStart + step,
      count: count ?? (bucketStart < now && bucketStart < end ? 0 : null),
      current:
        stats.status === "active" && bucketStart <= now && now < bucketStart + step && now < end,
      outsideWindow: bucketStart >= end,
      preOpening: index === 0 ? stats.pre_opening_count : 0,
    };
  });
}

export const verificationColors = {
  approved: "#63d7a4",
  pending: "#ac8be9",
  flagged: "#ef6b88",
  appealed: "#e8b862",
  rejected: "#95949f",
};

export function sessionClock(value: number | string, timezone: string) {
  return new Intl.DateTimeFormat("en-SG", {
    timeZone: timezone,
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).format(typeof value === "number" ? new Date(value) : parseApiDateTime(value));
}
