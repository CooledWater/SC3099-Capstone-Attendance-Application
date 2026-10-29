import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ApiError } from "@/lib/api";
import { submitCheckInAppeal, fetchCheckInDetail, fetchMyCheckInsPage, fetchMySessions, toRows, HISTORY_PAGE_SIZE, type EnrollmentRow } from "@/lib/attendance";
import { parseApiDateTime } from "@/lib/time";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import type { CheckInRow } from "./AttendanceTable";

const appealWindowMs = 7 * 24 * 60 * 60 * 1000;
const sessionDayFormat = new Intl.DateTimeFormat("en-GB", {
  timeZone: "Asia/Singapore", day: "2-digit", month: "short", year: "numeric",
});
const sessionClockFormat = new Intl.DateTimeFormat("en-US", {
  timeZone: "Asia/Singapore", hour: "numeric", minute: "2-digit", hour12: true,
});

function formatSessionTime(value: string) {
  const date = parseApiDateTime(value);
  if (Number.isNaN(date.getTime())) return "Invalid time";
  const day = sessionDayFormat.format(date);
  const time = sessionClockFormat.format(date);
  return `${day}, ${time}`;
}

function formatMetric(value: number | null | undefined) {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(2) : "—";
}

const statusLabel: Record<CheckInRow["status"], string> = {
  approved: "Approved",
  flagged: "Flagged",
  rejected: "Rejected",
  pending: "Pending",
  appealed: "Appealed",
};

const statusTone: Record<CheckInRow["status"], string> = {
  approved: "bg-accent/15 text-accent border-accent/25",
  flagged: "bg-warning/15 text-warning border-warning/25",
  rejected: "bg-destructive/15 text-destructive border-destructive/25",
  pending: "bg-primary/15 text-primary border-primary/25",
  appealed: "bg-warning/15 text-warning border-warning/25",
};

export function CourseHistory({ rows, initialCourseId = "all", initialStatuses = [], enrolledCourses = [] }: {
  rows: CheckInRow[]; initialCourseId?: string; initialStatuses?: string[];
  enrolledCourses?: EnrollmentRow[];
}) {
  const courses = useMemo(() => [...new Set([...rows.map((r) => r.course), ...enrolledCourses.map(row => row.course_code)])].sort(), [rows, enrolledCourses]);
  const [selectedCourseId, setCourse] = useState(initialCourseId);
  const course = selectedCourseId === "all" ? "all" : rows.find(row => row.courseId === selectedCourseId)?.course ?? enrolledCourses.find(row => row.course_id === selectedCourseId)?.course_code ?? selectedCourseId;
  const [statuses, setStatuses] = useState<string[]>(initialStatuses);
  const [search, setSearch] = useState("");
  const settledSearch = useDebouncedValue(search.trim());
  const [page, setPage] = useState(0);
  const courseId = selectedCourseId;
  const history = useQuery({
    queryKey: ["my-check-ins", "page", courseId, settledSearch, page, statuses],
    queryFn: ({ signal }) => fetchMyCheckInsPage("all", page * HISTORY_PAGE_SIZE, courseId, signal, settledSearch, statuses),
    placeholderData: (previous) => previous,
    staleTime: 15000,
    refetchInterval: 30000,
  });
  const sessions = useQuery({
    queryKey: ["my-sessions"],
    queryFn: fetchMySessions,
    staleTime: 15000,
  });
  const [selectedCheckIn, setSelectedCheckIn] = useState<CheckInRow | null>(null);
  const [selectedDetails, setSelectedDetails] = useState<CheckInRow | null>(null);
  const [appealReason, setAppealReason] = useState("");
  const queryClient = useQueryClient();
  const appeal = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) => submitCheckInAppeal(id, reason),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["my-check-ins"] }),
        queryClient.invalidateQueries({ queryKey: ["student-overview"] }),
      ]);
      setSelectedCheckIn(null);
      setAppealReason("");
      toast.success("Appeal submitted.");
    },
  });

  const filtered = useMemo(() => toRows(history.data ?? []), [history.data]);
  const matchingCount = rows.filter(row =>
    (courseId === "all" || row.courseId === courseId) &&
    (!statuses.length || statuses.includes(row.status)) &&
    (row.sessionName ?? "").toLowerCase().includes(settledSearch.toLowerCase())).length;
  const updating = search.trim() !== settledSearch || history.isFetching;

  function canAppeal(row: CheckInRow) {
    if (row.appealedAt != null) return false;
    if (row.status !== "flagged" && row.status !== "rejected") return false;
    const checkedInAt = parseApiDateTime(row.time).getTime();
    const age = Date.now() - checkedInAt;
    return Number.isFinite(checkedInAt) && age >= 0 && age <= appealWindowMs;
  }

  function submitAppeal(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const reason = appealReason.trim();
    if (!selectedCheckIn || !reason || appeal.isPending) return;
    appeal.mutate({ id: selectedCheckIn.id, reason });
  }

  const appealError =
    appeal.error instanceof ApiError && appeal.error.status === 404
      ? "The appeal endpoint or check-in record was not found. Backend appeal support may still be pending."
      : appeal.error instanceof Error
        ? appeal.error.message
        : null;

  function prefetchDetails(row: CheckInRow) {
    void queryClient.prefetchQuery({
      queryKey: ["my-check-in-detail", row.id],
      queryFn: ({ signal }) => fetchCheckInDetail(row.id, signal),
      staleTime: 60_000,
    });
  }

  const details = useQuery({
    queryKey: ["my-check-in-detail", selectedDetails?.id],
    queryFn: ({ signal }) => fetchCheckInDetail(selectedDetails!.id, signal),
    enabled: selectedDetails !== null,
    retry: false,
    staleTime: 60_000,
  });
  const selectedSession = selectedDetails
    ? sessions.data?.find((session) => session.id === selectedDetails.sessionId)
    : undefined;

  return (
    <>
      <section className="lg:col-span-8 rounded-2xl border border-primary/40 bg-primary/5 p-5 shadow-[var(--shadow-glass)] backdrop-blur">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="font-display text-base text-foreground">Check-in history</h2>
            <p className="text-xs text-muted-foreground">
              Page {page + 1} · {filtered.length} record{filtered.length === 1 ? "" : "s"}
              {course === "all" ? " across your courses" : ` in ${course}`}
            </p>
          </div>
          <label className="ml-auto text-xs text-muted-foreground">
            Course
            <select className="ml-2 rounded-lg border border-border bg-background px-3 py-2 text-foreground"
              value={selectedCourseId} onChange={(event) => { setCourse(event.target.value); setPage(0); }}>
              <option value="all">All courses</option>
              {courses.map(code => <option key={code} value={rows.find(row => row.course === code)?.courseId ?? enrolledCourses.find(row => row.course_code === code)?.course_id ?? code}>{code}</option>)}
            </select>
          </label>
        </div>
        <div className="mt-4 flex flex-wrap gap-3">
          <label className="flex min-w-48 flex-1 items-center gap-2 text-xs text-muted-foreground">
            <span className="sr-only">Session name</span>
            <input type="search" placeholder="Search by session name"
              className="min-w-0 flex-1 rounded-lg border border-border bg-background px-3 py-2 text-foreground"
              value={search} onChange={(event) => { setSearch(event.target.value); setPage(0); }} />
          </label>
        </div>
        {statuses.length > 0 && <p className="mt-3 text-xs text-muted-foreground">
          Showing flagged records and appeals awaiting review.
          <button type="button" className="ml-2 underline" onClick={() => { setStatuses([]); setPage(0); }}>Clear status filters</button>
        </p>}
        {history.isError && <p role="alert" className="mt-3 text-sm text-destructive">Could not load check-in history. <button type="button" className="underline" onClick={() => void history.refetch()}>Retry</button></p>}
        <div className="mt-4 overflow-x-auto" aria-busy={updating}>
          <table className="w-full min-w-[650px] text-left text-sm">
            <thead>
              <tr className="text-xs uppercase tracking-wide text-muted-foreground">
                <th className="pb-2 font-medium">Course</th>
                <th className="pb-2 font-medium">Session time</th>
                <th className="pb-2 font-medium">Session</th>
                <th className="pb-2 font-medium">Status</th>
                <th className="pb-2 font-medium">Risk score</th>
                <th className="pb-2 font-medium">Action</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((r) => {
                return (
                  <tr
                    key={r.id}
                    tabIndex={0}
                    role="button"
                    aria-label={`View details for ${r.sessionName ?? "this check-in"}`}
                    className="cursor-pointer border-t border-border/60 outline-none transition hover:bg-primary/5 focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary"
                    onMouseEnter={() => prefetchDetails(r)}
                    onFocus={() => prefetchDetails(r)}
                    onClick={() => setSelectedDetails(r)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        setSelectedDetails(r);
                      }
                    }}
                  >
                    <td className="py-2.5 pr-3 text-foreground">{r.course}</td>
                    <td className="py-2.5 pr-3 text-muted-foreground">
                      {formatSessionTime(r.time)}
                    </td>
                    <td className="py-2.5 pr-3 text-muted-foreground">{r.sessionName}</td>
                    <td className="py-2.5">
                      <span
                        className={`rounded-full border px-2 py-0.5 text-xs ${statusTone[r.status]}`}
                      >
                        {statusLabel[r.status]}
                      </span>
                    </td>
                    <td className="py-2.5 pr-3 tabular-nums">{r.riskScore ?? "—"}</td>
                    <td className="py-2.5">
                      {canAppeal(r) && (
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={updating}
                          onClick={(event) => {
                            event.stopPropagation();
                            setSelectedCheckIn(r);
                            setAppealReason("");
                            appeal.reset();
                          }}
                        >
                          Appeal
                        </Button>
                      )}
                    </td>
                  </tr>
                );
              })}
              {(history.isPending || (!history.isError && filtered.length === 0)) && (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-sm text-muted-foreground">
                    {history.isPending ? "Loading check-in history..." : "No check-ins match this selection."}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <div className="mt-4 flex items-center justify-between gap-3 text-xs text-muted-foreground">
          <span role="status">{updating ? "Updating results..." : "50 results per page"}</span>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" disabled={page === 0 || updating} onClick={() => setPage(value => value - 1)}>Previous</Button>
            <Button variant="outline" size="sm" disabled={history.isPending || history.isError || updating || filtered.length < HISTORY_PAGE_SIZE || matchingCount <= (page + 1) * HISTORY_PAGE_SIZE} onClick={() => setPage(value => value + 1)}>Next</Button>
          </div>
        </div>
      </section>

      <Dialog
        open={selectedCheckIn !== null}
        onOpenChange={(open) => {
          if (!open && !appeal.isPending) {
            setSelectedCheckIn(null);
            setAppealReason("");
            appeal.reset();
          }
        }}
      >
        <DialogContent className="border-border bg-card text-card-foreground">
          <DialogHeader>
            <DialogTitle className="font-display">Appeal check-in</DialogTitle>
            <DialogDescription>
              Explain why this {selectedCheckIn?.status} check-in should be reviewed. Appeals must
              be submitted within 7 days of the check-in.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={submitAppeal} className="space-y-4">
            <label className="block text-sm font-medium text-foreground" htmlFor="appeal-reason">
              Reason
              <Textarea
                id="appeal-reason"
                className="mt-2 border-border bg-background text-foreground"
                value={appealReason}
                onChange={(event) => setAppealReason(event.target.value)}
                placeholder="Describe what happened and why you are appealing."
                required
                rows={5}
                disabled={appeal.isPending}
              />
            </label>
            {appealError && (
              <p
                role="alert"
                className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive"
              >
                {appealError}
              </p>
            )}
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                disabled={appeal.isPending}
                onClick={() => {
                  setSelectedCheckIn(null);
                  setAppealReason("");
                  appeal.reset();
                }}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={!appealReason.trim() || appeal.isPending}>
                {appeal.isPending ? "Submitting…" : "Submit appeal"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={selectedDetails !== null} onOpenChange={(open) => { if (!open) setSelectedDetails(null); }}>
        <DialogContent className="max-h-[85vh] overflow-y-auto border-border bg-card text-card-foreground">
          <DialogHeader>
            <DialogTitle className="font-display">Check-in details</DialogTitle>
          </DialogHeader>
          {details.isPending ? (
            <p role="status" className="text-sm text-muted-foreground">Loading check-in details...</p>
          ) : details.isError ? (
            <p role="alert" className="text-sm text-destructive">Could not load check-in details. Please close this dialog and try again.</p>
          ) : details.data && selectedDetails ? (
            <div className="space-y-5 text-sm">
              <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div><dt className="text-xs text-muted-foreground">Session name</dt><dd className="mt-1">{details.data.session_name ?? selectedDetails.sessionName ?? "—"}</dd></div>
                <div><dt className="text-xs text-muted-foreground">Location</dt><dd className="mt-1">{selectedSession?.venue_name ?? "—"}</dd></div>
                <div><dt className="text-xs text-muted-foreground">Check-in closed at</dt><dd className="mt-1">{selectedSession?.checkin_closes_at ? formatSessionTime(selectedSession.checkin_closes_at) : "—"}</dd></div>
                <div><dt className="text-xs text-muted-foreground">Liveness</dt><dd className="mt-1">{details.data.liveness_passed == null ? "Not available" : `${details.data.liveness_passed ? "Passed" : "Failed"} · score ${formatMetric(details.data.liveness_score)}`}</dd></div>
                <div><dt className="text-xs text-muted-foreground">Face match</dt><dd className="mt-1">{details.data.face_match_passed == null ? "Not available" : `${details.data.face_match_passed ? "Passed" : "Failed"} · score ${formatMetric(details.data.face_match_score)}`}</dd></div>
                <div><dt className="text-xs text-muted-foreground">Risk score</dt><dd className="mt-1">{formatMetric(details.data.risk_score)}</dd></div>
              </dl>
            </div>
          ) : null}
        </DialogContent>
      </Dialog>
    </>
  );
}
