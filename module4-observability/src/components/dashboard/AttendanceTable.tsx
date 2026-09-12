import { useMemo, useState } from "react";
import { checkInsToCsv, downloadCsv, statusText } from "@/lib/attendance";

export type CheckInRow = {
  id: string;
  student: string;
  email: string;
  course: string;
  courseId: string;
  sessionId: string;
  room: string;
  time: string;
  status: "approved" | "flagged" | "no_show";
  risk: number;
  liveness: number;
  faceMatch: number;
  lat: number | null;
  lng: number | null;
};

type SortKey = "student" | "course" | "time" | "status" | "risk";

export const statusStyle: Record<CheckInRow["status"], string> = {
  approved: "bg-accent/10 text-accent",
  flagged: "bg-warning/10 text-warning",
  no_show: "bg-destructive/10 text-destructive",
};

export function AttendanceTable({ rows, loading }: { rows: CheckInRow[]; loading: boolean }) {
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: "time", dir: -1 });
  const [filter, setFilter] = useState<"all" | CheckInRow["status"]>("all");

  const visible = useMemo(() => {
    const list = filter === "all" ? rows : rows.filter((r) => r.status === filter);
    return [...list].sort((a, b) => {
      const { key, dir } = sort;
      if (key === "risk") return (a.risk - b.risk) * dir;
      if (key === "time") return (new Date(a.time).getTime() - new Date(b.time).getTime()) * dir;
      return String(a[key]).localeCompare(String(b[key])) * dir;
    });
  }, [rows, sort, filter]);

  function toggleSort(key: SortKey) {
    setSort((s) => (s.key === key ? { key, dir: s.dir === 1 ? -1 : 1 } : { key, dir: 1 }));
  }

  const headers: { key: SortKey; label: string; align?: string }[] = [
    { key: "student", label: "Student" },
    { key: "course", label: "Course" },
    { key: "time", label: "Check-in" },
    { key: "status", label: "Status" },
    { key: "risk", label: "Risk", align: "text-right" },
  ];

  return (
    <div className="mt-4 animate-rise rounded-2xl border border-border bg-glass">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-5 py-4">
        <div>
          <p className="font-display text-sm font-medium text-card-foreground">Attendance log</p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Click a column to sort · {visible.length} records
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {(["all", "approved", "flagged", "no_show"] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`rounded-full border px-3 py-1.5 text-xs transition ${
                filter === f
                  ? "border-primary/40 bg-primary/15 text-primary"
                  : "border-border bg-glass text-muted-foreground hover:text-foreground"
              }`}
            >
              {f === "all" ? "All" : statusText[f]}
            </button>
          ))}
          <button
            onClick={() => downloadCsv("attendance", checkInsToCsv(visible))}
            className="rounded-full bg-gradient-to-r from-primary to-accent px-3 py-1.5 text-xs font-medium text-primary-foreground transition hover:brightness-110"
          >
            Export CSV
          </button>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[720px] text-left text-sm">
          <thead>
            <tr className="text-[10px] uppercase tracking-wider text-muted-foreground">
              {headers.map((h) => (
                <th key={h.key} className={`px-5 py-3 font-medium ${h.align ?? ""}`}>
                  <button
                    onClick={() => toggleSort(h.key)}
                    className="transition hover:text-foreground"
                  >
                    {h.label} {sort.key === h.key ? (sort.dir === 1 ? "↑" : "↓") : "↕"}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {loading && (
              <tr>
                <td colSpan={5} className="px-5 py-6 text-sm text-muted-foreground">
                  Loading attendance…
                </td>
              </tr>
            )}
            {!loading && visible.length === 0 && (
              <tr>
                <td colSpan={5} className="px-5 py-6 text-sm text-muted-foreground">
                  No records match this filter.
                </td>
              </tr>
            )}
            {visible.map((r) => (
              <tr key={r.id} className="transition-colors hover:bg-secondary/50">
                <td className="px-5 py-3">
                  <span className="font-medium text-foreground">{r.student}</span>
                  <span className="block text-xs text-muted-foreground">{r.email}</span>
                </td>
                <td className="px-5 py-3 text-muted-foreground">
                  {r.course}
                  <span className="block text-xs">{r.room}</span>
                </td>
                <td className="px-5 py-3 text-muted-foreground">
                  {new Date(r.time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                </td>
                <td className="px-5 py-3">
                  <span className={`rounded-full px-2 py-0.5 text-[11px] ${statusStyle[r.status]}`}>
                    {statusText[r.status]}
                  </span>
                </td>
                <td
                  className={`px-5 py-3 text-right tabular-nums ${
                    r.risk > 70
                      ? "text-destructive"
                      : r.risk > 40
                        ? "text-warning"
                        : "text-muted-foreground"
                  }`}
                >
                  {r.risk}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
