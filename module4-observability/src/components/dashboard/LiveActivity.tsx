import type { CheckInRow } from "./AttendanceTable";

const statusLabel: Record<CheckInRow["status"], string> = {
  approved: "checked in",
  flagged: "was flagged",
  no_show: "did not attend",
};

const statusColor: Record<CheckInRow["status"], string> = {
  approved: "text-accent",
  flagged: "text-warning",
  no_show: "text-destructive",
};

export function LiveActivity({ rows }: { rows: CheckInRow[] }) {
  return (
    <div className="animate-rise rounded-2xl border border-border bg-glass p-5 lg:col-span-4">
      <p className="mb-4 font-display text-sm font-medium text-card-foreground">Live activity</p>
      <div className="space-y-4">
        {rows.length === 0 && (
          <p className="text-sm text-muted-foreground">Nothing has happened yet today.</p>
        )}
        {rows.map((r) => (
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
                {r.student} <span className={statusColor[r.status]}>{statusLabel[r.status]}</span>
              </p>
              <p className="text-xs text-muted-foreground">
                {new Date(r.time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} ·{" "}
                {r.course}
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
