import type { CheckInRow } from "./AttendanceTable";
import { formatSingaporeDateTime, parseApiDateTime } from "@/lib/time";

const statusLabel: Record<CheckInRow["status"], string> = {
  approved: "checked in",
  flagged: "was flagged",
  rejected: "was rejected",
  pending: "is pending review",
  appealed: "was appealed",
};

const statusColor: Record<CheckInRow["status"], string> = {
  approved: "text-accent",
  flagged: "text-warning",
  rejected: "text-destructive",
  pending: "text-primary",
  appealed: "text-warning",
};

export function LiveActivity({ rows, student = false }: { rows: CheckInRow[]; student?: boolean }) {
  const rejectedAppeal = (row: CheckInRow) => row.status === "rejected" && !!row.appealedAt && !!row.reviewedAt;
  const activityTime = (row: CheckInRow) => rejectedAppeal(row) ? row.reviewedAt! : row.status === "appealed" ? row.appealedAt ?? row.time : row.time;
  const activities = student
    ? [...rows].sort((a, b) => parseApiDateTime(activityTime(b)).getTime() - parseApiDateTime(activityTime(a)).getTime()).slice(0, 4)
    : rows;
  function studentMessage(row: CheckInRow) {
    const session = `${row.course}, ${row.sessionName ?? "Unnamed session"}`;
    if (rejectedAppeal(row)) return `Your appeal was rejected for ${session}`;
    if (row.status === "appealed") return `You submitted an appeal for ${session}`;
    if (row.status === "approved") return `You checked in for ${session}`;
    if (row.status === "flagged") return `Your check-in for ${session} was flagged for review`;
    if (row.status === "rejected") return `Your check-in for ${session} was rejected`;
    return `Your check-in for ${session} is pending verification`;
  }
  return (
    <div className="animate-rise rounded-2xl border border-border bg-glass p-5 lg:col-span-4">
      <p className="mb-4 font-display text-sm font-medium text-card-foreground">Live activity</p>
      <div className="space-y-4">
        {rows.length === 0 && (
          <p className="text-sm text-muted-foreground">Nothing has happened yet today.</p>
        )}
        {activities.map((r) => (
          <div key={r.id} className="flex items-start gap-3">
            <div className="grid size-9 shrink-0 place-items-center rounded-full bg-secondary font-display text-xs text-muted-foreground">
              {r.student
                .split(" ")
                .map((p) => p[0])
                .join("")
                .slice(0, 2)}
            </div>
            <div>
              <p className="text-sm text-foreground">
                {student ? studentMessage(r) : <>{r.student} <span className={statusColor[r.status]}>{statusLabel[r.status]}</span></>}
              </p>
              <p className="text-xs text-muted-foreground">
                {formatSingaporeDateTime(student ? activityTime(r) : r.time, { hour: "numeric", minute: "2-digit", hour12: true })}
                {!student && <> SGT · {r.course}</>}
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
