import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchMyAssignedCourses } from "@/lib/attendance";
import { useSessionValue } from "@/hooks/useSessionValue";
import { CheckInsPanel } from "./CheckInsPanel";
import { EnrollmentsPanel } from "./EnrollmentsPanel";
import { SessionsPanel } from "./SessionsPanel";
import { TaOverview } from "./TaOverview";
import { Tabs } from "./Tabs";

const tabs = [
  { id: "overview", label: "Overview" },
  { id: "sessions", label: "Sessions" },
  { id: "checkins", label: "Check-ins" },
  { id: "enrollments", label: "Enrollments" },
] as const;

export function TaView({ userId }: { userId: string }) {
  const [savedTab, setTab] = useSessionValue(`ta:${userId}:tab`, "overview");
  const tab = tabs.find((item) => item.id === savedTab)?.id ?? "overview";
  const [selectedCourseId, setSelectedCourseId] = useSessionValue(`ta:${userId}:course`, "");
  const [selectedSessionId, setSelectedSessionId] = useSessionValue(`ta:${userId}:session`, "");
  const courses = useQuery({
    queryKey: ["ta-assigned-courses", userId],
    queryFn: fetchMyAssignedCourses,
    refetchInterval: 30000,
  });
  const courseIds = useMemo(
    () => new Set(courses.data?.map((course) => course.id) ?? []),
    [courses.data],
  );
  const courseId = courseIds.has(selectedCourseId)
    ? selectedCourseId
    : (courses.data?.[0]?.id ?? "");
  const changeCourse = (id: string) => {
    setSelectedCourseId(id);
    setSelectedSessionId("");
  };
  return (
    <>
      <Tabs tabs={tabs} value={tab} onChange={setTab} />
      {courses.isPending ? (
        <p role="status" className="mt-4 text-sm text-muted-foreground">
          Loading assigned courses...
        </p>
      ) : courses.isError ? (
        <p
          role="alert"
          className="mt-4 rounded-xl border border-destructive/40 p-5 text-sm text-destructive"
        >
          Could not load your TA assignments.{" "}
          <button type="button" className="underline" onClick={() => void courses.refetch()}>
            Retry
          </button>
        </p>
      ) : !courses.data.length ? (
        <p className="mt-4 rounded-xl border border-border p-5 text-sm text-muted-foreground">
          No courses are currently assigned to your TA account.
        </p>
      ) : (
        <>
          {tab === "overview" && (
            <TaOverview
              courses={courses.data}
              courseId={courseId}
              onCourseChange={changeCourse}
              sessionId={selectedSessionId}
              onSessionChange={setSelectedSessionId}
              onOpenSessions={(id) => {
                setSelectedSessionId(id);
                setTab("sessions");
              }}
              onOpenCheckIns={(id) => {
                setSelectedSessionId(id);
                setTab("checkins");
              }}
              userId={userId}
            />
          )}
          {tab === "sessions" && (
            <SessionsPanel
              rows={[]}
              currentUserId={userId}
              canCreate={false}
              readOnly
              assignedCourses={courses.data}
              courseIds={courseIds}
              selectedCourseId={courseId}
              onCourseChange={changeCourse}
              onViewSession={(session) => {
                setSelectedSessionId(session.id);
                setTab("checkins");
              }}
            />
          )}
          {tab === "checkins" && (
            <CheckInsPanel
              rows={[]}
              loading={false}
              courseIds={courseIds}
              instructor={{
                courses: courses.data,
                selectedCourseId: courseId,
                onCourseChange: changeCourse,
                userId,
                initialSessionId: selectedSessionId,
                onSessionChange: setSelectedSessionId,
                canExport: false,
              }}
            />
          )}
          {tab === "enrollments" && (
            <EnrollmentsPanel
              courses={courses.data}
              loading={false}
              error={false}
              selectedCourseId={courseId}
              onCourseChange={changeCourse}
              canManage={false}
              studentDetails={false}
              stateKey={`ta:${userId}:roster`}
            />
          )}
        </>
      )}
    </>
  );
}
