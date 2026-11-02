import { api } from "./api";
import { parseApiDateTime } from "./time";

export type CourseParticipation = {
  course_id: string;
  course_code: string;
  course_name: string;
  total_sessions: number;
  recorded_checkins: number;
  expected_attendances: number | null;
  active_sessions: number;
  historical_enrollment_limited: boolean;
  rate: number | null;
};
export type DailyCheckIns = { date: string; count: number | null; partial: boolean };
export function addDays(value: string, amount: number) {
  const date = new Date(`${value}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + amount);
  return date.toISOString().slice(0, 10);
}
export function localDate(now: Date, timezone: string) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(now);
  const part = (type: string) => parts.find((item) => item.type === type)!.value;
  return `${part("year")}-${part("month")}-${part("day")}`;
}
export function weekStart(value: string) {
  const weekday = new Date(`${value}T00:00:00Z`).getUTCDay();
  return addDays(value, -((weekday + 6) % 7));
}
export function midnightUtc(value: string, timezone: string) {
  const target = Date.parse(`${value}T00:00:00Z`);
  let result = target;
  const formatter = new Intl.DateTimeFormat("en-CA", {
    timeZone: timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
  });
  for (let i = 0; i < 4; i++) {
    const parts = formatter.formatToParts(new Date(result));
    const part = (type: string) => parts.find((item) => item.type === type)!.value;
    const wall = Date.parse(
      `${part("year")}-${part("month")}-${part("day")}T${part("hour")}:${part("minute")}:${part("second")}Z`,
    );
    const delta = target - wall;
    result += delta;
    if (!delta) break;
  }
  return new Date(result).toISOString();
}
export function dailyCheckIns(
  rows: Array<{ id: string; checked_in_at: string }>,
  start: string,
  timezone: string,
  now = new Date(),
): DailyCheckIns[] {
  const today = localDate(now, timezone);
  const counts = new Map<string, number>();
  const ids = new Set<string>();
  rows.forEach((row) => {
    if (ids.has(row.id)) return;
    ids.add(row.id);
    const date = localDate(parseApiDateTime(row.checked_in_at), timezone);
    counts.set(date, (counts.get(date) ?? 0) + 1);
  });
  return Array.from({ length: 7 }, (_, index) => {
    const date = addDays(start, index);
    return { date, count: date > today ? null : (counts.get(date) ?? 0), partial: date === today };
  });
}
export async function fetchAdminChartData(start: string, timezone: string, signal: AbortSignal) {
  const params = new URLSearchParams({
    include_course_participation: "true",
    start_date: start,
    end_date: addDays(start, 7),
  });
  const data = await api.request<{
    timezone: string;
    chart_days: DailyCheckIns[];
    chart_courses: Omit<CourseParticipation, "rate">[];
  }>(`/stats/overview?${params}`, { signal });
  if (
    data.timezone !== timezone ||
    !Array.isArray(data.chart_days) ||
    data.chart_days.length !== 7 ||
    !Array.isArray(data.chart_courses)
  )
    throw new Error("Incomplete weekly analytics response");
  if (
    !data.chart_days.every(
      (day, i) =>
        day.date === addDays(start, i) &&
        (day.count === null || (Number.isInteger(day.count) && day.count >= 0)) &&
        typeof day.partial === "boolean",
    )
  )
    throw new Error("Incomplete daily statistics");
  const courses = data.chart_courses.map((stats) => {
    if (
      typeof stats.course_id !== "string" ||
      typeof stats.course_code !== "string" ||
      typeof stats.course_name !== "string" ||
      ![
        stats.recorded_checkins,
        stats.total_sessions,
        stats.active_sessions,
      ].every((value) => Number.isInteger(value) && value >= 0) ||
      (stats.expected_attendances !== null &&
        (!Number.isInteger(stats.expected_attendances) || stats.expected_attendances < 0))
    )
      throw new Error("Incomplete course statistics");
    return {
      ...stats,
      rate:
        stats.total_sessions && stats.expected_attendances
          ? stats.recorded_checkins / stats.expected_attendances
          : null,
    };
  });
  return { days: data.chart_days, courses };
}
