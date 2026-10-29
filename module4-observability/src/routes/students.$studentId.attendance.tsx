import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/hooks/useAuth";
import { fetchMyAssignedCourses } from "@/lib/attendance";
import {
  AttendanceSkeleton,
  StudentAttendanceDetails,
} from "@/components/dashboard/StudentAttendanceDetails";

export const Route = createFileRoute("/students/$studentId/attendance")({
  validateSearch: (search: Record<string, unknown>) => ({
    courseId: typeof search["courseId"] === "string" ? search["courseId"] : "",
    from: search["from"] === "overview" ? ("overview" as const) : ("enrollments" as const),
  }),
  head: () => ({
    meta: [{ title: "Student attendance" }, { name: "robots", content: "noindex,nofollow" }],
  }),
  component: StudentAttendancePage,
});

function StudentAttendancePage() {
  const { studentId } = Route.useParams();
  const { courseId, from } = Route.useSearch();
  const { user, loading } = useAuth();
  const permitted = user?.role === "instructor" || user?.role === "admin";
  const courses = useQuery({
    queryKey: ["courses", user?.id],
    queryFn: fetchMyAssignedCourses,
    enabled: permitted,
  });
  return (
    <main className="min-h-screen bg-background px-4 py-8 text-foreground sm:px-6">
      <div className="mx-auto w-full min-w-0 max-w-4xl space-y-7">
        <Link
          to="/"
          className="inline-block rounded text-sm text-muted-foreground hover:text-primary focus-visible:ring-2 focus-visible:ring-primary"
          onClick={() => {
            if (!user) return;
            try {
              const view = user.role === "admin" ? "admin" : "instructor";
              sessionStorage.setItem(`${view}:${user.id}:tab`, from);
              if (courseId) sessionStorage.setItem(`${view}:${user.id}:course`, courseId);
            } catch {
              /* Return navigation also works without storage. */
            }
          }}
        >
          ← Back to {from === "overview" ? "Overview" : "Enrollments"}
        </Link>
        {loading ? (
          <AttendanceSkeleton />
        ) : !user ? (
          <div role="alert" className="rounded-2xl border border-border p-6">
            <p>Sign in to view student attendance.</p>
            <Link to="/auth" className="mt-3 inline-block text-primary underline">
              Sign in
            </Link>
          </div>
        ) : !permitted ? (
          <p role="alert" className="rounded-2xl border border-destructive/40 p-6 text-destructive">
            Only instructors and administrators can view student attendance.
          </p>
        ) : (
          <StudentAttendanceDetails
            key={`${user.id}:${studentId}`}
            studentId={studentId}
            viewerId={user.id}
            initialCourseId={courseId}
            courses={courses.data ?? []}
          />
        )}
      </div>
    </main>
  );
}
