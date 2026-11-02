import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { KpiCard } from "./KpiCard";
import { CourseAnalytics } from "./CourseAnalytics";
import { buildCourseStats } from "./InstructorView";
import { EnrollmentsPanel } from "./EnrollmentsPanel";
import { SessionsPanel } from "./SessionsPanel";
import { CheckInsPanel, type CheckInFilter } from "./CheckInsPanel";
import { AuditLogs } from "./AuditLogs";
import { MetricsPanel } from "./MetricsPanel";
import { DeviceApprovals } from "./DeviceApprovals";
import { Tabs } from "./Tabs";
import { AdminCourses } from "./AdminCourses";
import { AdminUsers } from "./AdminUsers";
import { ExportPanel } from "./ExportPanel";
import { useSessionValue } from "@/hooks/useSessionValue";
import {
  fetchAdminOverview,
  fetchCheckIns,
  fetchCourses,
  fetchSessions,
  toRows,
} from "@/lib/attendance";
import { fetchPendingDeviceCount } from "@/lib/admin";
import { AdminCheckIns } from "./AdminCheckIns";
import { AdminOverviewCharts } from "./AdminOverviewCharts";

const tabs = [
  { id: "overview", label: "Overview" },
  { id: "sessions", label: "Sessions" },
  { id: "checkins", label: "Check-ins" },
  { id: "enrollments", label: "Enrollments" },
  { id: "devices", label: "Devices" },
  { id: "courses", label: "Courses & staff" },
  { id: "users", label: "Users" },
  { id: "export", label: "Export" },
  { id: "audit", label: "Audit logs" },
  { id: "metrics", label: "Metrics" },
] as const;
type Tab = (typeof tabs)[number]["id"];

export function AdminView({ userId }: { userId: string }) {
  const [savedTab, setTab] = useSessionValue(`admin:${userId}:tab`, "overview");
  const tab: Tab = tabs.find((item) => item.id === savedTab)?.id ?? "overview";
  const [selectedCourseId, setSelectedCourseId] = useSessionValue(`admin:${userId}:course`, "all");
  const [selectedSessionId, setSelectedSessionId] = useState("");
  const [initialReviewOnly, setInitialReviewOnly] = useState(false);
  const [checkinFilter, setCheckinFilter] = useState<CheckInFilter | undefined>();
  const [sessionStatusFilter, setSessionStatusFilter] = useState<"all" | "active">("all");
  const [deviceActiveFilter, setDeviceActiveFilter] = useState("all");
  const [deviceTrustedFilter, setDeviceTrustedFilter] = useState("all");
  const courses = useQuery({ queryKey: ["courses", userId], queryFn: fetchCourses });
  const checkIns = useQuery({
    queryKey: ["check-ins", userId],
    queryFn: fetchCheckIns,
    enabled:
      ["overview", "sessions", "metrics"].includes(tab) ||
      (tab === "checkins" && checkinFilter !== undefined),
    refetchInterval: 30000,
  });
  const sessions = useQuery({
    queryKey: ["sessions", userId],
    queryFn: fetchSessions,
    enabled:
      ["overview", "sessions", "metrics"].includes(tab) ||
      (tab === "checkins" && checkinFilter !== undefined),
  });
  const overview = useQuery({
    queryKey: ["admin-overview", userId],
    queryFn: ({ signal }) => fetchAdminOverview(30, signal),
    enabled: tab === "overview",
    refetchInterval: 30000,
  });
  const pendingDevices = useQuery({
    queryKey: ["admin-device-approval-count", userId],
    queryFn: ({ signal }) => fetchPendingDeviceCount(signal),
    enabled: tab === "overview",
    refetchInterval: 30000,
  });
  const activeCourseId =
    courses.data?.find((course) => course.id === selectedCourseId)?.id ??
    courses.data?.[0]?.id ??
    "";
  const rows = useMemo(() => toRows(checkIns.data ?? []), [checkIns.data]);
  const stats = useMemo(
    () => buildCourseStats(checkIns.data ?? [], sessions.data ?? []),
    [checkIns.data, sessions.data],
  );
  const allSessions = sessions.data ?? [];
  const activeSessions =
    overview.data?.active_sessions ?? allSessions.filter((s) => s.is_active).length;
  const approved = rows.filter((r) => r.status === "approved").length;
  const flagged = rows.filter((r) => r.status === "flagged").length;
  const highRiskThreshold = overview.data?.high_risk_threshold ?? 0.5;
  const highRisk = rows.filter((r) => r.risk >= highRiskThreshold);
  const success =
    overview.data?.approval_rate != null
      ? Math.round(overview.data.approval_rate * 100)
      : rows.length
        ? Math.round((approved / rows.length) * 100)
        : 0;
  const flaggedCount = overview.data?.flagged_count ?? flagged;
  const appealedCount =
    overview.data?.appealed_count ?? rows.filter((r) => r.status === "appealed").length;
  const todayCheckins = overview.data?.total_checkins_today;
  const highRiskToday = overview.data?.high_risk_checkins_today ?? highRisk.length;
  const pendingDeviceCount = pendingDevices.data?.total ?? 0;
  function openCheckins(filter: CheckInFilter) {
    setSelectedSessionId("");
    setCheckinFilter(filter);
    setTab("checkins");
  }

  return (
    <>
      <Tabs
        tabs={tabs}
        value={tab}
        onChange={(id) => {
          setCheckinFilter(undefined);
          setInitialReviewOnly(false);
          setTab(id);
        }}
      />
      {courses.isError && (
        <p role="alert" className="mb-4 text-destructive">
          Could not load courses.{" "}
          <button className="underline" onClick={() => void courses.refetch()}>
            Retry
          </button>
        </p>
      )}
      {tab === "overview" && (
        <>
          {overview.isError && (
            <p role="alert" className="mb-4 text-destructive">
              Could not refresh overview statistics.{" "}
              <button className="underline" onClick={() => void overview.refetch()}>
                Retry
              </button>
            </p>
          )}
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            <KpiCard
              label="Active sessions"
              value={String(activeSessions)}
              note="Across all courses"
              scope="Active now"
              tone="brand"
              className="xl:col-span-1"
              onClick={() => {
                setSessionStatusFilter("active");
                setTab("sessions");
              }}
            />
            <KpiCard
              label="Check-ins today"
              value={todayCheckins == null ? "—" : String(todayCheckins)}
              note={
                todayCheckins != null
                  ? "Across all courses · All statuses"
                  : overview.isError
                    ? "Today's total unavailable"
                    : "Loading today's total…"
              }
              scope="Today"
              tone="accent"
              className="xl:col-span-1"
              progress={success}
              onClick={() => openCheckins({ today: true })}
            />
            <KpiCard
              label="Needs review"
              value={String(flaggedCount + appealedCount)}
              note={`${flaggedCount} flagged · ${appealedCount} appealed`}
              scope="Outstanding"
              tone="danger"
              className="xl:col-span-1"
              onClick={() => openCheckins({ statuses: ["flagged", "appealed"] })}
            />
            <KpiCard
              label="High-risk check-ins"
              value={String(highRiskToday)}
              note="Configured risk threshold"
              scope="Today"
              tone="warning"
              className="xl:col-span-1"
              onClick={() => openCheckins({ today: true, minRisk: highRiskThreshold })}
            />
            <KpiCard
              label="Devices awaiting approval"
              value={String(pendingDeviceCount)}
              note="Admin action required"
              scope="Outstanding"
              tone="brand"
              className="xl:col-span-1"
              onClick={() => {
                setDeviceActiveFilter("true");
                setDeviceTrustedFilter("false");
                setTab("devices");
              }}
            />
          </div>
          <AdminOverviewCharts
            key={overview.data?.timezone ?? "Asia/Singapore"}
            userId={userId}
            timezone={overview.data?.timezone ?? "Asia/Singapore"}
            onOpenCheckIns={(courseId, reviewOnly, sessionId) => {
              setSelectedCourseId(courseId);
              setSelectedSessionId(sessionId);
              setInitialReviewOnly(reviewOnly);
              setCheckinFilter(undefined);
              setTab("checkins");
            }}
            onOpenSessions={(courseId) => {
              setSelectedCourseId(courseId);
              setSessionStatusFilter("all");
              setTab("sessions");
            }}
          />
          <CourseAnalytics stats={stats} title="System-wide course analytics" />
          <div className="mt-4 animate-rise rounded-2xl border border-border bg-glass p-5">
            <p className="font-display text-sm font-medium text-card-foreground">
              High-risk alerts
            </p>
            <ul className="mt-3 space-y-2">
              {highRisk.slice(0, 8).map((r) => (
                <li
                  key={r.id}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-destructive/20 bg-destructive/5 px-4 py-2.5 text-xs"
                >
                  <span className="text-foreground">
                    {r.student} · {r.course}
                  </span>
                  <span className="text-muted-foreground">
                    liveness {r.liveness.toFixed(2)} · face match {r.faceMatch.toFixed(2)}
                  </span>
                  <span className="tabular-nums text-destructive">risk {r.risk.toFixed(2)}</span>
                </li>
              ))}
              {highRisk.length === 0 && (
                <li className="text-xs text-muted-foreground">No high-risk check-ins right now.</li>
              )}
            </ul>
          </div>
        </>
      )}
      {tab === "sessions" && (
        <SessionsPanel
          rows={rows}
          canCreate
          isAdmin
          currentUserId={userId}
          assignedCourses={courses.data ?? []}
          selectedCourseId={selectedCourseId}
          initialStatus={sessionStatusFilter}
          onCourseChange={setSelectedCourseId}
          onViewSession={(session) => {
            setInitialReviewOnly(false);
            setCheckinFilter(undefined);
            setSelectedCourseId(session.course_id);
            setSelectedSessionId(session.id);
            setTab("checkins");
          }}
        />
      )}
      {tab === "devices" && (
        <DeviceApprovals
          userId={userId}
          initialActive={deviceActiveFilter}
          initialTrusted={deviceTrustedFilter}
        />
      )}
      {tab === "checkins" &&
        (courses.isPending ? (
          <p role="status">Loading courses…</p>
        ) : (
          !courses.isError &&
          (checkinFilter ? (
            <AdminCheckIns
              key={JSON.stringify(checkinFilter)}
              courses={courses.data ?? []}
              sessions={sessions.data ?? []}
              checkIns={checkIns.data ?? []}
              userId={userId}
              initialFilter={checkinFilter}
              loading={checkIns.isPending || sessions.isPending}
              error={checkIns.isError || sessions.isError}
              onRetry={() => {
                void checkIns.refetch();
                void sessions.refetch();
              }}
            />
          ) : (
            <CheckInsPanel
              rows={rows}
              loading={false}
              instructor={{
                courses: courses.data ?? [],
                selectedCourseId: activeCourseId,
                onCourseChange: (id) => {
                  setSelectedCourseId(id);
                  setSelectedSessionId("");
                },
                userId,
                reviewOnly: initialReviewOnly,
                initialSessionId: selectedSessionId,
                onSessionChange: setSelectedSessionId,
              }}
            />
          ))
        ))}
      {tab === "enrollments" && (
        <EnrollmentsPanel
          courses={courses.data ?? []}
          loading={courses.isLoading}
          error={courses.isError}
          selectedCourseId={selectedCourseId}
          onCourseChange={setSelectedCourseId}
          canManage
          studentDetails
          stateKey={`admin:${userId}:roster`}
        />
      )}
      {tab === "courses" && <AdminCourses userId={userId} />}
      {tab === "users" && <AdminUsers userId={userId} />}
      {tab === "export" && (
        <ExportPanel
          courses={courses.data ?? []}
          loading={courses.isPending}
          error={courses.isError}
        />
      )}
      {tab === "audit" && <AuditLogs />}
      {tab === "metrics" && <MetricsPanel showGrafanaLink />}
    </>
  );
}
