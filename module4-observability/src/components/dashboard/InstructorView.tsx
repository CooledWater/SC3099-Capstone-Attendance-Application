import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { KpiCard } from "./KpiCard";
import { CheckInTrend } from "./CheckInTrend";
import { LiveActivity } from "./LiveActivity";
import { StatusPie } from "./StatusPie";
import { CourseAnalytics, type CourseStat } from "./CourseAnalytics";
import { EnrollmentsPanel } from "./EnrollmentsPanel";
import { ExportPanel } from "./ExportPanel";
import { SessionsPanel } from "./SessionsPanel";
import { CheckInsPanel } from "./CheckInsPanel";
import { AuditLogs } from "./AuditLogs";
import { MetricsPanel } from "./MetricsPanel";
import { Tabs } from "./Tabs";
import { fetchCheckIns, fetchCourses, fetchSessions, toRows, trendOf } from "@/lib/attendance";

const tabs = [
  { id: "overview", label: "Overview" },
  { id: "sessions", label: "Sessions" },
  { id: "checkins", label: "Check-ins" },
  { id: "enrollments", label: "Enrollments" },
  { id: "export", label: "Export" },
  { id: "audit", label: "Audit logs" },
  { id: "metrics", label: "Metrics" },
] as const;

type Tab = (typeof tabs)[number]["id"];

export function buildCourseStats(
  checkIns: Awaited<ReturnType<typeof fetchCheckIns>>,
  sessions: Awaited<ReturnType<typeof fetchSessions>>,
): CourseStat[] {
  const map = new Map<string, CourseStat & { riskSum: number }>();

  const ensure = (id: string, code: string, name: string) => {
    if (!map.has(id))
      map.set(id, {
        id,
        code,
        name,
        sessions: 0,
        checkIns: 0,
        expected: 0,
        flagged: 0,
        avgRisk: 0,
        riskSum: 0,
      });
    return map.get(id)!;
  };

  sessions.forEach((s) => {
    const c = ensure(s.course_id, s.courses?.code ?? "—", s.courses?.name ?? "Course");
    c.sessions += 1;
    c.expected += s.expected_attendance ?? 0;
  });

  checkIns.forEach((ci) => {
    const session = sessions.find((item) => item.id === ci.session_id);
    if (!session) return;
    const c = ensure(
      session.course_id,
      session.courses?.code ?? "—",
      session.courses?.name ?? "Course",
    );
    c.checkIns += 1;
    c.riskSum += ci.risk_score;
    if (ci.status === "flagged") c.flagged += 1;
  });

  return [...map.values()]
    .map((c) => ({ ...c, avgRisk: c.checkIns ? Math.round(c.riskSum / c.checkIns) : 0 }))
    .sort((a, b) => a.code.localeCompare(b.code));
}

export function InstructorView({ userId }: { userId: string }) {
  const [tab, setTab] = useState<Tab>("overview");
  const [selectedCourseId, setSelectedCourseId] = useState("all");
  const checkIns = useQuery({
    queryKey: ["check-ins"],
    queryFn: fetchCheckIns,
    refetchInterval: 30000,
  });
  const sessions = useQuery({ queryKey: ["sessions"], queryFn: fetchSessions });
  const courses = useQuery({ queryKey: ["courses"], queryFn: fetchCourses });

  const visibleCourseIds = useMemo(
    () =>
      new Set(
        (courses.isSuccess ? courses.data : [])
          .filter((course) => course.instructor_id === userId)
          .map((course) => course.id),
      ),
    [courses.data, courses.isSuccess, userId],
  );
  const mySessions = useMemo(
    () => (sessions.data ?? []).filter((session) => visibleCourseIds.has(session.course_id)),
    [sessions.data, visibleCourseIds],
  );
  const visibleSessionIds = useMemo(
    () => new Set(mySessions.map((session) => session.id)),
    [mySessions],
  );
  const visibleCheckIns = useMemo(
    () => (checkIns.data ?? []).filter((item) => visibleSessionIds.has(item.session_id)),
    [checkIns.data, visibleSessionIds],
  );
  const rows = useMemo(() => toRows(visibleCheckIns), [visibleCheckIns]);
  const stats = useMemo(
    () => buildCourseStats(visibleCheckIns, mySessions),
    [visibleCheckIns, mySessions],
  );

  const expected = mySessions.reduce((n, s) => n + (s.expected_attendance ?? 0), 0);
  const approved = rows.filter((r) => r.status === "approved").length;
  const flagged = rows.filter((r) => r.status === "flagged").length;
  const rejected = rows.filter((r) => r.status === "rejected").length;
  const rate = expected > 0 ? Math.round((rows.length / expected) * 100) : 0;
  const avgRisk = rows.length ? Math.round(rows.reduce((s, r) => s + r.risk, 0) / rows.length) : 0;
  const students = new Set(rows.map((r) => r.email)).size;

  const activeSessions = mySessions.filter((s) => s.is_active).length;
  const success = rows.length ? Math.round((approved / rows.length) * 100) : 0;

  return (
    <>
      <Tabs tabs={tabs} value={tab} onChange={setTab} />

      {courses.isError && (
        <p className="mb-4 rounded-xl border border-warning/30 bg-warning/10 p-4 text-sm text-warning">
          Could not load course assignments, so instructor course data is hidden.
        </p>
      )}

      {tab === "overview" && (
        <>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
            <KpiCard
              label="My courses"
              value={String(stats.length)}
              note={`${mySessions.length} sessions (${activeSessions} active) · ${students} students`}
              tone="brand"
              bars={[40, 55, 48, 70, 62, 100]}
            />
            <KpiCard
              label="Check-in rate"
              value={`${rate}%`}
              note={`${rows.length} of ${expected} expected · ${success}% success`}
              tone="accent"
              progress={Math.min(rate, 100)}
            />
            <KpiCard
              label="Flagged items"
              value={String(flagged)}
              note="needs review"
              tone="warning"
              progress={rows.length ? (flagged / rows.length) * 100 : 0}
            />
            <KpiCard
              label="Average risk"
              value={String(avgRisk)}
              note={`${rejected} rejected check-ins`}
              tone={avgRisk > 50 ? "danger" : "accent"}
              progress={avgRisk}
            />
            <CheckInTrend data={trendOf(rows)} approved={approved} flagged={flagged} />
            <StatusPie rows={rows} />
            <LiveActivity rows={rows.slice(0, 4)} />
          </div>
          <CourseAnalytics stats={stats} title="Course analytics" />
        </>
      )}

      {tab === "sessions" && (
        <SessionsPanel rows={rows} canCreate courseIds={visibleCourseIds} currentUserId={userId} selectedCourseId={selectedCourseId} onCourseChange={setSelectedCourseId} />
      )}
      {tab === "checkins" && (
        <CheckInsPanel rows={rows} loading={checkIns.isLoading} courseIds={visibleCourseIds} />
      )}
      {tab === "enrollments" && <EnrollmentsPanel courses={(courses.data ?? []).filter((course) => course.instructor_id === userId)} loading={courses.isLoading} error={courses.isError} selectedCourseId={selectedCourseId} onCourseChange={setSelectedCourseId} canManage />}
      {tab === "audit" && <AuditLogs />}
      {tab === "export" && <ExportPanel courses={(courses.data ?? []).filter(course => course.instructor_id === userId)} loading={courses.isLoading} error={courses.isError} />}
      {tab === "metrics" && <MetricsPanel rows={rows} />}
    </>
  );
}
