import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, ApiError } from "@/lib/api";
import { formatSingaporeDateTime } from "@/lib/time";
import { availableNumber, courseCheckIns, type StudentAttendance } from "@/lib/student-attendance";
import type { CourseRow } from "@/lib/attendance";

const statusColors: Record<string, string> = {
  approved: "bg-emerald-500/15 text-emerald-300",
  pending: "bg-purple-500/15 text-purple-300",
  flagged: "bg-rose-500/20 text-rose-300",
  appealed: "bg-amber-500/20 text-amber-300",
  rejected: "bg-gray-500/20 text-gray-300",
};
const card = "min-w-0 rounded-2xl border border-border bg-secondary/30 p-5";

export function AttendanceSkeleton() {
  return (
    <div role="status" aria-label="Loading student attendance" className="space-y-6">
      <div className="h-20 animate-pulse rounded-2xl bg-secondary/50" />
      <div className="grid gap-3 sm:grid-cols-3">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-40 animate-pulse rounded-2xl bg-secondary/50" />
        ))}
      </div>
      <div className="h-72 animate-pulse rounded-2xl bg-secondary/50" />
    </div>
  );
}

export function StudentAttendanceDetails({
  studentId,
  initialCourseId = "",
  courses = [],
  viewerId,
}: {
  studentId: string;
  initialCourseId?: string;
  courses?: CourseRow[];
  viewerId: string;
}) {
  const [selection, setSelection] = useState({ studentId, courseId: initialCourseId });
  const details = useQuery({
    queryKey: ["student-attendance", viewerId, studentId],
    queryFn: ({ signal }) =>
      api.request<StudentAttendance>(`/stats/students/${encodeURIComponent(studentId)}`, {
        signal,
      }),
    retry: (attempt, error) =>
      !(error instanceof ApiError && [401, 403, 404].includes(error.status)) && attempt < 2,
  });
  if (details.isPending) return <AttendanceSkeleton />;
  if (details.isError || !details.data) {
    const code = details.error instanceof ApiError ? details.error.status : 0;
    const message =
      code === 401
        ? "Your session has expired. Sign in again to view student attendance."
        : code === 403
          ? "You do not have permission to view this student's attendance."
          : code === 404
            ? "This student could not be found."
            : "Could not load student attendance.";
    return (
      <div role="alert" className="rounded-2xl border border-destructive/40 bg-destructive/10 p-6">
        <p>{message}</p>
        <button
          type="button"
          className="mt-3 text-primary underline focus-visible:ring-2 focus-visible:ring-primary"
          onClick={() => void details.refetch()}
        >
          Retry
        </button>
      </div>
    );
  }
  const data = details.data;
  const requestedId = selection.studentId === studentId ? selection.courseId : initialCourseId;
  const course = data.courses.find((item) => item.course_id === requestedId) ?? data.courses[0];
  const initials = data.student_name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
  const label = (id: string, code: string) => {
    const name = courses.find((item) => item.id === id)?.name;
    return name ? `${code} · ${name}` : code;
  };
  const result = course ? courseCheckIns(data, course) : { records: [], ambiguous: false };
  const noSessions = course?.total_sessions === 0;
  const rate = course?.attendance_rate;
  return (
    <div className="min-w-0 space-y-6">
      <header className="flex min-w-0 items-center gap-4">
        <div
          aria-hidden="true"
          className="grid size-14 shrink-0 place-items-center rounded-2xl bg-primary/20 text-xl text-primary"
        >
          {initials}
        </div>
        <div className="min-w-0">
          <p className="text-[10px] uppercase tracking-wider text-muted-foreground">
            Student attendance
          </p>
          <h1 className="mt-1 break-words font-display text-2xl font-semibold">
            {data.student_name}
          </h1>
          <p className="mt-1 break-all text-sm text-muted-foreground">{data.student_email}</p>
        </div>
      </header>
      {!course ? (
        <p className="rounded-2xl border border-border p-6 text-sm text-muted-foreground">
          No authorised courses are available for this student.
        </p>
      ) : (
        <>
          <div className="flex flex-wrap items-end justify-between gap-3">
            {data.courses.length > 1 ? (
              <label className="grid min-w-0 gap-2 text-xs text-muted-foreground">
                Course
                <select
                  aria-label="Student attendance course"
                  value={course.course_id}
                  onChange={(event) => setSelection({ studentId, courseId: event.target.value })}
                  className="max-w-full rounded-lg border border-border bg-secondary px-3 py-2 text-sm text-foreground focus-visible:ring-2 focus-visible:ring-primary"
                >
                  {data.courses.map((item) => (
                    <option key={item.course_id} value={item.course_id}>
                      {label(item.course_id, item.course_code)}
                    </option>
                  ))}
                </select>
              </label>
            ) : (
              <p className="text-sm">{label(course.course_id, course.course_code)}</p>
            )}
            <p className="text-xs text-muted-foreground">
              {course.course_code} · Available course records
            </p>
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            <section className={card}>
              <h2 className="text-xs text-muted-foreground">
                Attendance rate{" "}
                <span
                  tabIndex={0}
                  aria-label="Recorded check-ins count regardless of verification status."
                  title="Recorded check-ins count regardless of verification status."
                  className="cursor-help rounded focus-visible:ring-2 focus-visible:ring-primary"
                >
                  ⓘ
                </span>
              </h2>
              <p className="mt-4 font-display text-3xl font-semibold">
                {noSessions
                  ? "No attendance data"
                  : availableNumber(rate)
                    ? `${Math.round(rate * 100)}%`
                    : "Not available"}
              </p>
              {!noSessions && availableNumber(rate) && (
                <div
                  role="progressbar"
                  aria-label="Attendance rate"
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={Math.round(rate * 100)}
                  className="mt-4 h-1.5 overflow-hidden rounded-full bg-primary/15"
                >
                  <div
                    className="h-full rounded-full bg-primary"
                    style={{ width: `${Math.max(0, Math.min(100, rate * 100))}%` }}
                  />
                </div>
              )}
            </section>
            <section className={card}>
              <h2 className="text-xs text-muted-foreground">Sessions checked in</h2>
              <p className="mt-4 font-display text-3xl font-semibold">
                {availableNumber(course.sessions_attended) &&
                availableNumber(course.total_sessions) ? (
                  <>
                    {course.sessions_attended}{" "}
                    <span className="text-base text-muted-foreground">
                      / {course.total_sessions}
                    </span>
                  </>
                ) : (
                  "Not available"
                )}
              </p>
              <p className="mt-4 text-xs text-muted-foreground">Checked in / counted sessions</p>
            </section>
            <section className={card}>
              <h2 className="text-xs text-muted-foreground">Average risk score</h2>
              <p className="mt-4 font-display text-3xl font-semibold">
                {availableNumber(course.average_risk_score) ? (
                  <>
                    {course.average_risk_score.toFixed(2)}{" "}
                    <span className="text-base text-muted-foreground">/ 1.00</span>
                  </>
                ) : (
                  "Not available"
                )}
              </p>
            </section>
          </div>
          <section className="min-w-0 overflow-hidden rounded-2xl border border-border bg-card/40 p-5">
            <div className="mb-5 flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-sm font-semibold">Recent check-ins</h2>
              <span className="text-xs text-muted-foreground">
                {result.records.length} records · {course.course_code}
              </span>
            </div>
            {result.ambiguous && (
              <p role="alert" className="mb-4 text-sm text-warning">
                Some records cannot be matched because multiple courses share this code. The API
                needs course_id on recent check-ins to identify them.
              </p>
            )}
            <div className="max-w-full overflow-x-auto">
              <table className="w-full min-w-[580px] text-left text-xs">
                <caption className="sr-only">Recent check-ins for {course.course_code}</caption>
                <thead className="text-muted-foreground">
                  <tr className="border-b border-border">
                    {["Session", "Course", "Check-in time", "Verification"].map(
                      (heading, index) => (
                        <th
                          key={heading}
                          scope="col"
                          className={`px-3 py-4 font-normal ${index === 0 ? "sticky left-0 z-10 bg-card" : ""}`}
                        >
                          {heading}
                        </th>
                      ),
                    )}
                  </tr>
                </thead>
                <tbody>
                  {result.records.map((item, index) => (
                    <tr
                      key={`${item.checked_in_at}-${item.session_name}-${index}`}
                      className="border-b border-border last:border-0"
                    >
                      <th scope="row" className="sticky left-0 z-10 bg-card px-3 py-5 font-medium">
                        {item.session_name}
                      </th>
                      <td className="px-3 py-5">{item.course_code}</td>
                      <td className="whitespace-nowrap px-3 py-5">
                        {formatSingaporeDateTime(item.checked_in_at, {
                          day: "numeric",
                          month: "short",
                          year: "numeric",
                          hour: "2-digit",
                          minute: "2-digit",
                          hour12: false,
                        })}
                      </td>
                      <td className="px-3 py-5">
                        <span
                          className={`rounded-md px-2 py-1 capitalize ${statusColors[item.status] ?? "bg-secondary text-foreground"}`}
                        >
                          {item.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {!result.records.length && (
              <p className="py-6 text-sm text-muted-foreground">No recent check-ins.</p>
            )}
          </section>
        </>
      )}
    </div>
  );
}
