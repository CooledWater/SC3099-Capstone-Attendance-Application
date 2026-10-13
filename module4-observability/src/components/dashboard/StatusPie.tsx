import type { CheckInRow } from "./AttendanceTable";

export function StatusPie({ rows, span = "lg:col-span-4" }: { rows: CheckInRow[]; span?: string }) {
  const total = rows.length || 1;
  const segments = [
    { status: "approved", label: "Approved", color: "var(--color-accent)", dot: "bg-accent" },
    { status: "flagged", label: "Flagged", color: "var(--color-warning)", dot: "bg-warning" },
    { status: "pending", label: "Pending", color: "var(--color-primary)", dot: "bg-primary" },
    { status: "appealed", label: "Appealed", color: "var(--color-warning)", dot: "bg-warning" },
    {
      status: "rejected",
      label: "Rejected",
      color: "var(--color-destructive)",
      dot: "bg-destructive",
    },
  ].map((segment) => ({
    ...segment,
    value: rows.filter((row) => row.status === segment.status).length,
  }));

  let position = 0;
  const stops = segments.map((segment) => {
    const start = position;
    position += (segment.value / total) * 100;
    return `${segment.color} ${start}% ${position}%`;
  });
  const gradient = rows.length ? `conic-gradient(${stops.join(", ")})` : "var(--color-secondary)";
  const approvedRate = (rows.filter((row) => row.status === "approved").length / total) * 100;

  return (
    <div className={`animate-rise rounded-2xl border border-border bg-glass p-5 ${span}`}>
      <p className="font-display text-sm font-medium text-card-foreground">Verification status</p>
      <p className="mt-0.5 text-xs text-muted-foreground">{rows.length} records</p>
      <div className="mt-4 flex items-center gap-5">
        <div className="relative size-28 shrink-0 rounded-full" style={{ background: gradient }}>
          <div className="absolute inset-[22%] grid place-items-center rounded-full bg-card">
            <span className="font-display text-lg font-semibold text-card-foreground">
              {Math.round(approvedRate)}%
            </span>
          </div>
        </div>
        <ul className="space-y-2 text-xs">
          {segments.map((l) => (
            <li key={l.label} className="flex items-center gap-2 text-muted-foreground">
              <span className={`size-2 rounded-full ${l.dot}`} />
              {l.label}
              <span className="tabular-nums text-foreground">{l.value}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
