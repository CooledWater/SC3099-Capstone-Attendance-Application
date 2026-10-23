import { useMemo, useState } from "react";
import { checkInsToCsv, downloadCsv, statusText } from "@/lib/attendance";
import { formatSingaporeDateTime } from "@/lib/time";
import {
  attendanceLabels,
  filterRoster,
  type Attendance,
  type RosterEntry,
} from "@/lib/checkin-roster";

export type CheckInRow = {
  id: string;
  student: string;
  email: string;
  course: string;
  courseId: string;
  sessionId: string;
  sessionName?: string;
  room: string;
  time: string;
  status: "approved" | "flagged" | "rejected" | "pending" | "appealed";
  risk: number;
  riskScore?: number;
  appealedAt?: string | null;
  reviewedAt?: string | null;
  liveness: number;
  faceMatch: number;
  lat: number | null;
  lng: number | null;
};

type SortKey = "student" | "course" | "time" | "status" | "risk";

export const statusStyle: Record<CheckInRow["status"], string> = {
  approved: "bg-accent/10 text-accent",
  flagged: "bg-warning/10 text-warning",
  rejected: "bg-destructive/10 text-destructive",
  pending: "bg-primary/10 text-primary",
  appealed: "bg-warning/10 text-warning",
};

export function AttendanceTable({ rows, loading }: { rows: CheckInRow[]; loading: boolean }) {
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: "time", dir: -1 });
  const [filter, setFilter] = useState<"all" | CheckInRow["status"]>("all");
  const [page, setPage] = useState(1);
  const pageSize = 50;

  const visible = useMemo(() => {
    const list = filter === "all" ? rows : rows.filter((r) => r.status === filter);
    return [...list].sort((a, b) => {
      const { key, dir } = sort;
      if (key === "risk") return (a.risk - b.risk) * dir;
      if (key === "time") return (new Date(a.time).getTime() - new Date(b.time).getTime()) * dir;
      return String(a[key]).localeCompare(String(b[key])) * dir;
    });
  }, [rows, sort, filter]);
  const pageCount = Math.max(1, Math.ceil(visible.length / pageSize));
  const currentPage = Math.min(page, pageCount);
  const firstIndex = (currentPage - 1) * pageSize;
  const pageRows = visible.slice(firstIndex, firstIndex + pageSize);

  function toggleSort(key: SortKey) {
    setPage(1);
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
          {(["all", "approved", "flagged", "pending", "appealed", "rejected"] as const).map((f) => (
            <button
              key={f}
              onClick={() => {
                setFilter(f);
                setPage(1);
              }}
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
            {!loading &&
              pageRows.map((r) => (
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
                    {formatSingaporeDateTime(r.time, { hour: "2-digit", minute: "2-digit" })} SGT
                  </td>
                  <td className="px-5 py-3">
                    <span
                      className={`rounded-full px-2 py-0.5 text-[11px] ${statusStyle[r.status]}`}
                    >
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
      <nav
        aria-label="Attendance pagination"
        className="flex flex-wrap items-center justify-between gap-3 border-t border-border px-5 py-4 text-xs text-muted-foreground"
      >
        <p aria-live="polite">
          {loading
            ? "Loading records…"
            : `Showing ${visible.length ? firstIndex + 1 : 0}–${Math.min(firstIndex + pageSize, visible.length)} of ${visible.length} records`}
        </p>
        <div className="flex items-center gap-3">
          <button
            className="rounded-lg border border-border px-3 py-2 disabled:opacity-40"
            disabled={loading || currentPage === 1}
            onClick={() => setPage(currentPage - 1)}
          >
            Previous
          </button>
          <span>
            Page {currentPage} of {pageCount}
          </span>
          <button
            className="rounded-lg border border-border px-3 py-2 disabled:opacity-40"
            disabled={loading || currentPage === pageCount}
            onClick={() => setPage(currentPage + 1)}
          >
            Next
          </button>
        </div>
      </nav>
    </div>
  );
}

const rosterVerification = { ...statusText, none: "No check-in" };
const rosterBadge: Record<CheckInRow["status"], string> = {
  ...statusStyle,
  approved: "bg-emerald-400/15 text-emerald-300",
  flagged: "bg-rose-400/20 text-rose-300",
  appealed: "bg-rose-400/20 text-rose-300",
};

export function VerificationBadge({ status }: { status: CheckInRow["status"] | null }) {
  return (
    <span
      className={`inline-flex rounded-full px-2 py-1 text-xs ${status ? rosterBadge[status] : "bg-secondary text-muted-foreground"}`}
    >
      {status ? statusText[status] : "—"}
    </span>
  );
}

export function AttendanceRoster({
  rows,
  loading,
  error,
  verification,
  onVerificationChange,
  flaggedIds,
  onSelect,
  onExport,
  exporting,
}: {
  rows: RosterEntry[];
  loading: boolean;
  error: string | null;
  verification: string[];
  onVerificationChange: (value: string[]) => void;
  flaggedIds: Set<string> | undefined;
  onSelect: (entry: RosterEntry) => void;
  onExport: () => void;
  exporting: boolean;
}) {
  const [search, setSearch] = useState("");
  const [attendance, setAttendance] = useState("all");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [sort, setSort] = useState<{
    key: "student_name" | "attendance" | "checked_in_at" | "status" | "risk_score";
    dir: 1 | -1;
  }>({ key: "checked_in_at", dir: -1 });
  const signature = JSON.stringify([search, attendance, verification, sort]);
  const [pagination, setPagination] = useState({ signature, page: 1 });
  const pageSize = 10;
  const filtered = useMemo(
    () =>
      filterRoster(rows, search, attendance, verification, flaggedIds).sort((a, b) => {
        if (sort.key === "risk_score") {
          if (a.risk_score == null) return b.risk_score == null ? 0 : 1;
          if (b.risk_score == null) return -1;
          return (a.risk_score - b.risk_score) * sort.dir;
        }
        if (sort.key === "checked_in_at") {
          if (!a.checked_in_at) return b.checked_in_at ? 1 : 0;
          if (!b.checked_in_at) return -1;
          return (Date.parse(a.checked_in_at) - Date.parse(b.checked_in_at)) * sort.dir;
        }
        return String(a[sort.key] ?? "").localeCompare(String(b[sort.key] ?? "")) * sort.dir;
      }),
    [rows, search, attendance, verification, flaggedIds, sort],
  );
  const pages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const page = pagination.signature === signature ? Math.min(pagination.page, pages) : 1;
  const start = (page - 1) * pageSize;
  const count = Number(attendance !== "all") + Number(verification.length > 0);
  const control =
    "rounded-lg border border-border bg-secondary/40 px-3 py-2.5 text-xs text-foreground outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:opacity-40";
  function clear() {
    setAttendance("all");
    onVerificationChange([]);
    setSearch("");
  }
  return (
    <section
      className="rounded-2xl border border-border bg-glass p-4 sm:p-5"
      aria-label="Attendance roster"
    >
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h3 className="font-display text-sm font-semibold text-card-foreground">
          Attendance roster
        </h3>
        <button
          type="button"
          className="rounded-full bg-gradient-to-r from-violet-500 to-emerald-400 px-5 py-2 text-sm font-semibold text-white transition hover:brightness-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:opacity-50"
          disabled={exporting}
          onClick={onExport}
          aria-label="Export CSV for selected session"
        >
          {exporting ? "Exporting…" : "Export CSV"}
        </button>
      </div>
      <div className="flex gap-2">
        <input
          aria-label="Search student name or email"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search student name or email"
          className={`${control} min-w-0 flex-1`}
        />
        <button
          type="button"
          className={control}
          aria-expanded={filtersOpen}
          aria-controls="attendance-roster-filters"
          onClick={() => setFiltersOpen(!filtersOpen)}
        >
          Filters{count ? ` (${count})` : ""}
        </button>
      </div>
      {filtersOpen && (
        <div
          id="attendance-roster-filters"
          className="mt-3 grid items-start gap-4 rounded-xl bg-secondary/20 p-3 sm:grid-cols-2"
        >
          <label className="grid content-start gap-2 text-xs text-muted-foreground">
            Attendance status
            <select
              className={`${control} h-11 w-full`}
              value={attendance}
              onChange={(event) => setAttendance(event.target.value)}
            >
              <option value="all">All attendance</option>
              {Object.entries(attendanceLabels).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <fieldset className="min-w-0 text-xs text-muted-foreground">
            <legend className="mb-2">Verification status</legend>
            <div className="grid grid-cols-2 gap-2 rounded-lg border border-border bg-secondary/40 p-3">
              <label className="col-span-2 flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={!verification.length}
                  onChange={() => onVerificationChange([])}
                  className="accent-primary"
                />{" "}
                All verification
              </label>
              {Object.entries(rosterVerification).map(([value, label]) => (
                <label key={value} className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={verification.includes(value)}
                    onChange={() =>
                      onVerificationChange(
                        verification.includes(value)
                          ? verification.filter((item) => item !== value)
                          : [...verification, value],
                      )
                    }
                    className="accent-primary"
                  />
                  {label}
                </label>
              ))}
            </div>
          </fieldset>
        </div>
      )}
      {(count > 0 || search) && (
        <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
          {attendance !== "all" && (
            <button
              className="rounded-full bg-primary/10 px-2.5 py-1 text-primary"
              onClick={() => setAttendance("all")}
              aria-label="Remove attendance filter"
            >
              {attendanceLabels[attendance as Attendance]} ×
            </button>
          )}
          {verification.map((value) => (
            <button
              key={value}
              className="rounded-full bg-primary/10 px-2.5 py-1 text-primary"
              onClick={() => onVerificationChange(verification.filter((item) => item !== value))}
              aria-label={`Remove ${rosterVerification[value as keyof typeof rosterVerification]} filter`}
            >
              {rosterVerification[value as keyof typeof rosterVerification]} ×
            </button>
          ))}
          {search && (
            <button
              className="rounded-full bg-primary/10 px-2.5 py-1 text-primary"
              onClick={() => setSearch("")}
              aria-label="Remove search"
            >
              Search: {search} ×
            </button>
          )}
          <button
            className="px-2 py-1 text-primary underline-offset-4 hover:underline"
            onClick={clear}
          >
            Clear all
          </button>
        </div>
      )}
      <div className="mt-4 overflow-x-auto">
        <table className="w-full min-w-[600px] text-left text-xs">
          <thead>
            <tr className="border-b border-border text-muted-foreground">
              {(
                [
                  ["student_name", "Student"],
                  ["attendance", "Attendance"],
                  ["checked_in_at", "Check-in"],
                  ["status", "Verification"],
                  ["risk_score", "Risk"],
                ] as const
              ).map(([key, label]) => (
                <th
                  key={key}
                  scope="col"
                  aria-sort={
                    sort.key === key ? (sort.dir === 1 ? "ascending" : "descending") : "none"
                  }
                  className="px-2 py-4 font-normal"
                >
                  <button
                    className="rounded hover:text-foreground focus-visible:ring-2 focus-visible:ring-primary"
                    onClick={() =>
                      setSort({ key, dir: sort.key === key && sort.dir === 1 ? -1 : 1 })
                    }
                  >
                    {label} {sort.key === key ? (sort.dir === 1 ? "↑" : "↓") : "↕"}
                  </button>
                </th>
              ))}
              <th scope="col" className="px-2 py-4 font-normal">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {(loading || error || !filtered.length) && (
              <tr>
                <td
                  colSpan={6}
                  className="px-2 py-8 text-muted-foreground"
                  role={error ? "alert" : "status"}
                >
                  {error ??
                    (loading
                      ? "Loading attendance…"
                      : "No students match your search and filters.")}
                </td>
              </tr>
            )}
            {!loading &&
              !error &&
              filtered.slice(start, start + pageSize).map((row) => (
                <tr key={row.student_id} className="hover:bg-secondary/20">
                  <td className="px-2 py-4">
                    <span className="font-medium text-foreground">{row.student_name}</span>
                    <span className="mt-1 block text-muted-foreground">{row.student_email}</span>
                  </td>
                  <td className="px-2 py-4">{attendanceLabels[row.attendance]}</td>
                  <td className="px-2 py-4 tabular-nums">
                    {row.checked_in_at
                      ? formatSingaporeDateTime(row.checked_in_at, {
                          hour: "numeric",
                          minute: "2-digit",
                          hour12: true,
                        })
                      : "—"}
                  </td>
                  <td className="px-2 py-4">
                    <VerificationBadge status={row.status} />
                  </td>
                  <td className="px-2 py-4 tabular-nums">{row.risk_score ?? "—"}</td>
                  <td className="px-2 py-4">
                    {row.checkin_id ? (
                      <button
                        className="rounded text-primary underline-offset-4 hover:underline focus-visible:ring-2 focus-visible:ring-primary"
                        onClick={() => onSelect(row)}
                      >
                        {row.status === "flagged" || row.status === "appealed"
                          ? "Review"
                          : "View details"}
                      </button>
                    ) : (
                      <span className="text-muted-foreground">No check-in</span>
                    )}
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
      <nav
        aria-label="Session attendance pagination"
        className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4 text-xs text-muted-foreground"
      >
        <p aria-live="polite">
          {loading || error
            ? "—"
            : `${filtered.length ? start + 1 : 0}–${Math.min(start + pageSize, filtered.length)} of ${filtered.length} students`}
        </p>
        <div className="flex gap-1">
          <button
            className={control}
            disabled={loading || !!error || page === 1}
            onClick={() => setPagination({ signature, page: page - 1 })}
          >
            Previous
          </button>
          <button
            className={control}
            disabled={loading || !!error || page >= pages}
            onClick={() => setPagination({ signature, page: page + 1 })}
          >
            Next
          </button>
        </div>
      </nav>
    </section>
  );
}
