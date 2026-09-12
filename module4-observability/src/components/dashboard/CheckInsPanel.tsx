import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchSessions, type SessionRow } from "@/lib/attendance";
import { AttendanceTable, type CheckInRow } from "./AttendanceTable";

export function CheckInsPanel({
  rows,
  loading,
  courseIds,
}: {
  rows: CheckInRow[];
  loading: boolean;
  courseIds?: Set<string>;
}) {
  const [sessionId, setSessionId] = useState("all");
  const sessions = useQuery({ queryKey: ["sessions"], queryFn: fetchSessions });

  const list = useMemo(() => {
    const all = (sessions.data ?? []) as SessionRow[];
    return courseIds ? all.filter((s) => courseIds.has(s.course_id)) : all;
  }, [sessions.data, courseIds]);

  const visible = sessionId === "all" ? rows : rows.filter((r) => r.sessionId === sessionId);

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
                {new Date(s.starts_at).toLocaleString([], {
                  month: "short",
                  day: "numeric",
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </option>
            ))}
          </select>
        </label>
      </div>
      <AttendanceTable rows={visible} loading={loading} />
    </div>
  );
}
