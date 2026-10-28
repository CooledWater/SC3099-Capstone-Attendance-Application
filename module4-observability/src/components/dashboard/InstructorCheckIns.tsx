import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle } from "lucide-react";
import { api } from "@/lib/api";
import type { CourseRow } from "@/lib/attendance";
import { statusText } from "@/lib/attendance";
import { formatSingaporeDateTime } from "@/lib/time";
import { exportFilename, saveExport } from "@/lib/exports";
import {
  attendanceLabels,
  factorLabel,
  fetchCourseSessions,
  fetchFlaggedSession,
  fetchSessionAttendance,
  reviewCheckIn,
  type CheckInDetails,
  type FlaggedCheckIn,
  type RosterEntry,
  type RosterSession,
  type SessionAttendance,
} from "@/lib/checkin-roster";
import { AttendanceRoster, VerificationBadge } from "./AttendanceTable";

const control =
  "rounded-lg border border-border bg-secondary/40 px-3 py-2.5 text-xs text-foreground outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:opacity-40";
const message = (error: unknown) =>
  error instanceof Error ? error.message : "The request failed. Please try again.";
const lifecycleLabel = (value: string) => value.charAt(0).toUpperCase() + value.slice(1);

export function InstructorCheckIns({
  courses,
  selectedCourseId,
  onCourseChange,
  userId,
  initialSessionId = "",
  onSessionChange,
  reviewOnly = false,
  canExport = true,
}: {
  courses: CourseRow[];
  selectedCourseId: string;
  onCourseChange: (id: string) => void;
  userId: string;
  initialSessionId?: string;
  onSessionChange?: (sessionId: string) => void;
  reviewOnly?: boolean;
  canExport?: boolean;
}) {
  const courseId =
    courses.find((course) => course.id === selectedCourseId)?.id ?? courses[0]?.id ?? "";
  useEffect(() => {
    if (courseId && courseId !== selectedCourseId) onCourseChange(courseId);
  }, [courseId, selectedCourseId, onCourseChange]);
  return (
    <div className="mt-4 space-y-5">
      <header className="flex flex-wrap items-center gap-4">
        <h2 className="font-display text-lg font-semibold">Check-ins</h2>
        <label className="ml-auto flex items-center gap-2 text-xs text-muted-foreground">
          Course
          <select
            aria-label="Check-ins course"
            className={`${control} max-w-full sm:min-w-64`}
            value={courseId}
            onChange={(event) => onCourseChange(event.target.value)}
            disabled={!courses.length}
          >
            {!courses.length && <option value="">No authorised courses</option>}
            {courses.map((course) => (
              <option value={course.id} key={course.id}>
                {course.code} · {course.name}
              </option>
            ))}
          </select>
        </label>
      </header>
      {courseId ? (
        <CourseCheckIns
          key={`${userId}:${courseId}`}
          courseId={courseId}
          userId={userId}
          initialSessionId={initialSessionId}
          {...(onSessionChange ? { onSessionChange } : {})}
          reviewOnly={reviewOnly}
          canExport={canExport}
        />
      ) : (
        <p className="rounded-2xl border border-border p-5 text-sm text-muted-foreground">
          No authorised courses are available.
        </p>
      )}
    </div>
  );
}

function CourseCheckIns({
  courseId,
  userId,
  initialSessionId,
  onSessionChange,
  reviewOnly,
  canExport = true,
}: {
  courseId: string;
  userId: string;
  initialSessionId: string;
  onSessionChange?: (sessionId: string) => void;
  reviewOnly: boolean;
  canExport?: boolean;
}) {
  const [selection, setSelection] = useState(initialSessionId);
  const sessions = useQuery({
    queryKey: ["checkin-sessions", userId, courseId],
    queryFn: ({ signal }) => fetchCourseSessions(courseId, signal),
    refetchInterval: 30000,
  });
  const session = sessions.data?.find((row) => row.id === selection) ?? sessions.data?.[0];
  useEffect(() => {
    if (session && session.id !== initialSessionId) onSessionChange?.(session.id);
  }, [session, initialSessionId, onSessionChange]);
  if (sessions.isPending)
    return (
      <p role="status" className="text-sm text-muted-foreground">
        Loading sessions…
      </p>
    );
  if (sessions.isError)
    return (
      <p role="alert" className="text-sm text-destructive">
        {message(sessions.error)}{" "}
        <button className={control} onClick={() => void sessions.refetch()}>
          Retry
        </button>
      </p>
    );
  if (!session)
    return (
      <p className="rounded-2xl border border-border p-5 text-sm text-muted-foreground">
        No active or closed sessions are available for this course.
      </p>
    );
  return (
    <>
      <label className="grid gap-2 text-xs text-muted-foreground">
        Session
        <select
          aria-label="Check-ins session"
          className={`${control} w-full`}
          value={session.id}
          onChange={(event) => setSelection(event.target.value)}
        >
          {sessions.data.map((row) => (
            <option value={row.id} key={row.id}>
              {row.name} ·{" "}
              {formatSingaporeDateTime(row.scheduled_start, {
                day: "numeric",
                month: "short",
                year: "numeric",
                hour: "numeric",
                minute: "2-digit",
                hour12: true,
              })}{" "}
              SGT · {lifecycleLabel(row.status)}
            </option>
          ))}
        </select>
      </label>
      <SessionCheckIns
        key={session.id}
        session={session}
        courseId={courseId}
        userId={userId}
        reviewOnly={reviewOnly}
        canExport={canExport}
      />
    </>
  );
}

function SessionCheckIns({
  session,
  courseId,
  userId,
  reviewOnly: initialReviewOnly,
  canExport = true,
}: {
  session: RosterSession;
  courseId: string;
  userId: string;
  reviewOnly: boolean;
  canExport?: boolean;
}) {
  const [verification, setVerification] = useState<string[]>(
    initialReviewOnly ? ["flagged", "appealed"] : [],
  );
  const reviewOnly =
    verification.length > 0 &&
    verification.every((value) => value === "flagged" || value === "appealed");
  const [selected, setSelected] = useState<RosterEntry | null>(null);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const exportBusy = useRef(false);
  const exportAbort = useRef<AbortController | null>(null);
  useEffect(() => () => exportAbort.current?.abort(), []);
  const roster = useQuery({
    queryKey: ["session-attendance", userId, courseId, session.id],
    queryFn: ({ signal }) => fetchSessionAttendance(session.id, signal),
    refetchInterval: 30000,
  });
  const flagged = useQuery({
    queryKey: ["session-flagged", userId, courseId, session.id],
    queryFn: ({ signal }) => fetchFlaggedSession(courseId, session.id, signal),
    enabled: reviewOnly,
    refetchInterval: 30000,
  });
  const flaggedIds =
    reviewOnly && flagged.data ? new Set(flagged.data.map((row) => row.id)) : undefined;
  const data =
    roster.data?.course_id === courseId && roster.data.session_id === session.id
      ? roster.data
      : undefined;
  async function exportSession() {
    if (!canExport) return;
    if (exportBusy.current) return;
    exportBusy.current = true;
    setExporting(true);
    setExportError(null);
    const controller = new AbortController();
    exportAbort.current = controller;
    try {
      const response = await api.response(
        `/export/session/${encodeURIComponent(session.id)}?format=csv`,
        { signal: controller.signal },
      );
      const blob = await response.blob();
      if (!controller.signal.aborted)
        saveExport(
          blob,
          exportFilename(
            response.headers.get("Content-Disposition"),
            `session-${session.id}.csv`,
            "csv",
          ),
        );
    } catch (error) {
      if (!controller.signal.aborted) setExportError(message(error));
    } finally {
      exportBusy.current = false;
      setExporting(false);
    }
  }
  const tableError = roster.isError
    ? message(roster.error)
    : reviewOnly && flagged.isError
      ? message(flagged.error)
      : null;
  return (
    <>
      {roster.isError && (
        <p role="alert" className="text-sm text-destructive">
          Could not load attendance.{" "}
          <button className={control} onClick={() => void roster.refetch()}>
            Retry
          </button>
        </p>
      )}
      {!roster.isError && !data && (
        <p role="status" className="text-sm text-muted-foreground">
          Loading attendance summary…
        </p>
      )}
      {data && !roster.isError && (
        <div className="grid gap-4 md:grid-cols-[1.3fr_1fr]">
          <AttendanceBreakdown data={data} />
          <ReviewSummary data={data} onFilter={() => setVerification(["flagged", "appealed"])} />
        </div>
      )}
      {exportError && (
        <p role="alert" className="text-sm text-destructive">
          {exportError}
        </p>
      )}
      <AttendanceRoster
        rows={data?.items ?? []}
        loading={roster.isPending || (reviewOnly && flagged.isPending)}
        error={tableError}
        verification={verification}
        onVerificationChange={setVerification}
        flaggedIds={flaggedIds}
        onSelect={setSelected}
        onExport={() => void exportSession()}
        exporting={exporting}
        canExport={canExport}
      />
      {reviewOnly && flagged.isError && (
        <button className={control} onClick={() => void flagged.refetch()}>
          Retry flagged check-ins
        </button>
      )}
      {selected?.checkin_id && (
        <CheckInDetail
          key={selected.checkin_id}
          entry={selected}
          session={session}
          courseId={courseId}
          userId={userId}
          onClose={() => setSelected(null)}
        />
      )}
    </>
  );
}

function AttendanceBreakdown({ data }: { data: SessionAttendance }) {
  const slices = [
    { label: "Present", count: data.summary.present, color: "#82deb3" },
    { label: "Absent", count: data.summary.absent, color: "#ee94af" },
  ];
  const percent = (count: number) => (data.expected ? (count / data.expected) * 100 : 0);
  const first = percent(slices[0]!.count);
  const background = data.expected
    ? `conic-gradient(#82deb3 0% ${first}%, #ee94af ${first}% 100%)`
    : "var(--color-secondary, #30283b)";
  return (
    <section className="rounded-2xl border border-border bg-glass p-5">
      <div className="flex items-center justify-between gap-3">
        <h3 className="font-display text-sm font-semibold">Attendance breakdown</h3>
        <span className="text-xs text-muted-foreground">{data.expected} expected</span>
      </div>
      <div className="mt-5 flex flex-wrap items-center justify-center gap-6 sm:flex-nowrap sm:justify-start">
        <div
          role="img"
          aria-label={`Attendance ${Math.round(data.summary.attendance_rate * 100)} percent`}
          className="grid size-36 shrink-0 place-items-center rounded-full"
          style={{ background }}
        >
          <div className="grid size-26 place-items-center rounded-full bg-card font-display text-2xl font-semibold">
            {Math.round(data.summary.attendance_rate * 100)}%
          </div>
        </div>
        <ul className="min-w-40 flex-1 space-y-3 text-xs">
          {slices.map((slice) => (
            <li key={slice.label} className="flex items-center gap-2">
              <span className="size-2 rounded-full" style={{ background: slice.color }} />
              <span className="text-muted-foreground">{slice.label}</span>
              <span className="ml-auto font-medium tabular-nums">
                {slice.count} · {Number(percent(slice.count).toFixed(1))}%
              </span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

function ReviewSummary({ data, onFilter }: { data: SessionAttendance; onFilter: () => void }) {
  const flagged = data.summary.verification.flagged,
    appealed = data.summary.verification.appealed;
  const total = flagged + appealed;
  return (
    <section
      className={`flex flex-col rounded-2xl border border-border p-5 ${total ? "bg-rose-400/5" : "bg-glass"}`}
    >
      <div className="flex items-center justify-between gap-3">
        <h3 className="font-display text-sm font-semibold">Check-ins requiring review</h3>
        <AlertTriangle
          aria-hidden="true"
          size={16}
          className={total ? "text-rose-300" : "text-muted-foreground"}
        />
      </div>
      <p
        className={`mt-5 text-4xl tabular-nums ${total ? "text-rose-300" : "text-muted-foreground"}`}
      >
        {total}
      </p>
      <p className="mt-3 text-xs text-muted-foreground">
        {flagged} flagged · {appealed} appealed
      </p>
      <button
        onClick={onFilter}
        className={`mt-5 w-full rounded-lg border px-3 py-3 text-xs font-medium focus-visible:ring-2 focus-visible:ring-primary ${total ? "border-rose-300/25 bg-rose-400/50 text-white hover:bg-rose-400/60" : "border-border bg-secondary/30 text-muted-foreground"}`}
      >
        Flagged check-ins
      </button>
    </section>
  );
}

export function CheckInDetail({
  entry,
  session,
  courseId,
  userId,
  onClose,
}: {
  entry: RosterEntry;
  session: RosterSession;
  courseId: string;
  userId: string;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const busy = useRef(false);
  const panel = useRef<HTMLElement>(null);
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    panel.current?.focus();
    panel.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    return () => {
      mounted.current = false;
    };
  }, []);
  const key = ["checkin-detail", userId, courseId, session.id, entry.checkin_id];
  const detail = useQuery({
    queryKey: key,
    queryFn: ({ signal }) =>
      api.request<CheckInDetails>(`/checkins/${encodeURIComponent(entry.checkin_id!)}`, { signal }),
    staleTime: 0,
  });
  const record =
    detail.data?.session_id === session.id && detail.data.course_id === courseId
      ? detail.data
      : undefined;
  const reviewable = record?.status === "flagged" || record?.status === "appealed";
  const appealedReview =
    record?.status === "appealed" ||
    (record?.status === "flagged" && Boolean(record.appeal_reason));
  const showRiskFactors = reviewable || record?.status === "rejected";
  const reviewEvidence = useQuery({
    queryKey: [
      "checkin-review-evidence",
      userId,
      courseId,
      session.id,
      entry.checkin_id,
      record?.status,
    ],
    queryFn: ({ signal }) =>
      record?.status === "rejected"
        ? api.request<FlaggedCheckIn[]>(`/checkins/session/${encodeURIComponent(session.id)}`, {
            signal,
          })
        : fetchFlaggedSession(courseId, session.id, signal),
    enabled: showRiskFactors,
    staleTime: 30_000,
  });
  const evidenceRows = Array.isArray(reviewEvidence.data) ? reviewEvidence.data : [];
  const evidence = evidenceRows.find((item) => item.id === entry.checkin_id) ?? record;
  async function decide(status: "approved" | "rejected") {
    if (busy.current || !record || !reviewable) return;
    busy.current = true;
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const result = await reviewCheckIn(record.id, status, notes);
      // Reflect the confirmed server decision immediately, then refresh full
      // evidence and aggregates. A refresh failure must not resubmit a decision.
      qc.setQueryData(key, { ...record, status: result.status });
      if (mounted.current) setSuccess(`Check-in ${statusText[result.status].toLowerCase()}.`);
      await Promise.all([
        qc.invalidateQueries({ queryKey: key }),
        ...[
          "session-attendance",
          "session-flagged",
          "check-ins",
          "my-check-ins",
          "sessions",
          "api-metrics",
          "audit-logs",
          "session-stats",
        ].map((name) => qc.invalidateQueries({ queryKey: [name] })),
      ]);
    } catch (failure) {
      if (mounted.current) setError(message(failure));
      if (
        failure &&
        typeof failure === "object" &&
        "status" in failure &&
        [400, 409].includes(Number(failure.status))
      ) {
        await Promise.all([
          qc.invalidateQueries({ queryKey: key }),
          ...[
            "session-attendance",
            "session-flagged",
            "session-stats",
            "checkin-review-evidence",
          ].map((name) => qc.invalidateQueries({ queryKey: [name] })),
        ]);
      }
    } finally {
      busy.current = false;
      if (mounted.current) setSaving(false);
    }
  }
  return (
    <section
      ref={panel}
      tabIndex={-1}
      aria-label="Check-in details"
      className="rounded-2xl border border-primary/40 bg-card p-5 outline-none focus-visible:ring-2 focus-visible:ring-primary"
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="font-display text-sm font-semibold">
            {entry.student_name} · Check-in details
          </h3>
          <p className="mt-1 text-xs text-muted-foreground">
            {entry.student_email} · {session.name} ·{" "}
            {formatSingaporeDateTime(session.scheduled_start)} SGT
          </p>
        </div>
        <button className={control} onClick={onClose}>
          Close
        </button>
      </div>
      {detail.isFetching && (
        <p role="status" className="mt-4 text-xs text-muted-foreground">
          Loading full check-in details…
        </p>
      )}
      {detail.isError && (
        <p role="alert" className="mt-4 text-sm text-destructive">
          {message(detail.error)}{" "}
          <button className={control} onClick={() => void detail.refetch()}>
            Retry
          </button>
        </p>
      )}
      {success && (
        <p role="status" className="mt-4 text-sm text-emerald-300">
          {success}
        </p>
      )}
      {record && !detail.isFetching && !detail.isError && (
        <>
          <div className="mt-5 grid gap-3 sm:grid-cols-2">
            <div className="rounded-xl bg-secondary/40 p-3">
              <p className="text-xs text-muted-foreground">Attendance</p>
              <p className="mt-1 text-sm">
                {attendanceLabels[entry.attendance]} ·{" "}
                {formatSingaporeDateTime(record.checked_in_at, {
                  hour: "numeric",
                  minute: "2-digit",
                  hour12: true,
                })}{" "}
                SGT
              </p>
            </div>
            <div className="rounded-xl bg-secondary/40 p-3">
              <p className="mb-1 text-xs text-muted-foreground">Verification</p>
              <VerificationBadge status={record.status} />
            </div>
            <div className="rounded-xl bg-secondary/40 p-3">
              <p className="text-xs text-muted-foreground">Risk score · scale 0–1</p>
              <p className="mt-1 text-2xl tabular-nums">
                {record.risk_score} <span className="text-sm text-muted-foreground">/ 1</span>
              </p>
            </div>
            {appealedReview && (
              <div className="rounded-xl bg-secondary/40 p-3">
                <p className="text-xs text-muted-foreground">Student explanation</p>
                <p className="mt-1 whitespace-pre-wrap break-words text-sm">
                  {record.appeal_reason || "No explanation submitted."}
                </p>
              </div>
            )}
          </div>
          {showRiskFactors && reviewEvidence.isFetching && (
            <p role="status" className="mt-5 text-xs text-muted-foreground">
              Loading review evidence…
            </p>
          )}
          {showRiskFactors && reviewEvidence.isError && (
            <p role="alert" className="mt-5 text-sm text-destructive">
              Could not load risk factors. {message(reviewEvidence.error)}{" "}
              <button className={control} onClick={() => void reviewEvidence.refetch()}>
                Retry risk factors
              </button>
            </p>
          )}
          {showRiskFactors && !reviewEvidence.isFetching && !reviewEvidence.isError && (
            <>
              <h4 className="mt-5 text-sm font-semibold">Risk factors</h4>
              <div className="mt-2 overflow-x-auto">
                <table className="w-full min-w-80 text-left text-xs">
                  <thead>
                    <tr className="border-b border-border text-muted-foreground">
                      {["Factor", "Severity", "Weight"].map((label) => (
                        <th key={label} scope="col" className="py-3 pr-3 font-normal">
                          {label}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {!evidence?.risk_factors?.length && (
                      <tr>
                        <td colSpan={3} className="py-4">
                          No risk factors returned.
                        </td>
                      </tr>
                    )}
                    {(evidence?.risk_factors ?? []).map((factor, i) => {
                      const item = typeof factor === "string" ? { type: factor } : factor;
                      const severity = item.severity ?? "unknown";
                      return (
                        <tr key={i}>
                          <td className="py-4 pr-3">
                            {factorLabel(item.type ?? item.signal_type ?? "")}
                          </td>
                          <td className="py-4 pr-3">
                            <span
                              className={`rounded-full px-2 py-1 ${severity === "high" || severity === "critical" ? "bg-rose-400/20 text-rose-300" : severity === "medium" ? "bg-amber-400/15 text-amber-300" : "bg-secondary text-muted-foreground"}`}
                            >
                              {lifecycleLabel(severity)}
                            </span>
                          </td>
                          <td className="py-4 tabular-nums">
                            {typeof item.weight === "number" ? String(item.weight) : "—"}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </>
          )}
          {reviewable && (
            <form
              className="mt-5"
              onSubmit={(event) => {
                event.preventDefault();
                void decide("approved");
              }}
            >
              <label className="grid gap-2 text-xs text-muted-foreground">
                Review notes <span className="sr-only">(optional)</span>
                <textarea
                  className={`${control} min-h-24 resize-y text-sm`}
                  value={notes}
                  onChange={(event) => setNotes(event.target.value)}
                  placeholder="Record the reason for your decision"
                  disabled={saving}
                />
              </label>
              <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
                <p className="text-xs text-muted-foreground">Decision updates verification only</p>
                <div className="flex gap-2">
                  <button
                    type="button"
                    className={control}
                    disabled={saving}
                    onClick={() => void decide("rejected")}
                  >
                    Reject
                  </button>
                  <button
                    type="submit"
                    className="rounded-lg border border-emerald-300/30 bg-emerald-500 px-4 py-2.5 text-xs font-semibold text-slate-950 hover:bg-emerald-400 focus-visible:ring-2 focus-visible:ring-emerald-300 disabled:opacity-50"
                    disabled={saving}
                  >
                    {saving ? "Saving…" : "Approve"}
                  </button>
                </div>
              </div>
            </form>
          )}
        </>
      )}
      {error && (
        <p role="alert" className="mt-3 text-sm text-destructive">
          {error}
        </p>
      )}
    </section>
  );
}
