import type { CheckInRow } from "./AttendanceTable";

export function StatusPie({ rows, span = "lg:col-span-4" }: { rows: CheckInRow[]; span?: string }) {
  const total = rows.length || 1;
  const approved = rows.filter((r) => r.status === "approved").length;
  const flagged = rows.filter((r) => r.status === "flagged").length;
  const noShow = rows.filter((r) => r.status === "no_show").length;

  const a = (approved / total) * 100;
  const f = (flagged / total) * 100;

  const gradient = `conic-gradient(var(--color-accent) 0 ${a}%, var(--color-warning) ${a}% ${a + f}%, var(--color-destructive) ${a + f}% 100%)`;

  const legend = [
    { label: "Approved", value: approved, dot: "bg-accent" },
    { label: "Flagged", value: flagged, dot: "bg-warning" },
    { label: "No-show", value: noShow, dot: "bg-destructive" },
  ];

  return (
    <div className={`animate-rise rounded-2xl border border-border bg-glass p-5 ${span}`}>
      <p className="font-display text-sm font-medium text-card-foreground">Verification status</p>
      <p className="mt-0.5 text-xs text-muted-foreground">{rows.length} records</p>
      <div className="mt-4 flex items-center gap-5">
        <div className="relative size-28 shrink-0 rounded-full" style={{ background: gradient }}>
          <div className="absolute inset-[22%] grid place-items-center rounded-full bg-card">
            <span className="font-display text-lg font-semibold text-card-foreground">
              {Math.round(a)}%
            </span>
          </div>
        </div>
        <ul className="space-y-2 text-xs">
          {legend.map((l) => (
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
