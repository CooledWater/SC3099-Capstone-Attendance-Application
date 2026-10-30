import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  CartesianGrid,
} from "recharts";
import {
  fetchAdminChartData,
  localDate,
  weekStart,
  type CourseParticipation,
} from "@/lib/admin-overview-charts";
import { InstructorOverview } from "./InstructorOverview";

const card = "min-w-0 rounded-2xl border border-border bg-glass p-5";
const percent = (rate: number | null) =>
  rate == null ? "No data" : `${Number((rate * 100).toFixed(2))}%`;
const dateLabel = (date: string, weekday = false) =>
  new Intl.DateTimeFormat("en-GB", {
    timeZone: "UTC",
    day: "numeric",
    month: "short",
    ...(weekday ? { weekday: "short" as const } : { year: "numeric" as const }),
  }).format(new Date(`${date}T00:00:00Z`));
function courseTooltip(course: CourseParticipation) {
  return `${course.course_code} · ${course.course_name}\n${percent(course.rate)}\n${course.recorded_checkins} recorded check-ins / ${course.expected_attendances ?? "No data"} expected student-session attendances${course.active_sessions ? "\nProvisional: includes active sessions" : ""}${course.rate != null && course.rate > 1 ? "\nExceeds saved enrollment denominator; not capped" : ""}`;
}
export function AdminOverviewCharts({
  userId,
  timezone,
  onOpenCheckIns,
  onOpenSessions,
}: {
  userId: string;
  timezone: string;
  onOpenCheckIns: (courseId: string, reviewOnly: boolean, sessionId: string) => void;
  onOpenSessions: (courseId: string) => void;
}) {
  const [start, setStart] = useState(() => weekStart(localDate(new Date(), timezone)));
  const [dateDraft, setDateDraft] = useState(start);
  const [detailId, setDetailId] = useState("");
  const [hovered, setHovered] = useState<string | null>(null);
  const query = useQuery({
    queryKey: ["admin-overview-charts", userId, start, timezone],
    queryFn: ({ signal }) => fetchAdminChartData(start, timezone, signal),
    refetchInterval: 30000,
    staleTime: 30000,
    retry: 1,
  });
  const points = query.data?.days ?? [];
  const courses = query.data?.courses ?? [];
  const selected = courses.find((course) => course.course_id === detailId);
  const hoveredCourse = courses.find((course) => course.course_id === hovered);
  const detailPanel = useRef<HTMLElement>(null);
  useEffect(() => {
    if (detailId) {
      detailPanel.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      detailPanel.current?.focus({ preventScroll: true });
    }
  }, [detailId]);
  function applyWeek(value: string, valid: boolean) {
    if (!value || !valid || !/^\d{4}-\d{2}-\d{2}$/.test(value)) {
      setDateDraft(start);
      return;
    }
    const next = weekStart(value);
    setDateDraft(next);
    if (next !== start) {
      setStart(next);
      setDetailId("");
    }
  }
  return (
    <div className="mt-4 space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <label className="grid gap-1 text-xs text-muted-foreground">
          Week starting
          <input
            aria-label="Admin reporting week"
            type="date"
            value={dateDraft}
            className="rounded-lg border border-border bg-secondary/40 px-3 py-2 text-sm text-foreground focus-visible:ring-2 focus-visible:ring-primary"
            onChange={(event) => {
              setDateDraft(event.target.value);
            }}
            onBlur={(event) =>
              applyWeek(event.currentTarget.value, event.currentTarget.validity.valid)
            }
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                applyWeek(event.currentTarget.value, event.currentTarget.validity.valid);
              } else if (event.key === "Escape") {
                event.preventDefault();
                setDateDraft(start);
              }
            }}
          />
        </label>
      </div>
      {query.isError ? (
        <p role="alert" className={`${card} text-sm text-destructive`}>
          Could not load weekly analytics.{" "}
          <button className="underline" onClick={() => void query.refetch()}>
            Retry
          </button>
        </p>
      ) : query.isPending || !query.data ? (
        <div role="status" className={`${card} animate-pulse text-sm text-muted-foreground`}>
          Loading weekly analytics…
        </div>
      ) : (
        <div className="grid gap-4 xl:grid-cols-2">
          <section className={card}>
            <h2 className="font-display text-base font-semibold">Check-ins over time</h2>
            <p className="mt-1 text-xs text-muted-foreground">All courses</p>
            <div className="mt-5 overflow-x-auto">
              <div
                className="h-72 min-w-[420px]"
                role="img"
                aria-label="Daily recorded check-ins for the selected week. Today is partial; future days are blank."
              >
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart
                    data={points}
                    margin={{ top: 18, right: 16, left: 8, bottom: 28 }}
                    accessibilityLayer
                  >
                    <CartesianGrid vertical={false} stroke="var(--color-border)" />
                    <XAxis
                      dataKey="date"
                      tickFormatter={(value) => dateLabel(value, true)}
                      interval={0}
                      tick={{ fontSize: 10 }}
                      label={{ value: "Date", position: "bottom", offset: 10 }}
                    />
                    <YAxis
                      allowDecimals={false}
                      domain={[0, Math.max(1, ...points.map((point) => point.count ?? 0))]}
                      tick={{ fontSize: 10 }}
                      label={{ value: "Check-ins", angle: -90, position: "insideLeft" }}
                    />
                    <Tooltip
                      filterNull={false}
                      content={({ active, payload }) => {
                        const item = payload?.[0]?.payload as (typeof points)[number] | undefined;
                        return active && item ? (
                          <div className="rounded-lg border border-border bg-card p-3 text-xs shadow-lg">
                            <p>{dateLabel(item.date)}</p>
                            <p>{item.count == null ? "Future date" : `${item.count} check-ins`}</p>
                            {item.partial && (
                              <p className="text-muted-foreground">Partial day · Today</p>
                            )}
                          </div>
                        ) : null;
                      }}
                    />
                    <Line
                      type="linear"
                      dataKey="count"
                      stroke="#a78bfa"
                      strokeWidth={2}
                      dot={{ r: 4, fill: "#a78bfa" }}
                      activeDot={{ r: 5 }}
                      connectNulls={false}
                      isAnimationActive={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          </section>
          <section className={card}>
            <h2 className="font-display text-base font-semibold">Attendance by course</h2>
            <p className="mt-2 text-xs text-muted-foreground">Attendance (%)</p>
            {!courses.length ? (
              <p className="py-12 text-sm text-muted-foreground">No courses available.</p>
            ) : (
              <div className="mt-6 flex">
                <div className="relative mb-10 h-52 w-12 shrink-0 text-xs text-muted-foreground">
                  {[0, 25, 50, 75, 100].map((tick) => (
                    <span
                      key={tick}
                      className="absolute right-2 translate-y-1/2"
                      style={{ bottom: `${tick}%` }}
                    >
                      {tick}%
                    </span>
                  ))}
                </div>
                <div
                  className="min-w-0 flex-1 overflow-x-auto pb-2"
                  tabIndex={0}
                  aria-label="Attendance by course chart; scroll to see all courses"
                >
                  <div
                    className="relative"
                    style={{ minWidth: Math.max(280, courses.length * 86) }}
                  >
                    <div className="pointer-events-none absolute inset-x-0 top-0 h-52">
                      {[0, 25, 50, 75, 100].map((tick) => (
                        <span
                          key={tick}
                          className="absolute inset-x-0 border-t border-border"
                          style={{ bottom: `${tick}%` }}
                        />
                      ))}
                    </div>
                    <div className="relative flex items-start">
                      {courses.map((course) => (
                        <button
                          key={course.course_id}
                          type="button"
                          className="group relative min-w-0 flex-1 rounded px-2 text-center focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                          title={courseTooltip(course)}
                          aria-label={`${courseTooltip(course)}. Open course analytics`}
                          onMouseEnter={() => setHovered(course.course_id)}
                          onMouseLeave={() => setHovered(null)}
                          onFocus={() => setHovered(course.course_id)}
                          onBlur={() => setHovered(null)}
                          onClick={() => setDetailId(course.course_id)}
                        >
                          <span className="relative flex h-52 items-end justify-center">
                            {course.rate != null && course.rate <= 1 ? (
                              <span
                                className="relative w-3/5 rounded-t-sm bg-violet-400 transition-opacity group-hover:opacity-80"
                                style={{ height: `${course.rate * 100}%` }}
                              >
                                <span className="absolute -top-6 left-1/2 -translate-x-1/2 whitespace-nowrap text-xs">
                                  {percent(course.rate)}
                                </span>
                              </span>
                            ) : (
                              <span className="self-center text-xs text-muted-foreground">
                                {percent(course.rate)}
                                {course.rate != null && "*"}
                              </span>
                            )}
                          </span>
                          <span className="mt-3 block break-words text-xs">
                            {course.course_code}
                          </span>
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            )}
            <p className="text-center text-xs text-muted-foreground">Course</p>
            {hoveredCourse && (
              <p
                role="tooltip"
                className="mt-3 whitespace-pre-line rounded-lg border border-border bg-card p-3 text-xs shadow-lg"
              >
                {courseTooltip(hoveredCourse)}
              </p>
            )}
            {courses.some((course) => course.rate != null && course.rate > 1) && (
              <p className="mt-2 text-xs text-warning">
                * Exceeds the saved enrollment denominator. The actual percentage is shown without
                capping.
              </p>
            )}
          </section>
        </div>
      )}
      {selected && (
        <section ref={detailPanel} tabIndex={-1} className={card} aria-label="Course analytics">
          <div className="flex items-center justify-between">
            <h2 className="font-display font-semibold">
              {selected.course_code} · Course analytics
            </h2>
            <button className="text-xs underline" onClick={() => setDetailId("")}>
              Close analytics
            </button>
          </div>
          <InstructorOverview
            courses={courses.map((course) => ({
              id: course.course_id,
              code: course.course_code,
              name: course.course_name,
            }))}
            coursesLoading={false}
            selectedCourseId={detailId}
            onCourseChange={setDetailId}
            reportingWeek={start}
            onOpenCheckIns={(review = false, session = "") =>
              onOpenCheckIns(detailId, review, session)
            }
            onOpenSessions={() => onOpenSessions(detailId)}
          />
        </section>
      )}
    </div>
  );
}
