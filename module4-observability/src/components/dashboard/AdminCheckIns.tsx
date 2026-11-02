import { useState } from "react";
import { AttendanceRoster } from "./AttendanceTable";
import { CheckInDetail } from "./InstructorCheckIns";
import type { CheckInFilter } from "./CheckInsPanel";
import {
  checkInsToCsv,
  downloadCsv,
  toRows,
  type CourseRow,
  type RawCheckIn,
  type SessionRow,
} from "@/lib/attendance";
import type { RosterEntry } from "@/lib/checkin-roster";
import { formatSingaporeDateTime, parseApiDateTime } from "@/lib/time";

const control =
  "rounded-lg border border-border bg-secondary/40 px-3 py-2.5 text-xs text-foreground focus-visible:ring-2 focus-visible:ring-primary";

export function AdminCheckIns({
  courses,
  sessions,
  checkIns,
  userId,
  initialFilter,
  loading,
  error,
  onRetry,
}: {
  courses: CourseRow[];
  sessions: SessionRow[];
  checkIns: RawCheckIn[];
  userId: string;
  initialFilter: CheckInFilter;
  loading: boolean;
  error: boolean;
  onRetry: () => void;
}) {
  const [courseId, setCourseId] = useState("all");
  const [sessionId, setSessionId] = useState("all");
  const [scope, setScope] = useState(initialFilter);
  const [verification, setVerification] = useState<string[]>(initialFilter.statuses ?? []);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const sessionMap = new Map(sessions.map((session) => [session.id, session]));
  const day = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Singapore",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
  const today = day.format(new Date());
  const scoped = checkIns.filter((row) => {
    const session = sessionMap.get(row.session_id);
    return (
      session &&
      (courseId === "all" || session.course_id === courseId) &&
      (sessionId === "all" || session.id === sessionId) &&
      (!scope.today || day.format(parseApiDateTime(row.checked_in_at)) === today) &&
      (scope.minRisk == null || row.risk_score >= scope.minRisk)
    );
  });
  const entries: RosterEntry[] = scoped.map((row) => {
    const session = sessionMap.get(row.session_id)!;
    const timestamp = parseApiDateTime(row.checked_in_at).getTime();
    const closes = Math.min(
      parseApiDateTime(session.ends_at).getTime(),
      session.actual_end ? parseApiDateTime(session.actual_end).getTime() : Infinity,
    );
    return {
      student_id: row.student_id ?? row.id,
      student_name: row.student_name ?? "Unknown student",
      student_email: row.student_email ?? "—",
      checkin_id: row.id,
      checked_in_at: row.checked_in_at,
      attendance:
        timestamp >= parseApiDateTime(session.starts_at).getTime() && timestamp < closes
          ? "present"
          : "absent",
      status: row.status,
      risk_score: row.risk_score,
    };
  });
  const checkInMap = new Map(scoped.map((row) => [row.id, row]));
  const selected = entries.find((entry) => entry.checkin_id === selectedId);
  const selectedRaw = selectedId ? checkInMap.get(selectedId) : undefined;
  const selectedSession = selectedRaw ? sessionMap.get(selectedRaw.session_id) : undefined;
  const context = (entry: RosterEntry) => {
    const row = entry.checkin_id ? checkInMap.get(entry.checkin_id) : undefined;
    const session = row ? sessionMap.get(row.session_id) : undefined;
    if (!session) return "";
    const name = session.name.replace(
      /\s+\(\d{1,2} (?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) (?:\d{4} )?\d{1,2}[:.]\d{2}(?: ?[AP]M)? SGT\)\s*$/i,
      "",
    );
    return `${session.courses?.code ?? "Course"} · ${name}`;
  };
  return (
    <div className="mt-4 space-y-5">
      <header className="flex flex-wrap items-center gap-4">
        <h2 className="font-display text-lg font-semibold">Check-ins</h2>
        <label className="ml-auto flex items-center gap-2 text-xs text-muted-foreground">
          Course
          <select
            aria-label="Check-ins course"
            className={control}
            value={courseId}
            onChange={(event) => {
              setCourseId(event.target.value);
              setSessionId("all");
              setSelectedId(null);
            }}
          >
            <option value="all">All courses</option>
            {courses.map((course) => (
              <option key={course.id} value={course.id}>
                {course.code} · {course.name}
              </option>
            ))}
          </select>
        </label>
      </header>
      <label className="grid gap-2 text-xs text-muted-foreground">
        Session
        <select
          aria-label="Check-ins session"
          className={`${control} w-full`}
          value={sessionId}
          onChange={(event) => {
            setSessionId(event.target.value);
            setSelectedId(null);
          }}
        >
          <option value="all">All sessions</option>
          {sessions
            .filter((session) => courseId === "all" || session.course_id === courseId)
            .map((session) => (
              <option key={session.id} value={session.id}>
                {session.courses?.code} · {session.name} ·{" "}
                {formatSingaporeDateTime(session.starts_at)} SGT
              </option>
            ))}
        </select>
      </label>
      {(scope.today || scope.minRisk != null) && (
        <p className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
          {scope.today && <span>Check-ins recorded today · SGT</span>}
          {scope.minRisk != null && <span>Risk ≥ {scope.minRisk}</span>}
          <button
            className="underline"
            onClick={() => {
              setScope({});
              setSelectedId(null);
            }}
          >
            Clear date and risk filters
          </button>
        </p>
      )}
      {error && (
        <p role="alert" className="text-sm text-destructive">
          Could not load check-ins.{" "}
          <button className="underline" onClick={onRetry}>
            Retry
          </button>
        </p>
      )}
      <AttendanceRoster
        key={`${courseId}:${sessionId}`}
        rows={entries}
        loading={loading}
        error={error ? "Could not load check-ins." : null}
        verification={verification}
        onVerificationChange={(value) => {
          setVerification(value);
          setSelectedId(null);
        }}
        flaggedIds={undefined}
        onSelect={(entry) => setSelectedId(entry.checkin_id)}
        onExport={() =>
          downloadCsv(
            "admin-checkins",
            checkInsToCsv(
              toRows(
                scoped.filter((row) => !verification.length || verification.includes(row.status)),
              ),
            ),
          )
        }
        exporting={false}
        checkInsOnly
        title="Check-ins across courses"
        rowContext={context}
      />
      {selected && selectedSession && (
        <CheckInDetail
          key={selected.checkin_id!}
          entry={selected}
          session={{
            id: selectedSession.id,
            course_id: selectedSession.course_id,
            name: selectedSession.name,
            scheduled_start: selectedSession.starts_at,
            scheduled_end: selectedSession.ends_at,
            status: selectedSession.status,
          }}
          courseId={selectedSession.course_id}
          userId={userId}
          onClose={() => setSelectedId(null)}
        />
      )}
    </div>
  );
}
