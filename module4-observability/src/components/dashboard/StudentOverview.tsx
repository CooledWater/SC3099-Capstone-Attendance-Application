import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { fetchStudentOverview, type StudentOverview as Overview } from "@/lib/student-overview";
import { formatSingaporeDateTime } from "@/lib/time";

const panel = "rounded-2xl border border-border bg-glass p-5 sm:p-6";
const link = "text-sm text-primary underline-offset-4 hover:underline focus-visible:ring-2 focus-visible:ring-primary";
function useCard(section: "attendance" | "today" | "flagged", userId: string, courseId = "") {
  return useQuery({
    queryKey: ["student-overview", userId, section, section === "attendance" ? courseId : "all"],
    queryFn: ({ signal }) => fetchStudentOverview(section, courseId, signal),
    refetchInterval: 30000,
  });
}
function RequestState({ query }: { query: UseQueryResult<Overview> }) {
  if (query.isPending) return <p role="status" className="mt-5 text-sm text-muted-foreground">Loading...</p>;
  if (query.isError) return <p role="alert" className="mt-5 text-sm text-destructive">Could not load this card. <button className="underline" onClick={() => void query.refetch()}>Retry</button></p>;
  return null;
}
type Props = {
  userId: string; courseId: string; onCourseChange: (id: string) => void;
  onAttendance: (courseId: string, statuses: string[]) => void;
};
export function StudentOverviewCards({ userId, courseId, onCourseChange, onAttendance }: Props) {
  const attendance = useCard("attendance", userId, courseId);
  const today = useCard("today", userId);
  const flagged = useCard("flagged", userId);
  const metric = attendance.data?.attendance;
  const selected = metric?.course_id ?? "";
  const percentage = metric?.percentage;
  const percentText = percentage == null ? "—" : `${Math.round(percentage)}%`;
  const periodError = attendance.data?.period?.error;
  const nextSession = [...(today.data?.today?.sessions ?? [])]
    .filter(session => session.status === "scheduled")
    .sort((a, b) => Date.parse(a.scheduled_start) - Date.parse(b.scheduled_start))[0];
  return <div className="lg:col-span-12 space-y-5">
    <div className="grid gap-4 lg:grid-cols-[1.6fr_1fr]">
      <section className={`${panel} border-primary/40 bg-primary/5`} aria-labelledby="student-attendance-heading">
        <h2 id="student-attendance-heading" className="font-display text-lg font-semibold">My attendance</h2>
        <p className="mt-1 text-xs text-muted-foreground">Semester to date · Completed sessions</p>
        <RequestState query={attendance} />
        {attendance.data && !attendance.isError && <>
          <label className="mt-4 block w-full max-w-sm">
            <span className="sr-only">Attendance course</span>
            <select value={selected} disabled={!attendance.data.courses?.length}
              onChange={event => onCourseChange(event.target.value)} className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm">
              {!attendance.data.courses?.length && <option value="">No enrolled courses</option>}
              {attendance.data.courses?.map(course => <option key={course.id} value={course.id}>{course.code} · {course.name}</option>)}
            </select>
          </label>
          {periodError ? <p role="alert" className="mt-5 text-sm text-warning">{periodError}</p> : metric && <div className="mt-6 flex flex-wrap items-center gap-6">
            <div role="img" aria-label={`${percentText} attendance; ${metric.approved} of ${metric.eligible} completed sessions attended`} className="relative grid size-40 shrink-0 place-items-center">
              <svg viewBox="0 0 120 120" className="absolute inset-0 size-full -rotate-90" aria-hidden="true">
                <circle cx="60" cy="60" r="52" fill="none" stroke="currentColor" strokeWidth="10" className="text-secondary" />
                {percentage != null && <circle cx="60" cy="60" r="52" fill="none" stroke="currentColor" strokeWidth="10" pathLength="100" strokeDasharray={`${percentage} 100`} className="text-emerald-400" />}
              </svg>
              <div className="text-center"><p className="text-3xl font-semibold tabular-nums">{percentText}</p><p className="mt-1 text-xs text-muted-foreground">attendance</p></div>
            </div>
            <div className="min-w-40 flex-1">
              <p className="text-xl font-semibold">{metric.eligible ? `${metric.approved} of ${metric.eligible}` : "No completed sessions"}</p>
              {metric.eligible > 0 && <p className="mt-2 text-sm text-muted-foreground">completed sessions attended</p>}
              <p className="mt-3 text-xs text-muted-foreground">{metric.unresolved ? `${metric.unresolved} awaiting review` : "No records awaiting review"}</p>
            </div>
          </div>}
          <div className="mt-6 flex flex-wrap items-center justify-end gap-3 border-t border-border pt-4">
            {selected && !periodError && <a href="#student-history" className={link} onClick={event => { onAttendance(selected, []); }}>View attendance →</a>}
          </div>
        </>}
      </section>
      <div className="grid content-start gap-3">
        <section className="rounded-xl border border-emerald-400/15 bg-emerald-400/[0.04] p-4 sm:p-5">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-sm text-muted-foreground">Today's sessions</h2>
            <span className="grid size-8 place-items-center rounded-lg bg-emerald-400/10 text-emerald-300">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="size-4" aria-hidden="true"><rect x="3" y="5" width="18" height="16" rx="3" /><path d="M7 3v4M17 3v4M3 11h18M7 15h3M14 15h3" /></svg>
            </span>
          </div>
          <RequestState query={today} />
          {today.data?.today && !today.isError && <>
            <p className="mt-1 text-4xl font-semibold tabular-nums text-slate-100">{today.data.today.total}</p>
            {!today.data.today.total ? <p className="mt-3 text-xs text-muted-foreground">You’re all caught up today</p> : <>
              <div className="mt-3 flex flex-wrap gap-2 text-xs">
                <span className="rounded-md bg-emerald-400/10 px-2 py-1 text-emerald-200">Active <span className="ml-1 font-medium tabular-nums">{today.data.today.active}</span></span>
                <span className="rounded-md bg-secondary/70 px-2 py-1 text-muted-foreground">Upcoming <span className="ml-1 font-medium tabular-nums text-foreground">{today.data.today.upcoming}</span></span>
                {today.data.today.completed > 0 && <span className="rounded-md bg-secondary/70 px-2 py-1 text-muted-foreground">Completed <span className="ml-1 tabular-nums text-foreground">{today.data.today.completed}</span></span>}
              </div>
              {nextSession && <p className="mt-3 text-xs text-muted-foreground">Next session <span className="ml-1 text-foreground">{formatSingaporeDateTime(nextSession.scheduled_start, { hour: "numeric", minute: "2-digit", hour12: true })}</span></p>}
            </>}
          </>}
        </section>
        <section className="overflow-hidden rounded-xl border border-rose-400/15 bg-rose-400/[0.03]">
          <div className="px-4 pt-4 sm:px-5 sm:pt-5">
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-sm text-muted-foreground">Flagged</h2>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="size-4 text-rose-300/80" aria-hidden="true"><path d="M10.3 4.3a2 2 0 0 1 3.4 0l7.6 13a2 2 0 0 1-1.7 3H4.4a2 2 0 0 1-1.7-3zM12 9v4M12 16v1" /></svg>
            </div>
          <RequestState query={flagged} />
          {flagged.data?.flagged && !flagged.isError && <>
            <p className="mt-2 text-4xl font-semibold tabular-nums text-rose-300">{flagged.data.flagged.total}</p>
            <div className="mt-3 pb-4">
              <div role="img" aria-label={`${flagged.data.flagged.appealed} appeals pending, ${flagged.data.flagged.flagged} flagged records`}
                className="flex h-2 overflow-hidden rounded-full bg-secondary/80">
                {flagged.data.flagged.total > 0 && <>
                  <span className="h-full bg-orange-400" style={{ width: `${flagged.data.flagged.appealed / flagged.data.flagged.total * 100}%` }} />
                  <span className="h-full bg-red-400" style={{ width: `${flagged.data.flagged.flagged / flagged.data.flagged.total * 100}%` }} />
                </>}
              </div>
              <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                <span className="inline-flex items-center gap-1.5"><span className="size-1.5 rounded-full bg-orange-400" aria-hidden="true" />Appealed {flagged.data.flagged.appealed}</span>
                <span className="inline-flex items-center gap-1.5"><span className="size-1.5 rounded-full bg-red-400" aria-hidden="true" />Flagged {flagged.data.flagged.flagged}</span>
              </div>
            </div>
          </>}
          </div>
          {flagged.data?.flagged && !flagged.isError && <footer className="border-t border-border/60 px-4 py-3 sm:px-5">
            <a href="#student-history" className="text-xs text-foreground underline-offset-4 hover:underline focus-visible:ring-2 focus-visible:ring-primary" onClick={() => onAttendance("all", ["flagged", "appealed"])}>View records →</a>
          </footer>}
        </section>
      </div>
    </div>
  </div>;
}
