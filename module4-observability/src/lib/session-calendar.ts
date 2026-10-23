import { api } from "./api";
import { parseApiDateTime, toSingaporeDateTimeLocal } from "./time";
import { toSessionRow, type ApiSession, type SessionRow } from "./attendance";

export const DAY = 86400000;
export const SLOT = 30 * 60000;
export function mondayOf(value: number): number {
  const date = toSingaporeDateTimeLocal(new Date(value).toISOString()).slice(0, 10);
  const midnight = Date.parse(`${date}T00:00:00+08:00`);
  const weekday = new Date(midnight + 8 * 3600000).getUTCDay();
  return midnight - ((weekday + 6) % 7) * DAY;
}

export async function loadCalendarSessions(course: string, start: number, signal: AbortSignal) {
  const result: SessionRow[] = [];
  for (const status of ["scheduled", "active"]) {
    let offset = 0;
    while (true) {
      // No lower start-date bound: sessions beginning before this week can
      // overlap it. Fetch all matching pages up to the visible week's end.
      const params = new URLSearchParams({
        status,
        end_date: new Date(start + 5 * DAY).toISOString(),
        limit: "100",
        offset: String(offset),
      });
      if (course !== "all") params.set("course_id", course);
      const page = await api.request<{ items: ApiSession[]; total: number }>(
        `/sessions/?${params}`,
        { signal },
      );
      result.push(...page.items.map(toSessionRow));
      offset += page.items.length;
      if (!page.items.length || offset >= page.total) break;
    }
  }
  return result.filter(
    (row) =>
      (course === "all" || row.course_id === course) &&
      (row.status === "scheduled" || row.status === "active") &&
      parseApiDateTime(row.starts_at).getTime() < start + 5 * DAY &&
      parseApiDateTime(row.ends_at).getTime() > start,
  );
}

export function movePayload(session: SessionRow, nextStart: number) {
  if (session.status !== "scheduled")
    throw new Error("Only Scheduled sessions can be moved. Refresh the calendar.");
  if (nextStart <= Date.now()) throw new Error("Choose a future date and time.");
  const delta = nextStart - parseApiDateTime(session.starts_at).getTime();
  const shift = (value: string) =>
    new Date(parseApiDateTime(value).getTime() + delta).toISOString();
  return {
    scheduled_start: new Date(nextStart).toISOString(),
    scheduled_end: shift(session.ends_at),
    checkin_opens_at: shift(session.checkin_opens_at),
    checkin_closes_at: shift(session.checkin_closes_at),
  };
}

export type CalendarBlock = {
  session: SessionRow;
  start: number;
  end: number;
  lane: number;
  lanes: number;
};
export function layoutDay(sessions: SessionRow[], day: number): CalendarBlock[] {
  const blocks = sessions
    .map((session) => ({
      session,
      start: Math.max(day, parseApiDateTime(session.starts_at).getTime()),
      end: Math.min(day + DAY, parseApiDateTime(session.ends_at).getTime()),
      lane: 0,
      lanes: 1,
    }))
    .filter((block) => block.end > block.start)
    .sort((a, b) => a.start - b.start || a.end - b.end || a.session.id.localeCompare(b.session.id));
  let cluster: CalendarBlock[] = [],
    until = 0;
  function assign() {
    const ends: number[] = [];
    for (const block of cluster) {
      let lane = ends.findIndex((end) => end <= block.start);
      if (lane < 0) lane = ends.length;
      ends[lane] = block.end;
      block.lane = lane;
    }
    cluster.forEach((block) => {
      block.lanes = ends.length;
    });
    cluster = [];
  }
  for (const block of blocks) {
    if (cluster.length && block.start >= until) assign();
    if (!cluster.length) until = block.end;
    cluster.push(block);
    until = Math.max(until, block.end);
  }
  assign();
  return blocks;
}
