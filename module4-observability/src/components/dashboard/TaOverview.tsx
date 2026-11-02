import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "@/lib/api";
import type { CourseRow } from "@/lib/attendance";
import { formatSingaporeDateTime, parseApiDateTime } from "@/lib/time";
import {
  fetchFlaggedSession,
  fetchSessionAttendance,
  type RosterEntry,
  type RosterSession,
  type Verification,
} from "@/lib/checkin-roster";
import {
  defaultTaSession,
  fetchTaCourseSessions,
  sessionClock,
  sessionTimeline,
  verificationColors,
  type SessionStats,
  type TimelineBucket,
} from "@/lib/ta-overview";
import { AttendanceRoster } from "./AttendanceTable";
import { CheckInDetail } from "./InstructorCheckIns";
import { RecentReviewActivity } from "./RecentReviewActivity";

const control =
  "max-w-full rounded-lg border border-border bg-secondary/40 px-3 py-2 text-sm text-foreground focus-visible:ring-2 focus-visible:ring-primary";
const statuses = Object.keys(verificationColors) as Verification[];
const kpiButton =
  "h-full w-full cursor-pointer text-left transition duration-150 ease-out hover:-translate-y-0.5 hover:shadow-lg active:translate-y-0.5 active:scale-[0.99] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background";

export function TaOverview({
  courses,
  courseId,
  onCourseChange,
  sessionId,
  onSessionChange,
  onOpenSessions,
  onOpenCheckIns,
  userId,
}: {
  courses: CourseRow[];
  courseId: string;
  onCourseChange: (id: string) => void;
  sessionId: string;
  onSessionChange: (id: string) => void;
  onOpenSessions: (sessionId: string) => void;
  onOpenCheckIns: (sessionId: string) => void;
  userId: string;
}) {
  const sessions = useQuery({
    queryKey: ["ta-course-sessions", userId, courseId],
    queryFn: ({ signal }) => fetchTaCourseSessions(courseId, signal),
    enabled: Boolean(courseId),
    refetchInterval: 30000,
  });
  const session =
    sessions.data?.find((row) => row.id === sessionId) ?? defaultTaSession(sessions.data ?? []);
  useEffect(() => {
    if (session && session.id !== sessionId) onSessionChange(session.id);
  }, [session, sessionId, onSessionChange]);
  return (
    <div className="mt-4 min-w-0 space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <label className="grid min-w-0 gap-1 text-xs text-muted-foreground">
          Course
          <select
            aria-label="TA overview course"
            value={courseId}
            onChange={(event) => onCourseChange(event.target.value)}
            className={control}
          >
            {courses.map((course) => (
              <option key={course.id} value={course.id}>
                {course.code} · {course.name}
              </option>
            ))}
          </select>
        </label>
        <label className="grid min-w-0 gap-1 text-xs text-muted-foreground">
          Session
          <select
            aria-label="TA overview session"
            className={control}
            value={session?.id ?? ""}
            disabled={sessions.isPending || sessions.isError || !sessions.data?.length}
            onChange={(event) => onSessionChange(event.target.value)}
          >
            {!session && (
              <option value="">{sessions.isPending ? "Loading sessions…" : "No sessions"}</option>
            )}
            {sessions.data?.map((row) => (
              <option key={row.id} value={row.id}>
                {row.name} · {row.status} ·{" "}
                {formatSingaporeDateTime(row.scheduled_start, {
                  day: "numeric",
                  month: "short",
                  year: "numeric",
                  hour: "2-digit",
                  minute: "2-digit",
                })}{" "}
                SGT
              </option>
            ))}
          </select>
        </label>
      </div>
      {sessions.isError ? (
        <p
          role="alert"
          className="rounded-xl border border-destructive/40 p-5 text-sm text-destructive"
        >
          Could not load sessions.{" "}
          <button type="button" className="underline" onClick={() => void sessions.refetch()}>
            Retry
          </button>
        </p>
      ) : sessions.isPending ? (
        <OverviewSkeleton />
      ) : !session ? (
        <p className="rounded-xl border border-border p-5 text-sm text-muted-foreground">
          No sessions are available for this assigned course.
        </p>
      ) : (
        <TaSessionOverview
          key={`${userId}:${courseId}:${session.id}`}
          session={session}
          courseId={courseId}
          userId={userId}
          onOpenSessions={onOpenSessions}
          onOpenCheckIns={onOpenCheckIns}
        />
      )}
    </div>
  );
}

function OverviewSkeleton() {
  return (
    <div role="status" aria-label="Loading session overview" className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {[1, 2, 3, 4].map((index) => (
          <div
            key={index}
            className="h-36 animate-pulse rounded-2xl border border-border bg-secondary/30"
          />
        ))}
      </div>
      <div className="h-72 animate-pulse rounded-2xl border border-border bg-secondary/30" />
    </div>
  );
}

export function TaSessionOverview({
  session,
  courseId,
  userId,
  onOpenSessions,
  onOpenCheckIns,
}: {
  session: RosterSession;
  courseId: string;
  userId: string;
  onOpenSessions: (sessionId: string) => void;
  onOpenCheckIns: (sessionId: string) => void;
}) {
  const [verification, setVerification] = useState<string[]>([]);
  const [selected, setSelected] = useState<RosterEntry | null>(null);
  const rosterAnchor = useRef<HTMLDivElement>(null);
  const stats = useQuery({
    queryKey: ["session-stats", userId, courseId, session.id],
    queryFn: ({ signal }) =>
      api.request<SessionStats>(`/stats/sessions/${encodeURIComponent(session.id)}`, { signal }),
    refetchInterval: (query) => (query.state.data?.status === "active" ? 15000 : 60000),
  });
  const roster = useQuery({
    queryKey: ["session-attendance", userId, courseId, session.id],
    queryFn: ({ signal }) => fetchSessionAttendance(session.id, signal),
    refetchInterval: stats.data?.status === "active" ? 15000 : 60000,
  });
  const reviewOnly =
    verification.length > 0 &&
    verification.every((value) => value === "flagged" || value === "appealed");
  const flagged = useQuery({
    queryKey: ["session-flagged", userId, courseId, session.id],
    queryFn: ({ signal }) => fetchFlaggedSession(courseId, session.id, signal),
    enabled: reviewOnly,
    refetchInterval: stats.data?.status === "active" ? 15000 : 60000,
  });
  const data =
    stats.data?.session_id === session.id && stats.data.course_id === courseId
      ? stats.data
      : undefined;
  const attendance =
    roster.data?.session_id === session.id && roster.data.course_id === courseId
      ? roster.data
      : undefined;
  const filter = (values: string[]) => {
    setVerification(values);
    rosterAnchor.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  };
  const rosterError = roster.isError
    ? "Could not load session check-ins."
    : reviewOnly && flagged.isError
      ? "Could not load flagged check-ins."
      : null;
  return (
    <>
      {stats.isError ? (
        <p
          role="alert"
          className="rounded-xl border border-destructive/40 p-5 text-sm text-destructive"
        >
          Could not load session statistics.{" "}
          <button type="button" className="underline" onClick={() => void stats.refetch()}>
            Retry
          </button>
        </p>
      ) : !data ? (
        <OverviewSkeleton />
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <button
              type="button"
              onClick={() => onOpenSessions(session.id)}
              className={`${kpiButton} rounded-2xl border border-blue-400/35 bg-blue-950/35 p-5 shadow-glass`}
            >
              <h2 className="text-xs uppercase tracking-wider text-muted-foreground">
                Today’s sessions
              </h2>
              <p className="mt-3 font-display text-3xl font-semibold">{data.today.total}</p>
              <p className="mt-3 text-xs text-muted-foreground">
                {Object.entries(data.today.breakdown)
                  .filter(([, count]) => count > 0)
                  .map(([key, count]) => `${count} ${key}`)
                  .join(" · ") || "No sessions today"}
              </p>
            </button>
            <button
              type="button"
              onClick={() => onOpenCheckIns(session.id)}
              className={`${kpiButton} rounded-2xl border border-emerald-300/50 bg-emerald-900/55 p-5 shadow-glass`}
            >
              <h2 className="text-xs uppercase tracking-wider text-muted-foreground">
                Check-in rate
              </h2>
              <p className="mt-3 font-display text-3xl font-semibold">
                {data.expected_count
                  ? `${Math.round((data.submitted_count / data.expected_count) * 100)}%`
                  : "Unavailable"}
              </p>
              <p className="mt-3 text-xs text-muted-foreground">
                {data.submitted_count} / {data.expected_count} submitted
              </p>
              {data.status === "active" && (
                <p className="mt-2 text-xs text-muted-foreground">Live</p>
              )}
            </button>
            <button
              type="button"
              className={`${kpiButton} rounded-2xl border border-rose-400/45 bg-rose-950/35 p-5 shadow-glass`}
              onClick={() => filter(["flagged", "appealed"])}
            >
              <h2 className="text-xs uppercase tracking-wider text-muted-foreground">
                Needs review
              </h2>
              <p className="mt-3 font-display text-3xl font-semibold">
                {data.by_status.flagged + data.by_status.appealed}
              </p>
              <p className="mt-3 text-xs text-muted-foreground">
                {data.by_status.flagged} flagged · {data.by_status.appealed} appealed
              </p>
              <p className="mt-2 text-xs text-warning">
                {data.by_status.flagged + data.by_status.appealed
                  ? "Outstanding"
                  : "No outstanding reviews"}
              </p>
            </button>
            <section className="rounded-2xl border border-orange-400/45 bg-orange-900/45 p-5 shadow-glass">
              <h2 className="text-xs uppercase tracking-wider text-muted-foreground">
                Average risk score
              </h2>
              <p className="mt-3 font-display text-3xl font-semibold">
                {data.scored_count ? (
                  <>
                    {data.average_risk_score.toFixed(2)}{" "}
                    <span className="text-lg text-muted-foreground">/ 1</span>
                  </>
                ) : (
                  "No scored check-ins"
                )}
              </p>
              <p className="mt-3 text-xs text-muted-foreground">
                {data.scored_count} scored check-ins only
              </p>
            </section>
          </div>
          {data.status === "scheduled" &&
            parseApiDateTime(data.server_time) < parseApiDateTime(data.scheduled_start) &&
            !data.submitted_count && (
              <p className="text-sm text-muted-foreground">
                Check-ins have not opened for this scheduled session.
              </p>
            )}
          {data.status === "cancelled" && (
            <p className="text-sm text-muted-foreground">This session is cancelled.</p>
          )}
          <div className="grid min-w-0 gap-4 lg:grid-cols-[1.25fr_1fr]">
            <SessionTimeline stats={data} />
            <VerificationDonut stats={data} verification={verification} onFilter={filter} />
          </div>
        </>
      )}
      <div ref={rosterAnchor} className="min-w-0 scroll-mt-4">
        {rosterError && (
          <p role="alert" className="mb-3 text-sm text-destructive">
            {rosterError}{" "}
            <button
              type="button"
              className="underline"
              onClick={() => {
                void roster.refetch();
                if (reviewOnly) void flagged.refetch();
              }}
            >
              Retry
            </button>
          </p>
        )}
        <AttendanceRoster
          rows={attendance?.items ?? []}
          loading={roster.isPending || (reviewOnly && flagged.isPending)}
          error={rosterError}
          verification={verification}
          onVerificationChange={setVerification}
          flaggedIds={
            reviewOnly && flagged.data ? new Set(flagged.data.map((row) => row.id)) : undefined
          }
          onSelect={setSelected}
          onExport={() => {}}
          exporting={false}
          canExport={false}
          checkInsOnly
        />
      </div>
      {selected?.checkin_id && (
        <CheckInDetail
          key={selected.checkin_id}
          entry={selected}
          session={session}
          courseId={courseId}
          userId={userId}
          onClose={() => setSelected(null)}
        />
      )}
      <RecentReviewActivity
        sessionId={session.id}
        sessionName={session.name}
        courseCode={data?.course_code ?? ""}
        timeZone={data?.timezone ?? "Asia/Singapore"}
        events={data?.recent_review_activity ?? []}
        loading={!stats.isError && !data}
        error={stats.isError}
        onRetry={() => void stats.refetch()}
      />
    </>
  );
}

function SessionTimeline({ stats }: { stats: SessionStats }) {
  const buckets = sessionTimeline(stats);
  const label = (item: TimelineBucket) =>
    `${sessionClock(item.start, stats.timezone)}–<${sessionClock(item.end, stats.timezone)}`;
  return (
    <section className="min-w-0 rounded-2xl border border-border bg-glass p-5">
      <h2 className="text-sm font-semibold">Check-ins over time</h2>
      <p className="mt-4 text-[10px] text-muted-foreground">Check-ins per interval</p>
      <div
        className="mt-5 h-80 min-w-0"
        role="img"
        aria-label={`Five-minute check-in counts for ${stats.session_name}`}
      >
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={buckets} margin={{ top: 10, right: 12, bottom: 8, left: -18 }}>
            <CartesianGrid vertical={false} stroke="var(--border)" />
            <XAxis
              dataKey="start"
              tickFormatter={(value) => sessionClock(Number(value), stats.timezone)}
              interval={Math.max(0, Math.ceil(buckets.length / 5) - 1)}
              tick={{ fontSize: 10 }}
            />
            <YAxis
              allowDecimals={false}
              domain={[0, (max: number) => Math.max(1, max)]}
              tick={{ fontSize: 10 }}
            />
            <Tooltip
              content={({ active, payload }) => {
                const item = payload?.[0]?.payload as TimelineBucket | undefined;
                return active && item ? (
                  <div className="max-w-64 rounded-lg border border-border bg-card p-3 text-xs">
                    <p>{label(item)}</p>
                    <p>
                      {item.count == null ? "Future interval" : `${item.count} check-ins`}
                      {item.current ? " · In progress" : ""}
                    </p>
                    {item.preOpening > 0 && (
                      <p className="mt-1">
                        Includes {item.preOpening} pre-opening records clamped into this bucket.
                      </p>
                    )}
                    {item.outsideWindow && <p>Recorded outside the configured window.</p>}
                  </div>
                ) : null;
              }}
            />
            <Line
              type="linear"
              dataKey="count"
              stroke="#ac8be9"
              strokeWidth={2}
              dot={{ r: 3 }}
              connectNulls={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-1 text-center text-[10px] text-muted-foreground">5-minute interval start</p>
      {buckets.some((item) => item.current) && (
        <p className="mt-2 text-xs text-muted-foreground">
          Current interval: {label(buckets.find((item) => item.current)!)} · In progress
        </p>
      )}
      {!stats.submitted_count && (
        <p className="mt-3 text-xs text-muted-foreground">
          No check-ins submitted for this {stats.status} session.
        </p>
      )}
    </section>
  );
}

function VerificationDonut({
  stats,
  verification,
  onFilter,
}: {
  stats: SessionStats;
  verification: string[];
  onFilter: (value: string[]) => void;
}) {
  let offset = 0;
  const total = stats.submitted_count;
  return (
    <section className="min-w-0 rounded-2xl border border-border bg-glass p-5">
      <h2 className="text-sm font-semibold">Verification status</h2>
      {total ? (
        <div className="relative mx-auto my-5 size-44">
          <svg
            viewBox="0 0 120 120"
            className="size-full -rotate-90"
            aria-label="Verification status distribution"
          >
            {statuses.map((status) => {
              const fraction = stats.by_status[status] / total;
              const before = offset;
              offset += fraction;
              return fraction > 0 ? (
                <circle
                  key={status}
                  cx="60"
                  cy="60"
                  r="48"
                  fill="none"
                  stroke={verificationColors[status]}
                  strokeWidth="16"
                  pathLength="100"
                  strokeDasharray={`${fraction * 100} ${100 - fraction * 100}`}
                  strokeDashoffset={-before * 100}
                  role="button"
                  tabIndex={0}
                  aria-label={`Filter ${status}: ${stats.by_status[status]}`}
                  onClick={() => onFilter([status])}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      onFilter([status]);
                    }
                  }}
                  className="cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary"
                />
              ) : null;
            })}
          </svg>
          <div className="pointer-events-none absolute inset-0 grid content-center justify-items-center">
            <p className="font-display text-3xl font-semibold">{total}</p>
            <p className="mt-1 text-xs text-muted-foreground">Submitted</p>
          </div>
        </div>
      ) : (
        <p className="my-8 text-center text-sm text-muted-foreground">No submitted check-ins.</p>
      )}
      <div className="space-y-1">
        {statuses.map((status) => (
          <button
            type="button"
            key={status}
            aria-pressed={verification.length === 1 && verification[0] === status}
            onClick={() => onFilter([status])}
            className="flex w-full items-center justify-between gap-3 rounded-lg px-2 py-2 text-left text-xs hover:bg-secondary/40 focus-visible:ring-2 focus-visible:ring-primary"
          >
            <span className="flex items-center gap-2 capitalize">
              <span
                className="size-2 rounded-full"
                style={{ backgroundColor: verificationColors[status] }}
              />
              {status}
            </span>
            <span>
              {stats.by_status[status]} ·{" "}
              {total ? ((stats.by_status[status] / total) * 100).toFixed(1) : "0.0"}%
            </span>
          </button>
        ))}
      </div>
    </section>
  );
}
