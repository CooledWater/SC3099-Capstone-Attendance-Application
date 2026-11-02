import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchSessions, type SessionRow } from "@/lib/attendance";
import { formatSingaporeDateTime } from "@/lib/time";
import { AttendanceTable, type CheckInRow } from "./AttendanceTable";
import { InstructorCheckIns } from "./InstructorCheckIns";
import type { CourseRow } from "@/lib/attendance";

export type CheckInFilter = {
  statuses?: CheckInRow["status"][];
  today?: boolean;
  minRisk?: number;
};

export function CheckInsPanel({
  rows,
  loading,
  courseIds,
  sessionRows,
  instructor,
  initialFilter,
}: {
  rows: CheckInRow[];
  loading: boolean;
  courseIds?: Set<string>;
  sessionRows?: SessionRow[];
  instructor?: {
    courses: CourseRow[];
    selectedCourseId: string;
    onCourseChange: (id: string) => void;
    userId: string;
    initialSessionId?: string;
    onSessionChange?: (sessionId: string) => void;
    reviewOnly?: boolean;
    canExport?: boolean;
  };
  initialFilter?: CheckInFilter;
}) {
  const [sessionId, setSessionId] = useState("all");
  const sessions = useQuery({
    queryKey: ["sessions"],
    queryFn: fetchSessions,
    enabled: sessionRows === undefined && !instructor,
  });

  const list = useMemo(() => {
    const all = sessionRows ?? sessions.data ?? [];
    return courseIds ? all.filter((s) => courseIds.has(s.course_id)) : all;
  }, [sessions.data, sessionRows, courseIds]);

  const visible = useMemo(() => {
    const sessionVisible =
      sessionId === "all" ? rows : rows.filter((r) => r.sessionId === sessionId);
    if (!initialFilter) return sessionVisible;
    const today = new Intl.DateTimeFormat("en-CA", {
      timeZone: "Asia/Singapore",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).format(new Date());
    return sessionVisible.filter((row) => {
      const statusMatches =
        !initialFilter.statuses?.length || initialFilter.statuses.includes(row.status);
      const dateMatches =
        !initialFilter.today ||
        new Intl.DateTimeFormat("en-CA", {
          timeZone: "Asia/Singapore",
          year: "numeric",
          month: "2-digit",
          day: "2-digit",
        }).format(new Date(row.time)) === today;
      const riskMatches = initialFilter.minRisk == null || row.risk >= initialFilter.minRisk;
      return statusMatches && dateMatches && riskMatches;
    });
  }, [initialFilter, rows, sessionId]);

  if (instructor) return <InstructorCheckIns {...instructor} initialFilter={initialFilter ?? {}} />;

  return (
    <div className="mt-4">
      <div className="animate-rise flex flex-wrap items-center gap-3 rounded-2xl border border-border bg-glass px-5 py-4">
        <div className="mr-auto">
          <p className="font-display text-sm font-medium text-card-foreground">Check-ins</p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Live view · refreshes automatically every 30 seconds
          </p>
        </div>
        <label className="text-xs text-muted-foreground">
          Session
          <select
            value={sessionId}
            onChange={(e) => setSessionId(e.target.value)}
            className="ml-2 rounded-lg border border-border bg-secondary/40 px-3 py-2 text-sm text-foreground outline-none focus:border-primary/50"
          >
            <option value="all">All sessions</option>
            {list.map((s) => (
              <option key={s.id} value={s.id}>
                {s.courses?.code ?? "—"} · {s.room} ·{" "}
                {formatSingaporeDateTime(s.starts_at, {
                  month: "short",
                  day: "numeric",
                  hour: "2-digit",
                  minute: "2-digit",
                })}{" "}
                SGT
              </option>
            ))}
          </select>
        </label>
      </div>
      <AttendanceTable key={sessionId} rows={visible} loading={loading} />
    </div>
  );
}
