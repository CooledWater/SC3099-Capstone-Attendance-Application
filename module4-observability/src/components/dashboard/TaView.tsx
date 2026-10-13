import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  fetchCheckInsForSessions,
  fetchMyAssignedCourses,
  fetchSessionsForCourses,
  toRows,
} from "@/lib/attendance";
import { CheckInsPanel } from "./CheckInsPanel";

export function TaView({ userId }: { userId: string }) {
  const courses = useQuery({
    queryKey: ["ta-assigned-courses", userId],
    queryFn: fetchMyAssignedCourses,
  });
  const courseIds = useMemo(
    () => (courses.isSuccess ? courses.data.map((course) => course.id) : []),
    [courses.data, courses.isSuccess],
  );
  const sessions = useQuery({
    queryKey: ["ta-sessions", userId, courseIds],
    queryFn: () => fetchSessionsForCourses(courseIds),
    enabled: courses.isSuccess,
  });
  const checkIns = useQuery({
    queryKey: ["ta-check-ins", userId, sessions.data?.map((session) => session.id) ?? []],
    queryFn: () => fetchCheckInsForSessions(sessions.data ?? []),
    enabled: sessions.isSuccess,
    refetchInterval: 30000,
  });
  const rows = useMemo(() => toRows(checkIns.data ?? []), [checkIns.data]);

  return (
    <div className="rounded-2xl border border-border bg-glass p-5">
      <div>
        <p className="font-display text-sm font-medium text-card-foreground">
          Teaching assistant console
        </p>
        <p className="mt-1 text-xs text-muted-foreground">
          Sessions and attendance are limited to courses assigned to your TA account.
        </p>
      </div>
      {courses.isLoading && (
        <p className="mt-4 text-sm text-muted-foreground">Loading your assigned courses…</p>
      )}
      {courses.isError && (
        <p className="mt-4 rounded-xl border border-warning/30 bg-warning/10 p-4 text-sm text-warning">
          Could not load your course assignments. The TA assignment API may not be available yet.
        </p>
      )}
      {courses.isSuccess && courseIds.length === 0 && (
        <p className="mt-4 text-sm text-muted-foreground">
          No courses are currently assigned to your TA account.
        </p>
      )}
      {courses.isSuccess && courseIds.length > 0 && sessions.isLoading && (
        <p className="mt-4 text-sm text-muted-foreground">Loading sessions for your courses…</p>
      )}
      {sessions.isError && (
        <p className="mt-4 rounded-xl border border-warning/30 bg-warning/10 p-4 text-sm text-warning">
          Could not load sessions for your assigned courses.
        </p>
      )}
      {sessions.isSuccess && sessions.data.length === 0 && (
        <p className="mt-4 text-sm text-muted-foreground">
          No sessions are available for your assigned courses.
        </p>
      )}
      {sessions.isSuccess && sessions.data.length > 0 && checkIns.isError && (
        <p className="mt-4 rounded-xl border border-warning/30 bg-warning/10 p-4 text-sm text-warning">
          Could not load check-ins for your assigned sessions.
        </p>
      )}
      {sessions.isSuccess && sessions.data.length > 0 && !checkIns.isError && (
        <CheckInsPanel
          rows={rows}
          loading={checkIns.isLoading}
          courseIds={new Set(courseIds)}
          sessionRows={sessions.data}
        />
      )}
    </div>
  );
}
