import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { EnrollmentsPanel } from "./EnrollmentsPanel";
import { ExportPanel } from "./ExportPanel";
import { SessionsPanel } from "./SessionsPanel";
import { CheckInsPanel } from "./CheckInsPanel";
import { AuditLogs } from "./AuditLogs";
import { MetricsPanel } from "./MetricsPanel";
import { Tabs } from "./Tabs";
import { InstructorOverview } from "./InstructorOverview";
import { useSessionValue } from "@/hooks/useSessionValue";
import { fetchCheckIns, fetchMyAssignedCourses, fetchSessions, toRows } from "@/lib/attendance";
import type { CourseStat } from "./CourseAnalytics";

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

// Kept for the existing admin overview, which shares this small presentation
// aggregate. Instructor Overview uses the course-scoped backend aggregation.
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
  sessions.forEach((session) => {
    const course = ensure(
      session.course_id,
      session.courses?.code ?? "—",
      session.courses?.name ?? "Course",
    );
    course.sessions += 1;
    course.expected += session.expected_attendance ?? 0;
  });
  checkIns.forEach((checkIn) => {
    const session = sessions.find((item) => item.id === checkIn.session_id);
    if (!session) return;
    const course = ensure(
      session.course_id,
      session.courses?.code ?? "—",
      session.courses?.name ?? "Course",
    );
    course.checkIns += 1;
    course.riskSum += checkIn.risk_score;
    if (checkIn.status === "flagged") course.flagged += 1;
  });
  return [...map.values()]
    .map((course) => ({
      ...course,
      avgRisk: course.checkIns ? Math.round(course.riskSum / course.checkIns) : 0,
    }))
    .sort((a, b) => a.code.localeCompare(b.code));
}

export function InstructorView({ userId }: { userId: string }) {
  const [savedTab, setTab] = useSessionValue(`instructor:${userId}:tab`, "overview");
  const tab = tabs.find((item) => item.id === savedTab)?.id ?? "overview";
  const [selectedCourseId, setSelectedCourseId] = useSessionValue(
    `instructor:${userId}:course`,
    "all",
  );
  const [selectedSessionId, setSelectedSessionId] = useState("");
  const [reviewOnly, setReviewOnly] = useState(false);
  const needsCheckInRows = tab === "sessions" || tab === "metrics";
  const needsSessionRows = tab === "sessions" || tab === "metrics";
  const checkIns = useQuery({
    queryKey: ["check-ins", userId],
    queryFn: fetchCheckIns,
    enabled: needsCheckInRows,
    refetchInterval: 30000,
  });
  const sessions = useQuery({
    queryKey: ["sessions", userId],
    queryFn: fetchSessions,
    enabled: needsSessionRows,
  });
  const courses = useQuery({
    queryKey: ["courses", userId],
    queryFn: fetchMyAssignedCourses,
  });
  const visibleCourseIds = useMemo(
    () =>
      new Set(
        (courses.data ?? [])
          .filter((course) => course.instructor_id === userId)
          .map((course) => course.id),
      ),
    [courses.data, userId],
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
  const instructorCourses = (courses.data ?? []).filter(
    (course) => course.instructor_id === userId,
  );
  const activeCourseId =
    selectedCourseId === "all" ? (instructorCourses[0]?.id ?? "") : selectedCourseId;

  return (
    <>
      <Tabs tabs={tabs} value={tab} onChange={setTab} />
      {courses.isError && (
        <p className="mb-4 rounded-xl border border-warning/30 bg-warning/10 p-4 text-sm text-warning">
          Could not load course assignments, so instructor course data is hidden.
        </p>
      )}
      {tab === "overview" && (
        <InstructorOverview
          courses={instructorCourses}
          coursesLoading={courses.isLoading}
          selectedCourseId={activeCourseId}
          onCourseChange={(id) => {
            setSelectedCourseId(id);
            setSelectedSessionId("");
            setReviewOnly(false);
          }}
          onOpenCheckIns={(onlyReview = false, sessionId = "") => {
            setReviewOnly(onlyReview);
            setSelectedSessionId(sessionId);
            setTab("checkins");
          }}
          onOpenSessions={() => {
            setReviewOnly(false);
            setTab("sessions");
          }}
        />
      )}
      {tab === "sessions" && (
        <SessionsPanel
          rows={rows}
          canCreate
          courseIds={visibleCourseIds}
          currentUserId={userId}
          selectedCourseId={selectedCourseId}
          onCourseChange={setSelectedCourseId}
          onViewSession={(session) => {
            setSelectedCourseId(session.course_id);
            setSelectedSessionId(session.id);
            setTab("checkins");
          }}
        />
      )}
      {tab === "checkins" && (
        <CheckInsPanel
          rows={rows}
          loading={checkIns.isLoading}
          courseIds={visibleCourseIds}
          instructor={{
            courses: instructorCourses,
            selectedCourseId: activeCourseId,
            onCourseChange: (id) => {
              setSelectedCourseId(id);
              setSelectedSessionId("");
            },
            userId,
            initialSessionId: selectedSessionId,
            reviewOnly,
          }}
        />
      )}
      {tab === "enrollments" && (
        <EnrollmentsPanel
          courses={instructorCourses}
          loading={courses.isLoading}
          error={courses.isError}
          selectedCourseId={selectedCourseId}
          onCourseChange={setSelectedCourseId}
          canManage
          studentDetails
          stateKey={`instructor:${userId}:roster`}
        />
      )}
      {tab === "audit" && <AuditLogs />}
      {tab === "export" && (
        <ExportPanel
          courses={instructorCourses}
          loading={courses.isLoading}
          error={courses.isError}
        />
      )}
      {tab === "metrics" && <MetricsPanel rows={rows} />}
    </>
  );
}
