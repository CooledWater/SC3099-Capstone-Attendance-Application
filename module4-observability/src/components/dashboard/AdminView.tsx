import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { KpiCard } from "./KpiCard";
import { CheckInTrend } from "./CheckInTrend";
import { LiveActivity } from "./LiveActivity";
import { StatusPie } from "./StatusPie";
import { CourseAnalytics } from "./CourseAnalytics";
import { buildCourseStats } from "./InstructorView";
import { EnrollmentsPanel } from "./EnrollmentsPanel";
import { SessionsPanel } from "./SessionsPanel";
import { CheckInsPanel } from "./CheckInsPanel";
import { AuditLogs } from "./AuditLogs";
import { MetricsPanel } from "./MetricsPanel";
import { DeviceApprovals } from "./DeviceApprovals";
import { Tabs } from "./Tabs";
import { fetchCheckIns, fetchCourses, fetchSessions, toRows, trendOf } from "@/lib/attendance";

const tabs = [
  { id: "overview", label: "Overview" },
  { id: "sessions", label: "Sessions" },
  { id: "checkins", label: "Check-ins" },
  { id: "enrollments", label: "Enrollments" },
  { id: "devices", label: "Devices" },
  { id: "audit", label: "Audit logs" },
  { id: "metrics", label: "Metrics" },
] as const;

type Tab = (typeof tabs)[number]["id"];

export function AdminView() {
  const [tab, setTab] = useState<Tab>("overview");
  const [selectedCourseId, setSelectedCourseId] = useState("all");
  const courses = useQuery({ queryKey: ["courses"], queryFn: fetchCourses });
  const checkIns = useQuery({
    queryKey: ["check-ins"],
    queryFn: fetchCheckIns,
    refetchInterval: 30000,
  });
  const sessions = useQuery({ queryKey: ["sessions"], queryFn: fetchSessions });

  const rows = useMemo(() => toRows(checkIns.data ?? []), [checkIns.data]);
  const stats = useMemo(
    () => buildCourseStats(checkIns.data ?? [], sessions.data ?? []),
    [checkIns.data, sessions.data],
  );

  const allSessions = sessions.data ?? [];
  const activeSessions = allSessions.filter((s) => s.is_active).length;
  const expected = allSessions.reduce((n, s) => n + (s.expected_attendance ?? 0), 0);
  const approved = rows.filter((r) => r.status === "approved").length;
  const flagged = rows.filter((r) => r.status === "flagged").length;
  const rejected = rows.filter((r) => r.status === "rejected").length;
  const rate = expected > 0 ? Math.round((rows.length / expected) * 100) : 0;
  const success = rows.length ? Math.round((approved / rows.length) * 100) : 0;
  const students = new Set(rows.map((r) => r.email)).size;
  const avgRisk = rows.length ? Math.round(rows.reduce((s, r) => s + r.risk, 0) / rows.length) : 0;

  return (
    <>
      <Tabs tabs={tabs} value={tab} onChange={setTab} />

      {tab === "overview" && (
        <>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
            <KpiCard
              label="Total sessions"
              value={String(allSessions.length)}
              note={`${activeSessions} active · ${allSessions.length - activeSessions} inactive`}
              tone="brand"
              bars={[45, 58, 52, 74, 66, 100]}
            />
            <KpiCard
              label="Total check-ins"
              value={String(rows.length)}
              note={`${success}% success rate · ${students} students`}
              tone="accent"
              progress={success}
            />
            <KpiCard
              label="Platform check-in rate"
              value={`${rate}%`}
              note={`${rows.length} of ${expected} expected`}
              tone={rate < 60 ? "warning" : "accent"}
              progress={Math.min(rate, 100)}
            />
            <KpiCard
              label="Integrity signals"
              value={String(flagged)}
              note={`${rejected} rejected · avg risk ${avgRisk}`}
              tone={flagged > 0 ? "danger" : "accent"}
              progress={rows.length ? (flagged / rows.length) * 100 : 0}
            />
            <CheckInTrend data={trendOf(rows)} approved={approved} flagged={flagged} />
            <StatusPie rows={rows} />
            <LiveActivity rows={rows.slice(0, 4)} />
          </div>
          <CourseAnalytics stats={stats} title="System-wide course analytics" />
        </>
      )}

      {tab === "sessions" && <SessionsPanel rows={rows} canCreate selectedCourseId={selectedCourseId} onCourseChange={setSelectedCourseId} />}
      {tab === "devices" && <DeviceApprovals />}
      {tab === "checkins" && <CheckInsPanel rows={rows} loading={checkIns.isLoading} />}
      {tab === "enrollments" && <EnrollmentsPanel courses={courses.data ?? []} loading={courses.isLoading} error={courses.isError} selectedCourseId={selectedCourseId} onCourseChange={setSelectedCourseId} canManage />}
      {tab === "audit" && <AuditLogs />}
      {tab === "metrics" && <MetricsPanel rows={rows} />}
    </>
  );
}
