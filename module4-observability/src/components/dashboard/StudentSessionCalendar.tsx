import { useMemo, useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import type { CheckInRow } from "./AttendanceTable";
import {
  fetchMySessions,
  toSessionRow,
  type ApiSession,
  type EnrollmentRow,
  type SessionRow,
} from "@/lib/attendance";
import { formatSingaporeDateTime, parseApiDateTime } from "@/lib/time";
import { DAY, SLOT, layoutDay, mondayOf } from "@/lib/session-calendar";

const GRID_START_HOUR = 8;
const GRID_END_HOUR = 21;
const SLOT_HEIGHT = 56;
const GRID_START = GRID_START_HOUR * 60 * 60 * 1000;
const GRID_END = GRID_END_HOUR * 60 * 60 * 1000;

type Verification = CheckInRow["status"];
type CalendarState = "upcoming" | "active" | "attended" | "missed" | "awaiting" | "cancelled" | "unknown";

type CalendarItem = {
  session: SessionRow;
  verification?: Verification | undefined;
  state: CalendarState;
  label: string;
};

const stateLabel: Record<CalendarState, string> = {
  upcoming: "Upcoming",
  active: "Active",
  attended: "Attended",
  missed: "Missed",
  awaiting: "Awaiting review",
  cancelled: "Cancelled",
  unknown: "Attendance unavailable",
};

const stateTone: Record<CalendarState, string> = {
  upcoming: "border-violet-300 bg-violet-400/20 text-violet-100",
  active: "border-sky-300 bg-sky-400/20 text-sky-100",
  attended: "border-emerald-300 bg-emerald-400/20 text-emerald-100",
  missed: "border-rose-300 bg-rose-400/20 text-rose-100",
  awaiting: "border-amber-300 bg-amber-400/20 text-amber-100",
  cancelled: "border-slate-400 bg-slate-400/15 text-slate-200",
  unknown: "border-amber-300/70 bg-amber-400/10 text-amber-100",
};

const control = "rounded-lg border border-border bg-secondary/40 px-3 py-2 text-xs text-foreground transition hover:bg-secondary focus-visible:ring-2 focus-visible:ring-primary disabled:opacity-50";

function dateKey(value: number) {
  return formatSingaporeDateTime(new Date(value).toISOString(), {
    year: "numeric", month: "2-digit", day: "2-digit",
  });
}

function clock(value: string) {
  return formatSingaporeDateTime(value, { hour: "numeric", minute: "2-digit", hour12: true });
}

function rangeLabel(week: number) {
  const start = formatSingaporeDateTime(new Date(week).toISOString(), { day: "numeric", month: "short" });
  const end = formatSingaporeDateTime(new Date(week + 4 * DAY).toISOString(), { day: "numeric", month: "short", year: "numeric" });
  return `${start} – ${end}`;
}

function attendanceState(session: SessionRow, verification: Verification | undefined, known: boolean): CalendarItem {
  if (session.status === "cancelled") return { session, verification, state: "cancelled", label: stateLabel.cancelled };
  if (session.status === "scheduled") return { session, verification, state: "upcoming", label: stateLabel.upcoming };
  if (session.status === "active") {
    return {
      session,
      verification,
      state: "active",
      label: verification ? `Active · ${verification}` : stateLabel.active,
    };
  }
  if (!known) return { session, verification, state: "unknown", label: stateLabel.unknown };
  if (verification === "approved") return { session, verification, state: "attended", label: stateLabel.attended };
  if (verification === "pending" || verification === "flagged" || verification === "appealed") {
    return { session, verification, state: "awaiting", label: stateLabel.awaiting };
  }
  if (verification === "rejected") {
    return { session, verification, state: "missed", label: "Missed · Rejected" };
  }
  return { session, state: "missed", label: stateLabel.missed };
}

function formatSessionVenue(session: SessionRow) {
  return session.room === "Not set" ? "Venue not specified" : session.room;
}

function formatSessionCourse(session: SessionRow) {
  if (!session.courses) return "Course not specified";
  return `${session.courses.code} · ${session.courses.name}`;
}

export function StudentSessionCalendar({
  userId,
  rows,
  checkInsLoading,
  checkInsError,
  onRetryCheckIns,
  enrolledCourses,
  enrollmentsLoading,
  enrollmentsError,
  onRetryEnrollments,
  week,
  onWeekChange,
  courseId,
  onCourseChange,
}: {
  userId: string;
  rows: CheckInRow[];
  checkInsLoading: boolean;
  checkInsError: boolean;
  onRetryCheckIns: () => void;
  enrolledCourses: EnrollmentRow[];
  enrollmentsLoading: boolean;
  enrollmentsError: boolean;
  onRetryEnrollments: () => void;
  week: number;
  onWeekChange: (week: number) => void;
  courseId: string;
  onCourseChange: (courseId: string) => void;
}) {
  const [selected, setSelected] = useState<CalendarItem | null>(null);
  const days = useMemo(() => Array.from({ length: 5 }, (_, index) => week + index * DAY), [week]);
  const query = useQuery({
    queryKey: ["student-session-calendar", userId, week],
    queryFn: ({ signal }) => fetchMySessions({
      startDate: new Date(week).toISOString(),
      endDate: new Date(week + 5 * DAY).toISOString(),
      signal,
    }),
    placeholderData: keepPreviousData,
    staleTime: 15_000,
    refetchInterval: 30_000,
  });

  const latestCheckIns = useMemo(() => {
    const result = new Map<string, CheckInRow>();
    for (const row of rows) {
      const previous = result.get(row.sessionId);
      if (!previous || parseApiDateTime(row.time).getTime() > parseApiDateTime(previous.time).getTime()
        || (row.time === previous.time && row.id > previous.id)) {
        result.set(row.sessionId, row);
      }
    }
    return result;
  }, [rows]);

  const sessions = useMemo(() => {
    const known = !checkInsLoading && !checkInsError;
    return (query.data ?? [])
      .filter((item: ApiSession) => courseId === "all" || item.course_id === courseId)
      .map((item: ApiSession) => {
      const session = toSessionRow(item);
      const verification = latestCheckIns.get(session.id)?.status;
      return attendanceState(session, verification, known);
      });
  }, [checkInsError, checkInsLoading, courseId, latestCheckIns, query.data]);

  const courseOptions = useMemo(() => {
    const options = new Map(enrolledCourses.map((course) => [course.course_id, course]));
    for (const item of query.data ?? []) {
      if (!options.has(item.course_id)) {
        options.set(item.course_id, {
          course_id: item.course_id,
          course_code: item.course_code ?? item.course_id,
          course_name: item.course_name ?? item.course_code ?? "Course",
        });
      }
    }
    return [...options.values()].sort((a, b) => a.course_code.localeCompare(b.course_code));
  }, [enrolledCourses, query.data]);

  const segments = useMemo(() => days.map((day) => layoutDay(sessions.map((item) => item.session), day)), [days, sessions]);
  const itemBySession = useMemo(() => new Map(sessions.map((item) => [item.session.id, item])), [sessions]);
  const today = dateKey(Date.now());
  const gridHeight = 26 * SLOT_HEIGHT;

  function blockButton(block: ReturnType<typeof layoutDay>[number], day: number) {
    const item = itemBySession.get(block.session.id)!;
    const sessionStart = parseApiDateTime(block.session.starts_at).getTime();
    const sessionEnd = parseApiDateTime(block.session.ends_at).getTime();
    const visibleStart = Math.max(block.start, day + GRID_START);
    const visibleEnd = Math.min(block.end, day + GRID_END);
    if (!Number.isFinite(sessionStart) || !Number.isFinite(sessionEnd) || visibleEnd <= visibleStart) return null;
    const duration = Math.max(1, Math.round((sessionEnd - sessionStart) / 60000));
    return (
      <button
        key={`${block.session.id}-${day}`}
        type="button"
        className={`absolute z-10 overflow-hidden rounded-md border-l-[3px] p-2 text-left text-[11px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary ${stateTone[item.state]}`}
        style={{
          top: ((visibleStart - day - GRID_START) / SLOT) * SLOT_HEIGHT,
          height: Math.max(SLOT_HEIGHT / 2, ((visibleEnd - visibleStart) / SLOT) * SLOT_HEIGHT),
          left: `calc(${(block.lane / block.lanes) * 100}% + 3px)`,
          width: `calc(${100 / block.lanes}% - 6px)`,
        }}
        onClick={() => setSelected(item)}
        aria-label={`${block.session.name}, ${formatSessionCourse(block.session)}, ${clock(block.session.starts_at)} to ${clock(block.session.ends_at)}, ${formatSessionVenue(block.session)}, ${item.label}`}
        title={`${block.session.name} · ${duration} minutes · ${item.label}`}
      >
        <span className="block truncate font-semibold">{block.session.name}</span>
        <span className="block truncate">{formatSessionCourse(block.session)}</span>
        <span className="block truncate">{formatSessionVenue(block.session)}</span>
      </button>
    );
  }

  return (
    <section className="lg:col-span-12 rounded-2xl border border-primary/40 bg-primary/5 p-4 shadow-[var(--shadow-glass)] sm:p-5" aria-labelledby="student-sessions-heading">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 id="student-sessions-heading" className="font-display text-lg font-semibold">My attendance</h1>
        </div>
        <label className="text-xs text-muted-foreground">
          <span className="sr-only">Course</span>
          <select aria-label="Course" value={courseId} onChange={(event) => onCourseChange(event.target.value)} className="rounded-lg border border-border bg-background px-3 py-2 text-foreground">
            <option value="all">All courses</option>
            {courseOptions.map((course) => <option key={course.course_id} value={course.course_id}>{course.course_code} · {course.course_name}</option>)}
          </select>
        </label>
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex gap-1.5">
          <Button variant="outline" size="sm" aria-label="Previous week" onClick={() => onWeekChange(week - 7 * DAY)}>←</Button>
          <Button variant="outline" size="sm" onClick={() => onWeekChange(mondayOf(Date.now()))}>Today</Button>
          <Button variant="outline" size="sm" aria-label="Next week" onClick={() => onWeekChange(week + 7 * DAY)}>→</Button>
        </div>
        <p className="text-sm font-semibold" aria-live="polite">{rangeLabel(week)}</p>
      </div>

      <div className="mt-4 flex flex-wrap gap-x-4 gap-y-2 text-xs text-muted-foreground" aria-label="Calendar legend">
        {(["upcoming", "active", "attended", "missed", "awaiting"] as CalendarState[]).map((state) => <span key={state} className="inline-flex items-center gap-1.5"><span className={`size-2 rounded-full ${state === "upcoming" ? "bg-violet-300" : state === "active" ? "bg-sky-300" : state === "attended" ? "bg-emerald-300" : state === "missed" ? "bg-rose-300" : "bg-amber-300"}`} aria-hidden="true" />{stateLabel[state]}</span>)}
      </div>

      {query.isPending && <p role="status" className="mt-4 text-sm text-muted-foreground">Loading sessions…</p>}
      {query.isError && <p role="alert" className="mt-4 text-sm text-destructive">Could not load your sessions. <button type="button" className="underline" onClick={() => void query.refetch()}>Retry</button></p>}
      {checkInsError && <p role="alert" className="mt-2 text-sm text-warning">Attendance outcomes could not be loaded. <button type="button" className="underline" onClick={onRetryCheckIns}>Retry</button></p>}
      {!query.isPending && !query.isError && !sessions.length && <p role="status" className="mt-4 text-sm text-muted-foreground">No sessions in this week.</p>}
      {enrollmentsLoading && <p role="status" className="mt-2 text-sm text-muted-foreground">Loading your authorised courses…</p>}
      {enrollmentsError && <p role="alert" className="mt-2 text-sm text-warning">Authorised courses could not be loaded. <button type="button" className="underline" onClick={onRetryEnrollments}>Retry</button></p>}
      {!enrollmentsLoading && !enrollmentsError && !enrolledCourses.length && !query.data?.length && !query.isPending && !query.isError && <p role="status" className="mt-4 text-sm text-muted-foreground">No enrolled courses.</p>}

      <div className="mt-4 max-h-[70vh] overflow-auto rounded-xl border border-border">
        <div className="min-w-[980px]">
          <div className="grid bg-card" style={{ gridTemplateColumns: "58px repeat(5, minmax(140px, 1fr))" }}>
            <div className="border-b border-border px-2 py-3 text-[10px] text-muted-foreground">SGT</div>
            {days.map((day) => <div key={day} className={`border-b border-l border-border px-2 py-3 text-center text-xs font-medium ${dateKey(day) === today ? "bg-primary/20" : ""}`}><span className="block uppercase text-muted-foreground">{formatSingaporeDateTime(new Date(day).toISOString(), { weekday: "short" })}</span><span className="mt-1 block text-sm">{formatSingaporeDateTime(new Date(day).toISOString(), { day: "numeric" })}</span></div>)}
          </div>
          <div className="grid" style={{ gridTemplateColumns: "58px repeat(5, minmax(140px, 1fr))" }}>
            <div>{Array.from({ length: 26 }, (_, index) => <div key={index} className="pr-1 text-right text-[10px] text-muted-foreground" style={{ height: SLOT_HEIGHT }}>{formatSingaporeDateTime(new Date(week + GRID_START + index * SLOT).toISOString(), { hour: "2-digit", minute: "2-digit", hour12: false })}</div>)}</div>
            {days.map((day, index) => <div key={day} className={`relative border-l border-border ${dateKey(day) === today ? "bg-primary/[0.04]" : ""}`} style={{ height: gridHeight }}>
              {Array.from({ length: 26 }, (_, slot) => <div key={slot} className="border-t border-border/50" style={{ height: SLOT_HEIGHT }} aria-hidden="true" />)}
              {segments[index]!.map((block) => blockButton(block, day))}
            </div>)}
          </div>
        </div>
      </div>

      {selected && <div role="dialog" aria-modal="true" aria-labelledby="student-session-detail-title" className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4" onClick={() => setSelected(null)}>
        <div className="w-full max-w-md rounded-2xl border border-border bg-card p-5 shadow-xl" onClick={(event) => event.stopPropagation()}>
          <div className="flex items-start justify-between gap-3">
            <div><h2 id="student-session-detail-title" className="font-display text-lg font-semibold">{selected.session.name}</h2><p className="mt-1 text-xs text-muted-foreground">{selected.session.courses?.code ?? "Course"}</p></div>
            <button type="button" aria-label="Close session details" className="rounded-md px-2 py-1 text-muted-foreground hover:text-foreground focus-visible:ring-2 focus-visible:ring-primary" onClick={() => setSelected(null)}>×</button>
          </div>
          <dl className="mt-5 grid grid-cols-1 gap-4 text-sm sm:grid-cols-2">
            <div><dt className="text-xs text-muted-foreground">Time</dt><dd className="mt-1">{clock(selected.session.starts_at)}–{clock(selected.session.ends_at)} SGT</dd></div>
            <div><dt className="text-xs text-muted-foreground">Venue</dt><dd className="mt-1">{formatSessionVenue(selected.session)}</dd></div>
            <div><dt className="text-xs text-muted-foreground">Session state</dt><dd className="mt-1">{selected.label}</dd></div>
            <div><dt className="text-xs text-muted-foreground">Verification</dt><dd className="mt-1">{selected.verification ?? "No check-in"}</dd></div>
          </dl>
          {selected.verification === "appealed" && <p className="mt-5 rounded-lg border border-amber-300/30 bg-amber-400/10 p-3 text-sm text-amber-100">Appeal awaiting review.</p>}
          {selected.state === "upcoming" && <p className="mt-5 rounded-lg border border-violet-300/30 bg-violet-400/10 p-3 text-sm text-violet-100">Check-in has not opened.</p>}
          {selected.verification === "rejected" && <p className="mt-5 rounded-lg border border-rose-300/30 bg-rose-400/10 p-3 text-sm text-rose-100">Rejected — attendance was not credited.</p>}
          <div className="mt-5 flex justify-end"><Button variant="outline" onClick={() => setSelected(null)}>Close</Button></div>
        </div>
      </div>}
    </section>
  );
}
