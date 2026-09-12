import { useMemo, useState } from "react";
import type { CheckInRow } from "./AttendanceTable";

const statusLabel: Record<CheckInRow["status"], string> = {
  approved: "Approved",
  flagged: "Flagged",
  no_show: "No-show",
};

const statusTone: Record<CheckInRow["status"], string> = {
  approved: "bg-accent/15 text-accent border-accent/25",
  flagged: "bg-warning/15 text-warning border-warning/25",
  no_show: "bg-destructive/15 text-destructive border-destructive/25",
};

export function CourseHistory({ rows }: { rows: CheckInRow[] }) {
  const courses = useMemo(() => [...new Set(rows.map((r) => r.course))].sort(), [rows]);
  const [course, setCourse] = useState<string>("all");

  const filtered = useMemo(
    () =>
      (course === "all" ? rows : rows.filter((r) => r.course === course))
        .slice()
        .sort((a, b) => +new Date(b.time) - +new Date(a.time)),
    [rows, course],
  );

  return (
    <section className="lg:col-span-8 rounded-2xl border border-border bg-card/60 p-5 shadow-[var(--shadow-glass)] backdrop-blur">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="font-display text-base text-foreground">Check-in history</h2>
          <p className="text-xs text-muted-foreground">
            {filtered.length} record{filtered.length === 1 ? "" : "s"}
            {course === "all" ? " across your courses" : ` in ${course}`}
          </p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {["all", ...courses].map((c) => (
            <button
              key={c}
              onClick={() => setCourse(c)}
              className={`rounded-full border px-3 py-1 text-xs transition ${
                course === c
                  ? "border-primary/40 bg-primary/15 text-foreground"
                  : "border-border bg-background/40 text-muted-foreground hover:text-foreground"
              }`}
            >
              {c === "all" ? "All courses" : c}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-4 overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="text-xs uppercase tracking-wide text-muted-foreground">
              <th className="pb-2 font-medium">Course</th>
              <th className="pb-2 font-medium">Checked in</th>
              <th className="pb-2 font-medium">Room</th>
              <th className="pb-2 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((r) => {
              const d = new Date(r.time);
              return (
                <tr key={r.id} className="border-t border-border/60">
                  <td className="py-2.5 pr-3 text-foreground">{r.course}</td>
                  <td className="py-2.5 pr-3 text-muted-foreground">
                    {d.toLocaleDateString(undefined, {
                      day: "2-digit",
                      month: "short",
                      year: "numeric",
                    })}
                    <span className="ml-2 text-foreground/70">
                      {d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}
                    </span>
                  </td>
                  <td className="py-2.5 pr-3 text-muted-foreground">{r.room}</td>
                  <td className="py-2.5">
                    <span
                      className={`rounded-full border px-2 py-0.5 text-xs ${statusTone[r.status]}`}
                    >
                      {statusLabel[r.status]}
                    </span>
                  </td>
                </tr>
              );
            })}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={4} className="py-8 text-center text-sm text-muted-foreground">
                  No check-ins recorded yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
