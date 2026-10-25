import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { StudentOverviewCards } from "./StudentOverview";
import { CourseHistory } from "./CourseHistory";
import { LiveActivity } from "./LiveActivity";
import { MyDevicesPanel } from "./MyDevicesPanel";
import { fetchMyCheckIns, fetchMyEnrollments, toRows } from "@/lib/attendance";
import { formatSingaporeDateTime } from "@/lib/time";

export function StudentView({ userId = "" }: { userId?: string } = {}) {
  const [tab, setTab] = useState<"dashboard" | "devices">("dashboard");
  const [overviewCourse, setOverviewCourse] = useState("");
  const [historyFilter, setHistoryFilter] = useState({ courseId: "all", statuses: [] as string[], revision: 0 });
  function showHistory(courseId: string, statuses: string[]) {
    setHistoryFilter(previous => ({ courseId, statuses, revision: previous.revision + 1 }));
  }
  const q = useQuery({
    queryKey: ["my-check-ins", userId, "summary"],
    queryFn: fetchMyCheckIns,
    refetchInterval: 30000,
  });
  const enrollments = useQuery({
    queryKey: ["my-enrollments", userId],
    refetchInterval: 30000,
    queryFn: fetchMyEnrollments,
  });
  const rows = useMemo(() => toRows(q.data ?? []), [q.data]);

  return (
    <>
      <div className="mb-4 flex flex-wrap items-center gap-1 rounded-full border border-border bg-glass p-1">
        {(["dashboard", "devices"] as const).map((value) => (
          <button
            key={value}
            type="button"
            aria-pressed={tab === value}
            onClick={() => setTab(value)}
            className={`rounded-full px-3.5 py-1.5 text-xs transition ${tab === value ? "bg-primary/20 text-primary" : "text-muted-foreground hover:text-foreground"}`}
          >
            {value === "dashboard" ? "Overview" : "My devices"}
          </button>
        ))}
      </div>
      {tab === "devices" ? <MyDevicesPanel /> : <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        <StudentOverviewCards userId={userId} courseId={overviewCourse} onCourseChange={setOverviewCourse} onAttendance={showHistory} />
        <div id="student-history" className="lg:col-span-8 scroll-mt-4">
          <CourseHistory key={historyFilter.revision} rows={rows} enrolledCourses={enrollments.data ?? []} initialCourseId={historyFilter.courseId} initialStatuses={historyFilter.statuses} />
        </div>
        <LiveActivity rows={rows} student />
        <section className="lg:col-span-12 rounded-2xl border border-primary/40 bg-primary/5 p-5" aria-labelledby="student-enrollments-heading">
          <h2 id="student-enrollments-heading" className="font-display text-base text-foreground">
            My course enrollments
          </h2>
          <p className="mt-1 text-xs text-muted-foreground">All courses you are currently enrolled in.</p>
          {enrollments.isPending ? (
            <p role="status" className="mt-4 text-sm text-muted-foreground">Loading your course enrollments...</p>
          ) : enrollments.isError ? (
            <div role="alert" className="mt-4 rounded-xl border border-warning/30 bg-warning/10 p-4 text-sm text-warning">
              Could not load your course enrollments.
              <button type="button" className="ml-3 underline" onClick={() => void enrollments.refetch()}>Retry</button>
            </div>
          ) : !enrollments.data?.length ? (
            <p className="mt-4 text-sm text-muted-foreground">You are not currently enrolled in any courses.</p>
          ) : (
            <div className="mt-4 overflow-x-auto">
              <table className="w-full min-w-[650px] text-left text-sm">
                <thead>
                  <tr className="text-xs uppercase tracking-wide text-muted-foreground">
                    {["Course code", "Course name", "Semester", "Instructor", "Enrolled on"].map((label) => (
                      <th key={label} scope="col" className="pb-3 pr-4 font-medium">{label}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {enrollments.data.map((enrollment) => (
                    <tr key={enrollment.course_id} className="border-t border-border/60">
                      <td className="py-3 pr-4 font-medium">{enrollment.course_code}</td>
                      <td className="py-3 pr-4">{enrollment.course_name}</td>
                      <td className="py-3 pr-4">{enrollment.semester ?? "Not set"}</td>
                      <td className="py-3 pr-4">{enrollment.instructor_name ?? "Not assigned"}</td>
                      <td className="py-3 pr-4">{enrollment.enrolled_at ? `${formatSingaporeDateTime(enrollment.enrolled_at)} SGT` : "Not available"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>}
    </>
  );
}
