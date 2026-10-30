import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "@/lib/api";
import { formatSingaporeDateTime } from "@/lib/time";
import type { CourseRow } from "@/lib/attendance";

type OverviewData = {
  course_code: string;
  course_name: string;
  timezone: string;
  attendance: {
    recorded: number;
    expected: number;
    rate: number;
    held_sessions: number;
    active_sessions: number;
    approval_rate: number | null;
    historical_enrollment_limited: boolean;
  };
  outstanding: { flagged: number; appealed: number };
  today: { date: string; total: number; breakdown: Record<string, number> };
  low_participation: {
    threshold: number;
    total: number;
    students: Array<{
      student_id: string;
      student_name: string;
      student_email: string;
      submitted_sessions: number;
      expected_sessions: number;
      participation_rate: number;
    }>;
  };
  risk_distribution: {
    scored_count: number;
    bands: Array<{ key: "low" | "medium" | "high"; count: number }>;
  };
  trend: Array<{
    start: string;
    end: string;
    recorded: number;
    expected: number;
    rate: number | null;
    provisional: boolean;
  }>;
  recent_sessions: Array<{
    session_id: string;
    name: string;
    status: string;
    scheduled_start: string;
    scheduled_end: string;
    recorded: number;
    expected: number;
    rate: number;
  }>;
};

type Mode = "weekly" | "monthly";

function isoDate(date: Date) {
  return date.toISOString().slice(0, 10);
}

function dateOnly(value: string) {
  return new Date(`${value}T00:00:00Z`);
}

function addDays(value: string, days: number) {
  const result = dateOnly(value);
  result.setUTCDate(result.getUTCDate() + days);
  return isoDate(result);
}

function monthStart() {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Singapore",
    year: "numeric",
    month: "2-digit",
  }).formatToParts(new Date());
  const part = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((item) => item.type === type)?.value ?? "";
  return `${part("year")}-${part("month")}`;
}

function rangeFor(mode: Mode, value: string) {
  if (mode === "weekly") return { start: value, end: addDays(value, 7) };
  const start = `${value}-01`;
  const end = dateOnly(start);
  end.setUTCMonth(end.getUTCMonth() + 1);
  return { start, end: isoDate(end) };
}

function percent(value: number | null) {
  return value == null ? "—" : `${Math.round(value * 100)}%`;
}

function exactPercent(value: number | null) {
  if (value == null) return "—";
  return `${(value * 100)
    .toFixed(2)
    .replace(/\.00$/, "")
    .replace(/(\.\d)0$/, "$1")}%`;
}

function Card({
  children,
  onClick,
  className = "",
}: {
  children: ReactNode;
  onClick?: () => void;
  className?: string;
}) {
  const content = (
    <div className={`h-full rounded-2xl border bg-glass p-5 shadow-glass ${className}`}>
      {children}
    </div>
  );
  return onClick ? (
    <button
      type="button"
      className="h-full w-full cursor-pointer text-left transition duration-150 ease-out hover:-translate-y-0.5 hover:shadow-lg active:translate-y-0.5 active:scale-[0.99] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background"
      onClick={onClick}
    >
      {content}
    </button>
  ) : (
    content
  );
}

function bucketDate(value: string) {
  return new Date(`${value}T00:00:00+08:00`);
}

function bucketRangeLabel(item: OverviewData["trend"][number]) {
  const start = bucketDate(item.start);
  const end = bucketDate(item.end);
  end.setDate(end.getDate() - 1);
  const format = (date: Date) =>
    new Intl.DateTimeFormat("en-SG", {
      month: "short",
      day: "numeric",
      timeZone: "Asia/Singapore",
    }).format(date);
  return start.toDateString() === end.toDateString()
    ? format(start)
    : `${format(start)}–${format(end)}`;
}

function bucketLabel(item: OverviewData["trend"][number], monthly: boolean, index?: number) {
  return monthly && index != null ? `W${index + 1}` : bucketRangeLabel(item);
}

function Trend({ data, monthly }: { data: OverviewData["trend"]; monthly: boolean }) {
  const points = data.map((item, index) => ({
    ...item,
    label: `${bucketLabel(item, monthly, index)}${item.provisional ? " (live)" : ""}`,
  }));
  return (
    <section className="min-w-0 rounded-2xl border border-border bg-glass p-5">
      <h2 className="font-display text-base font-semibold">Attendance rate over time</h2>
      <p className="text-xs text-muted-foreground">
        {monthly ? "Weekly" : "Daily"} recorded participation · 0–100%
      </p>
      {data.length ? (
        <div className="mt-8">
          <div
            className="h-60 min-w-0"
            role="img"
            aria-label="Attendance rate over time. Hover over a point for its period, recorded and expected counts, and rate."
          >
            <ResponsiveContainer width="100%" height="100%">
              <LineChart
                data={points}
                margin={{ top: 8, right: 12, bottom: 0, left: -12 }}
                accessibilityLayer
              >
                <XAxis dataKey="label" interval={0} tick={{ fontSize: 10 }} />
                <YAxis
                  domain={[0, 1]}
                  ticks={[0, 0.25, 0.5, 0.75, 1]}
                  tickFormatter={percent}
                  tick={{ fontSize: 10 }}
                />
                <Tooltip
                  filterNull={false}
                  content={({ active, payload }) => {
                    const item = payload?.[0]?.payload as (typeof points)[number] | undefined;
                    return active && item ? (
                      <div className="max-w-64 rounded-lg border border-border bg-card p-3 text-xs shadow-lg">
                        <p className="font-medium">
                          {monthly ? `${item.label}: ` : ""}
                          {bucketRangeLabel(item)}
                        </p>
                        <p className="mt-1">
                          {item.recorded} recorded / {item.expected} expected
                        </p>
                        <p className="mt-1">
                          {item.rate == null
                            ? "No attendance rate available"
                            : `Attendance rate: ${exactPercent(item.rate)}`}
                        </p>
                        {item.provisional && (
                          <p className="mt-1 text-muted-foreground">
                            Provisional: includes active sessions.
                          </p>
                        )}
                      </div>
                    ) : null;
                  }}
                />
                <Line
                  type="linear"
                  dataKey="rate"
                  stroke="oklch(0.63 0.19 285)"
                  strokeWidth={2}
                  dot={{ r: 4, fill: "#c4b5fd" }}
                  activeDot={{ r: 5 }}
                  connectNulls={false}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <p className="mt-2 text-center text-[10px] text-muted-foreground">
            {monthly ? "Week" : "Day"}
          </p>
        </div>
      ) : (
        <p className="mt-8 text-sm text-muted-foreground">No data for this period.</p>
      )}
    </section>
  );
}

export function InstructorOverview({
  courses,
  coursesLoading,
  selectedCourseId,
  onCourseChange,
  onOpenCheckIns,
  onOpenSessions,
  reportingWeek,
}: {
  courses: CourseRow[];
  coursesLoading: boolean;
  selectedCourseId: string;
  onCourseChange: (id: string) => void;
  onOpenCheckIns: (reviewOnly?: boolean, sessionId?: string) => void;
  onOpenSessions: () => void;
  reportingWeek?: string;
}) {
  const [mode, setMode] = useState<Mode>(reportingWeek ? "weekly" : "monthly");
  const [period, setPeriod] = useState(monthStart);
  const [studentSearch, setStudentSearch] = useState("");
  const [studentPage, setStudentPage] = useState(0);
  const range = useMemo(
    () =>
      reportingWeek
        ? { start: reportingWeek, end: addDays(reportingWeek, 7) }
        : rangeFor(mode, period),
    [mode, period, reportingWeek],
  );
  // Course statistics use an inclusive end, down to database microsecond precision.
  const inclusiveEnd = `${addDays(range.end, -1)}T23:59:59.999999+08:00`;
  const courseStats = useQuery({
    queryKey: ["instructor-course-stats", selectedCourseId, range.start, inclusiveEnd],
    enabled: Boolean(selectedCourseId),
    queryFn: ({ signal }) =>
      api.request<{ overall_attendance_rate: number }>(
        `/stats/courses/${encodeURIComponent(selectedCourseId)}?start_date=${encodeURIComponent(`${range.start}T00:00:00+08:00`)}&end_date=${encodeURIComponent(inclusiveEnd)}`,
        { signal },
      ),
  });
  const overview = useQuery({
    queryKey: ["instructor-overview", selectedCourseId, mode, range.start, range.end],
    enabled: Boolean(selectedCourseId),
    queryFn: ({ signal }) =>
      api.request<OverviewData>(
        `/stats/courses/${encodeURIComponent(selectedCourseId)}/overview?start_date=${encodeURIComponent(`${range.start}T00:00:00+08:00`)}&end_date=${encodeURIComponent(`${range.end}T00:00:00+08:00`)}`,
        { signal },
      ),
  });
  useEffect(() => {
    const firstCourse = courses[0];
    if (firstCourse && !courses.some((course) => course.id === selectedCourseId))
      onCourseChange(firstCourse.id);
  }, [courses, selectedCourseId, onCourseChange]);
  useEffect(() => {
    setStudentSearch("");
    setStudentPage(0);
  }, [selectedCourseId, mode, period]);

  if (coursesLoading)
    return (
      <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[1, 2, 3, 4].map((item) => (
          <div
            key={item}
            className="h-36 animate-pulse rounded-2xl border border-border bg-glass"
          />
        ))}
      </div>
    );
  if (!courses.length)
    return (
      <div className="mt-4 rounded-2xl border border-border bg-glass p-8 text-sm text-muted-foreground">
        No courses are assigned to your instructor account.
      </div>
    );
  if (overview.isError || courseStats.isError)
    return (
      <div
        role="alert"
        className="mt-4 rounded-2xl border border-destructive/40 bg-destructive/10 p-5 text-sm text-destructive"
      >
        Could not load overview statistics.{" "}
        <button
          type="button"
          className="ml-2 underline"
          onClick={() => {
            void overview.refetch();
            void courseStats.refetch();
          }}
        >
          Retry
        </button>
      </div>
    );
  if (overview.isPending || !overview.data || courseStats.isPending || !courseStats.data)
    return (
      <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[1, 2, 3, 4].map((item) => (
          <div
            key={item}
            className="h-36 animate-pulse rounded-2xl border border-border bg-glass"
          />
        ))}
      </div>
    );

  const data = overview.data;
  const filteredStudents = data.low_participation.students.filter((student) =>
    `${student.student_name} ${student.student_email}`
      .toLowerCase()
      .includes(studentSearch.toLowerCase()),
  );
  const studentPageSize = 5;
  const visibleStudents = filteredStudents.slice(
    studentPage * studentPageSize,
    (studentPage + 1) * studentPageSize,
  );
  const studentPages = Math.max(1, Math.ceil(filteredStudents.length / studentPageSize));
  const bandLabels = {
    low: { label: "Low", range: "<0.3" },
    medium: { label: "Medium", range: "0.3–<0.5" },
    high: { label: "High", range: "≥0.5" },
  };
  const riskBands = data.risk_distribution.bands.map((item) => ({
    ...bandLabels[item.key],
    count: item.count,
  }));
  const maxRisk = Math.max(1, ...riskBands.map((item) => item.count));
  const riskStep = maxRisk <= 5 ? 1 : maxRisk <= 10 ? 2 : maxRisk <= 20 ? 5 : 10;
  const riskAxisMax = Math.ceil(maxRisk / riskStep) * riskStep;
  const riskTicks = Array.from(
    { length: riskAxisMax / riskStep + 1 },
    (_, index) => riskAxisMax - index * riskStep,
  );
  return (
    <div className="mt-4 space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <label className="grid gap-1 text-xs text-muted-foreground">
          Course
          <select
            aria-label="Overview course"
            value={selectedCourseId}
            onChange={(event) => onCourseChange(event.target.value)}
            className="min-w-64 rounded-lg border border-border bg-secondary/40 px-3 py-2 text-sm text-foreground focus-visible:ring-2 focus-visible:ring-primary"
          >
            {courses.map((course) => (
              <option value={course.id} key={course.id}>
                {course.code} · {course.name}
              </option>
            ))}
          </select>
        </label>
        {!reportingWeek && (
          <>
            <div
              className="flex rounded-lg border border-border p-1"
              role="group"
              aria-label="Reporting mode"
            >
              <button
                type="button"
                className={`rounded-md px-3 py-2 text-xs ${mode === "weekly" ? "bg-primary/20 text-primary" : "text-muted-foreground"}`}
                onClick={() => {
                  setMode("weekly");
                  setPeriod(range.start);
                }}
              >
                Weekly
              </button>
              <button
                type="button"
                className={`rounded-md px-3 py-2 text-xs ${mode === "monthly" ? "bg-primary/20 text-primary" : "text-muted-foreground"}`}
                onClick={() => {
                  setMode("monthly");
                  setPeriod(monthStart());
                }}
              >
                Monthly
              </button>
            </div>
            <label className="grid gap-1 text-xs text-muted-foreground">
              {mode === "weekly" ? "Week starting" : "Month"}
              <input
                type={mode === "weekly" ? "date" : "month"}
                value={period}
                onChange={(event) => {
                  if (event.target.value && event.target.validity.valid) {
                    setPeriod(event.target.value);
                  }
                }}
                className="rounded-lg border border-border bg-secondary/40 px-3 py-2 text-sm text-foreground focus-visible:ring-2 focus-visible:ring-primary"
              />
            </label>
          </>
        )}
        <p className="ml-auto text-xs text-muted-foreground">
          {range.start} – {addDays(range.end, -1)}
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Card className="border-emerald-300/50 !bg-emerald-900/55 p-4">
          <p className="text-xs uppercase tracking-wider text-muted-foreground">Attendance rate</p>
          <p className="mt-2 font-display text-3xl font-semibold">
            {percent(courseStats.data.overall_attendance_rate)}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">Includes active sessions</p>
          <p className="mt-2 text-xs text-accent">
            Approval rate: {percent(data.attendance.approval_rate)}
          </p>
        </Card>
        <Card
          onClick={() => onOpenCheckIns(true)}
          className="border-rose-400/45 bg-rose-950/35 p-4"
        >
          <p className="text-xs uppercase tracking-wider text-muted-foreground">Needs review</p>
          <p className="mt-2 font-display text-3xl font-semibold">
            {data.outstanding.flagged + data.outstanding.appealed}
          </p>
          <p className="mt-2 text-xs text-warning">Outstanding</p>
          <p className="mt-2 text-xs text-muted-foreground">
            Flagged {data.outstanding.flagged} · Appealed {data.outstanding.appealed}
          </p>
        </Card>
        <Card onClick={onOpenSessions} className="border-blue-400/35 !bg-blue-950/35 p-4">
          <p className="text-xs uppercase tracking-wider text-muted-foreground">Today’s sessions</p>
          <p className="mt-2 font-display text-3xl font-semibold">{data.today.total}</p>
          <p className="mt-2 text-xs text-muted-foreground">
            {Object.entries(data.today.breakdown)
              .filter(([key]) => key.toLowerCase() !== "closed")
              .map(([key, value]) => `${key} ${value}`)
              .join(" · ")}
          </p>
        </Card>
        <Card className="border-orange-400/45 bg-orange-900/45 p-4">
          <p className="text-xs uppercase tracking-wider text-muted-foreground">
            Low check-in participation
          </p>
          <p className="mt-2 font-display text-3xl font-semibold">{data.low_participation.total}</p>
          <p className="mt-2 text-xs text-warning">≤40% check-ins · Closed sessions</p>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Trend data={data.trend} monthly={mode === "monthly"} />
        <section className="rounded-2xl border border-border bg-glass p-5">
          <h2 className="font-display text-base font-semibold">Risk score distribution</h2>
          <p className="mt-1 text-xs text-muted-foreground">
            {data.risk_distribution.scored_count} scored check-ins
          </p>
          <div className="mt-8 flex h-52">
            <div className="relative h-44 w-8 shrink-0 border-r border-border text-[10px] text-muted-foreground">
              {riskTicks.map((tick, index) => (
                <span
                  key={`${tick}-${index}`}
                  className="absolute right-2 -translate-y-1/2"
                  style={{
                    bottom: `${(riskTicks.length - 1 - index) * (100 / (riskTicks.length - 1))}%`,
                  }}
                >
                  {tick}
                </span>
              ))}
            </div>
            <div className="relative h-44 min-w-0 flex-1 border-b border-border">
              <div className="pointer-events-none absolute inset-0 flex flex-col justify-between">
                {riskTicks.map((_, index) => (
                  <span key={index} className="border-t border-border/60" />
                ))}
              </div>
              <div className="relative z-10 flex h-full items-end gap-0">
                {riskBands.map((item) => (
                  <div
                    key={item.label}
                    className="relative flex h-full flex-1 items-end justify-center"
                  >
                    <span
                      className="absolute text-xs"
                      style={{ bottom: `${(item.count / riskAxisMax) * 100}%` }}
                    >
                      {item.count}
                    </span>
                    <div
                      className="mx-auto w-1/2 min-w-3 rounded-t-sm border-x border-background/20 bg-violet-400"
                      title={`${item.label} (${item.range}): ${item.count} check-ins`}
                      style={{
                        height: `${(item.count / riskAxisMax) * 100}%`,
                        minHeight: item.count > 0 ? "4px" : "0px",
                      }}
                    />
                  </div>
                ))}
              </div>
            </div>
          </div>
          <div className="ml-8 flex gap-0 text-center text-[10px] text-muted-foreground">
            {riskBands.map((item) => (
              <span key={item.label} className="flex-1">
                <span className="block">{item.label}</span>
                <span className="block">{item.range}</span>
              </span>
            ))}
          </div>
        </section>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="rounded-2xl border border-border bg-glass p-5">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="font-display text-sm font-medium">Low participation students</h2>
            </div>
          </div>
          <input
            aria-label="Search low participation students"
            value={studentSearch}
            onChange={(event) => {
              setStudentSearch(event.target.value);
              setStudentPage(0);
            }}
            placeholder="Search students"
            className="mt-3 w-full rounded-lg border border-border bg-secondary/40 px-3 py-2 text-xs text-foreground focus-visible:ring-2 focus-visible:ring-primary"
          />
          <div className="mt-4 space-y-2">
            {visibleStudents.length ? (
              visibleStudents.map((student) => (
                <Link
                  to="/students/$studentId/attendance"
                  params={{ studentId: student.student_id }}
                  search={{ courseId: selectedCourseId, from: "overview" }}
                  key={student.student_id}
                  className="flex w-full items-center justify-between rounded-lg border border-border/60 p-3 text-left text-xs hover:bg-secondary/40 focus-visible:ring-2 focus-visible:ring-primary"
                >
                  <span>
                    <span className="block text-foreground">{student.student_name}</span>
                    <span className="text-muted-foreground">
                      {student.student_email} · {student.submitted_sessions}/
                      {student.expected_sessions} sessions
                    </span>
                  </span>
                  <span className="text-warning">{percent(student.participation_rate)}</span>
                </Link>
              ))
            ) : (
              <p className="text-sm text-muted-foreground">
                {data.low_participation.students.length
                  ? "No matching students."
                  : "No students below the threshold."}
              </p>
            )}
          </div>
          {filteredStudents.length > studentPageSize && (
            <div className="mt-4 flex items-center justify-between text-xs text-muted-foreground">
              <span>
                Page {studentPage + 1} of {studentPages}
              </span>
              <span className="flex gap-2">
                <button
                  type="button"
                  className="rounded border border-border px-2 py-1 disabled:opacity-40"
                  disabled={!studentPage}
                  onClick={() => setStudentPage((page) => page - 1)}
                >
                  Previous
                </button>
                <button
                  type="button"
                  className="rounded border border-border px-2 py-1 disabled:opacity-40"
                  disabled={studentPage + 1 >= studentPages}
                  onClick={() => setStudentPage((page) => page + 1)}
                >
                  Next
                </button>
              </span>
            </div>
          )}
        </section>
        <section className="rounded-2xl border border-border bg-glass p-5">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="font-display text-sm font-medium">Recent session participation</h2>
              <p className="mt-1 text-xs text-muted-foreground">
                Closed sessions · recorded check-ins
              </p>
            </div>
            <button
              type="button"
              className="text-xs text-primary underline"
              onClick={onOpenSessions}
            >
              View all sessions
            </button>
          </div>
          <div className="mt-4 space-y-4">
            {data.recent_sessions.length ? (
              data.recent_sessions.map((session) => (
                <button
                  type="button"
                  key={session.session_id}
                  onClick={() => onOpenCheckIns(false, session.session_id)}
                  className="w-full text-left focus-visible:ring-2 focus-visible:ring-primary"
                >
                  <div className="flex justify-between gap-3 text-xs">
                    <span className="truncate">{session.name}</span>
                    <span>
                      {percent(session.rate)} · {session.recorded}/{session.expected}
                    </span>
                  </div>
                  <div className="mt-2 h-2 overflow-hidden rounded-full bg-secondary">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-primary to-accent"
                      style={{ width: `${Math.min(100, session.rate * 100)}%` }}
                    />
                  </div>
                  <p className="mt-1 text-[10px] text-muted-foreground">
                    {formatSingaporeDateTime(session.scheduled_end, {
                      day: "numeric",
                      month: "short",
                      hour: "numeric",
                      minute: "2-digit",
                      hour12: true,
                    })}{" "}
                    {!reportingWeek && "SGT"}
                  </p>
                </button>
              ))
            ) : (
              <p className="text-sm text-muted-foreground">No closed sessions in this period.</p>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
