import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { KpiCard } from "./KpiCard";
import { CourseHistory } from "./CourseHistory";
import { LiveActivity } from "./LiveActivity";
import { fetchActiveSessions, fetchMyCheckIns, fetchMyEnrollments, toRows } from "@/lib/attendance";

export function StudentView() {
  const q = useQuery({
    queryKey: ["my-check-ins"],
    queryFn: fetchMyCheckIns,
    refetchInterval: 30000,
  });
  const enrollments = useQuery({
    queryKey: ["my-enrollments"],
    queryFn: fetchMyEnrollments,
  });
  const activeSessions = useQuery({
    queryKey: ["active-sessions"],
    queryFn: fetchActiveSessions,
    refetchInterval: 30000,
  });
  const rows = useMemo(() => toRows(q.data ?? []), [q.data]);
  const enrolledCourseIds = useMemo(
    () =>
      new Set(
        (enrollments.isSuccess ? enrollments.data : []).map((enrollment) => enrollment.course_id),
      ),
    [enrollments.data, enrollments.isSuccess],
  );
  const myActiveSessions = useMemo(
    () =>
      activeSessions.isSuccess && enrollments.isSuccess
        ? (activeSessions.data ?? []).filter((session) => enrolledCourseIds.has(session.course_id))
        : [],
    [activeSessions.data, activeSessions.isSuccess, enrollments.isSuccess, enrolledCourseIds],
  );

  const approved = rows.filter((r) => r.status === "approved").length;
  const flagged = rows.filter((r) => r.status === "flagged").length;
  const rejected = rows.filter((r) => r.status === "rejected").length;
  const rate = rows.length ? Math.round((approved / rows.length) * 100) : 0;
  const courses = new Set(rows.map((r) => r.course)).size;

  return (
    <>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        <KpiCard
          label="My check-ins"
          value={String(rows.length)}
          note={`across ${courses} course${courses === 1 ? "" : "s"}`}
          tone="brand"
          bars={[35, 50, 44, 68, 60, 100]}
        />
        <KpiCard
          label="Attendance rate"
          value={`${rate}%`}
          note={`${approved} approved records`}
          tone="accent"
          progress={rate}
        />
        <KpiCard
          label="Flagged"
          value={String(flagged)}
          note="check-ins under review"
          tone="warning"
          progress={rows.length ? (flagged / rows.length) * 100 : 0}
        />
        <KpiCard
          label="Rejected"
          value={String(rejected)}
          note="check-ins not approved"
          tone={rejected > 0 ? "danger" : "accent"}
          progress={rows.length ? (rejected / rows.length) * 100 : 0}
        />
        <CourseHistory rows={rows} />
        <LiveActivity rows={rows.slice(0, 4)} />
        <section className="lg:col-span-12 rounded-2xl border border-border bg-glass p-5">
          <div>
            <h2 className="font-display text-base text-foreground">
              Open sessions in your courses
            </h2>
            <p className="mt-1 text-xs text-muted-foreground">
              Only sessions for your active course enrollments are shown. Start check-in from the
              student check-in app.
            </p>
          </div>
          {enrollments.isLoading || activeSessions.isLoading ? (
            <p className="mt-4 text-sm text-muted-foreground">Loading your open sessions…</p>
          ) : enrollments.isError || activeSessions.isError ? (
            <p className="mt-4 rounded-xl border border-warning/30 bg-warning/10 p-4 text-sm text-warning">
              Could not load course enrollments or open sessions.
            </p>
          ) : myActiveSessions.length === 0 ? (
            <p className="mt-4 text-sm text-muted-foreground">
              No check-in sessions are currently open for your courses.
            </p>
          ) : (
            <ul className="mt-4 divide-y divide-border">
              {myActiveSessions.map((session) => (
                <li
                  key={session.id}
                  className="flex flex-wrap items-center justify-between gap-3 py-3 first:pt-0 last:pb-0"
                >
                  <div>
                    <p className="text-sm font-medium text-foreground">
                      {session.course_code ?? "Course"} · {session.course_name ?? session.name}
                    </p>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      {session.name}
                      {session.venue_name ? ` · ${session.venue_name}` : ""}
                    </p>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Check-in closes{" "}
                    {new Date(session.checkin_closes_at).toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </>
  );
}
