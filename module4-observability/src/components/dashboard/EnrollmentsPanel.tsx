import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import type { CourseRow } from "@/lib/attendance";
import {
  bulkEnroll,
  fetchInvitations,
  resendInvitation,
  type InvitationResult,
  enrollStudent,
  fetchRoster,
  parseEnrollmentEmails,
  removeEnrollment,
  type BulkResult,
  type RosterStudent,
} from "@/lib/enrollments";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogCancel,
} from "@/components/ui/alert-dialog";

const input =
  "mt-1 w-full rounded-lg border border-border bg-secondary/40 px-3 py-2 text-sm text-foreground outline-none focus:ring-2 focus:ring-primary/60";
const button =
  "rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition hover:opacity-90 focus-visible:ring-2 focus-visible:ring-primary disabled:opacity-50";
const secondary =
  "rounded-lg border border-border px-3 py-2 text-sm focus-visible:ring-2 focus-visible:ring-primary disabled:opacity-50";

export function EnrollmentsPanel({
  courses,
  loading,
  error,
  selectedCourseId,
  onCourseChange,
  canManage,
}: {
  courses: CourseRow[];
  loading: boolean;
  error: boolean;
  selectedCourseId: string;
  onCourseChange: (id: string) => void;
  canManage: boolean;
}) {
  const qc = useQueryClient();
  const course = courses.find((item) => item.id === selectedCourseId) ?? courses[0];
  const courseId = course?.id ?? "";
  useEffect(() => {
    if (courseId && selectedCourseId !== courseId) onCourseChange(courseId);
  }, [courseId, selectedCourseId, onCourseChange]);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("all");
  const [open, setOpen] = useState(false);
  const [target, setTarget] = useState<RosterStudent | null>(null);
  const [removing, setRemoving] = useState(false);
  const removeLock = useRef(false);
  const [removeError, setRemoveError] = useState("");
  const roster = useQuery({
    queryKey: ["enrollment-roster", courseId],
    queryFn: ({ signal }) => fetchRoster(courseId, "all", "", signal),
    enabled: Boolean(courseId),
  });
  // The API returns the complete roster, so searching needs no network round trip.
  const term = search.trim().toLowerCase();
  const students = (roster.data?.students ?? []).filter(
    (student) =>
      (status === "all" || student.is_active === (status === "true")) &&
      (!term || student.student_name.toLowerCase().includes(term) ||
        student.student_email.toLowerCase().includes(term)),
  );
  const invitations = useQuery({
    queryKey: ["enrollment-invitations", courseId],
    queryFn: () => fetchInvitations(courseId),
    enabled: Boolean(courseId && canManage),
    refetchInterval: (query) =>
      query.state.data?.items?.some((item) =>
        ["queued", "sending"].includes(item.invitation_status),
      )
        ? 3000
        : 30000,
  });
  const invitationItems = invitations.data?.items ?? [];
  const [resending, setResending] = useState("");
  const resendLock = useRef(false);
  const [invitationError, setInvitationError] = useState("");
  async function resend(email: string) {
    if (resendLock.current) return;
    resendLock.current = true;
    setResending(email);
    try {
      await resendInvitation(courseId, email);
      await invitations.refetch();
    } finally {
      resendLock.current = false;
      setResending("");
    }
  }
  async function refresh() {
    await Promise.all([
      qc.invalidateQueries({ queryKey: ["enrollment-roster", courseId] }),
      qc.invalidateQueries({ queryKey: ["enrollment-invitations", courseId] }),
      qc.invalidateQueries({ queryKey: ["course-enrollment-count", courseId] }),
      qc.invalidateQueries({ queryKey: ["sessions"] }),
      qc.invalidateQueries({ queryKey: ["stats"] }),
    ]);
  }
  async function remove() {
    if (!target || removeLock.current) return;
    removeLock.current = true;
    setRemoving(true);
    setRemoveError("");
    try {
      await removeEnrollment(target.id);
      setTarget(null);
      toast.success("Enrollment deactivated.");
      await refresh();
    } catch (failure) {
      setRemoveError(failure instanceof Error ? failure.message : "Could not remove enrollment.");
    } finally {
      removeLock.current = false;
      setRemoving(false);
    }
  }
  if (loading)
    return (
      <p role="status" className="p-5 text-muted-foreground">
        Loading courses...
      </p>
    );
  if (error)
    return (
      <p role="alert" className="p-5 text-destructive">
        Could not load your accessible courses. Refresh to retry.
      </p>
    );
  if (!course)
    return (
      <div className="rounded-2xl border border-border bg-glass p-6">
        <h2 className="text-xl font-semibold">Enrollments</h2>
        <p className="mt-2 text-muted-foreground">No courses are assigned to your account.</p>
      </div>
    );
  return (
    <section className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="font-display text-xl font-semibold">Enrollments</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Manage who is enrolled in each course.
          </p>
        </div>
        {canManage && (
          <button className={button} onClick={() => setOpen(true)}>
            + Add students
          </button>
        )}
      </div>
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-border bg-glass p-5">
        <label className="text-xs text-muted-foreground">
          Course
          <select
            aria-label="Enrollment course"
            value={courseId}
            className={input}
            onChange={(event) => {
              onCourseChange(event.target.value);
              setSearch("");
              setTarget(null);
            }}
          >
            {courses.map((item) => (
              <option key={item.id} value={item.id}>
                {item.code} - {item.name}
              </option>
            ))}
          </select>
        </label>
        <div className="text-right">
          <p className="text-2xl font-semibold">{roster.data?.total_records ?? "..."}</p>
          <p className="text-xs text-muted-foreground">Total enrollment records</p>
        </div>
      </div>
      {invitationError && (
        <p role="alert" className="text-sm text-destructive">
          {invitationError}
        </p>
      )}
      <div className="rounded-2xl border border-border bg-glass p-5">
        <div className="flex flex-wrap justify-between gap-2">
          <h3 className="font-semibold">Student roster</h3>
          {roster.data && (
            <p className="text-xs text-muted-foreground">
              {roster.data.active_count} active · {roster.data.inactive_count} inactive
            </p>
          )}
        </div>
        <div className="my-5 flex flex-wrap items-end gap-3">
          <label className="min-w-0 flex-1 text-xs text-muted-foreground">
            Search students
            <input
              className={input}
              value={search}
              placeholder="Search by name or email"
              onChange={(event) => setSearch(event.target.value)}
            />
          </label>
          <label className="text-xs text-muted-foreground">
            Enrollment status
            <select
              className={input}
              value={status}
              onChange={(event) => setStatus(event.target.value)}
            >
              <option value="all">All</option>
              <option value="true">Active</option>
              <option value="false">Inactive</option>
            </select>
          </label>
        </div>
        {roster.isError ? (
          <p role="alert" className="text-sm text-destructive">
            {roster.error instanceof Error ? roster.error.message : "Could not load roster."}{" "}
            <button className="underline" onClick={() => void roster.refetch()}>
              Retry
            </button>
          </p>
        ) : roster.isLoading ? (
          <p role="status" className="py-5 text-sm text-muted-foreground">
            Loading roster...
          </p>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[700px] text-left text-sm">
                <thead>
                  <tr className="border-b border-border text-xs text-muted-foreground">
                    {["Student", "Email", "Face enrolled", "Status", ...(canManage ? ["Action"] : [])].map(
                      (label) => (
                        <th key={label} className="px-2 py-3 font-medium">
                          {label}
                        </th>
                      ),
                    )}
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {students.map((student) => (
                    <tr key={student.id}>
                      <td className="px-2 py-5 font-medium">{student.student_name}</td>
                      <td className="px-2 py-5">{student.student_email}</td>
                      <td className="px-2 py-5">
                        {student.face_enrolled ? (
                          <span
                            className="text-lg font-semibold text-accent"
                            aria-label="Face enrolled"
                            title="Face enrolled"
                          >
                            ✓
                          </span>
                        ) : (
                          <span
                            className="text-lg font-semibold text-destructive"
                            aria-label="Face not enrolled"
                            title="Face not enrolled"
                          >
                            ✕
                          </span>
                        )}
                      </td>
                      <td className="px-2 py-5">
                        <span
                          className={`rounded-full px-2 py-1 text-xs ${student.is_active ? "bg-accent/10 text-accent" : "bg-secondary text-muted-foreground"}`}
                        >
                          {student.is_active ? "Active" : "Inactive"}
                        </span>
                      </td>
                      {canManage && (
                        <td className="px-2 py-5">
                          {student.is_active ? (
                            <button
                              className="text-destructive underline-offset-4 hover:underline focus-visible:ring-2 focus-visible:ring-primary"
                              onClick={() => {
                                setTarget(student);
                                setRemoveError("");
                              }}
                            >
                              Remove
                            </button>
                          ) : (
                            <span className="text-xs text-muted-foreground">Already removed</span>
                          )}
                          {student.is_active &&
                            invitationItems.some(
                              (item) =>
                                item.email === student.student_email && item.invitation_pending,
                            ) && (
                              <div className="mt-2 text-xs">
                                <p className="text-muted-foreground">
                                  Invitation:{" "}
                                  {
                                    invitationItems.find(
                                      (item) => item.email === student.student_email,
                                    )?.invitation_status
                                  }
                                </p>
                                <button
                                  type="button"
                                  className="mt-1 text-primary underline"
                                  disabled={Boolean(resending)}
                                  onClick={() => {
                                    setInvitationError("");
                                    void resend(student.student_email).catch((failure) =>
                                      setInvitationError(
                                        failure instanceof Error
                                          ? failure.message
                                          : "Could not resend invitation.",
                                      ),
                                    );
                                  }}
                                >
                                  {resending === student.student_email
                                    ? "Queuing..."
                                    : "Resend invitation"}
                                </button>
                              </div>
                            )}
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {students.length === 0 && (
              <p className="py-6 text-sm text-muted-foreground">
                {search || status !== "all"
                  ? "No students match these filters."
                  : "No students are enrolled in this course yet."}
              </p>
            )}
            <p className="mt-4 border-t border-border pt-4 text-xs text-muted-foreground">
              Showing {students.length} of {roster.data?.total_records ?? 0}{" "}
              enrollment records
            </p>
          </>
        )}
      </div>
      {canManage && (
        <AddStudents
          key={courseId}
          course={course}
          open={open}
          setOpen={setOpen}
          refresh={refresh}
          invitations={invitationItems}
          onResend={resend}
          resending={resending}
        />
      )}
      <AlertDialog
        open={target !== null}
        onOpenChange={(value) => {
          if (!value && !removing) setTarget(null);
        }}
      >
        <AlertDialogContent className="border-border bg-card text-card-foreground">
          <AlertDialogHeader>
            <AlertDialogTitle>Remove enrollment?</AlertDialogTitle>
            <AlertDialogDescription>
              {target?.student_name} · {target?.student_email} · {course.code}. This deactivates the
              enrollment. Past attendance records are kept, and the student can be enrolled again.
            </AlertDialogDescription>
          </AlertDialogHeader>
          {removeError && (
            <p role="alert" className="text-sm text-destructive">
              {removeError}
            </p>
          )}
          <AlertDialogFooter>
            <AlertDialogCancel disabled={removing}>Cancel</AlertDialogCancel>
            <button
              className={`${button} bg-destructive text-destructive-foreground`}
              disabled={removing}
              onClick={() => void remove()}
            >
              {removing ? "Removing..." : "Remove"}
            </button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  );
}

function AddStudents({
  course,
  open,
  setOpen,
  refresh,
  invitations,
  onResend,
  resending,
}: {
  course: CourseRow;
  open: boolean;
  setOpen: (value: boolean) => void;
  refresh: () => Promise<void>;
  invitations: InvitationResult[];
  onResend: (email: string) => Promise<void>;
  resending: string;
}) {
  const [mode, setMode] = useState("single");
  const [studentEmail, setStudentEmail] = useState("");
  const [text, setText] = useState("");
  const [createAccounts, setCreateAccounts] = useState(false);
  const [busy, setBusy] = useState(false);
  const lock = useRef(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [result, setResult] = useState<BulkResult | null>(null);
  const parsed = parseEnrollmentEmails(text);
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (lock.current) return;
    lock.current = true;
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      if (mode === "single") {
        const email = studentEmail.trim();
        if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
          setError("Enter a valid student email address.");
          return;
        }
        await enrollStudent(course.id, email);
        setStudentEmail("");
        setSuccess("Student enrolled successfully.");
      } else {
        const response = await bulkEnroll(course.id, parsed.emails, createAccounts);
        setResult(response);
        const failed = response.details.filter(
          (row) => !["enrolled", "created", "already_enrolled"].includes(row.status),
        );
        setText(failed.map((row) => row.email).join("\n"));
        setSuccess(
          failed.length
            ? "Completed. Unresolved addresses remain below for correction."
            : "Bulk enrollment completed.",
        );
      }
      await refresh();
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Enrollment failed.");
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }
  return (
    <Dialog
      open={open}
      onOpenChange={(value) => {
        if (!busy) setOpen(value);
      }}
    >
      <DialogContent
        className="max-h-[90vh] overflow-y-auto border-border bg-card text-card-foreground sm:max-w-2xl"
        onEscapeKeyDown={(event) => {
          if (busy) event.preventDefault();
        }}
      >
        <DialogHeader>
          <DialogTitle>Add students</DialogTitle>
          <DialogDescription>
            {course.code} - {course.name}
          </DialogDescription>
        </DialogHeader>
        <div className="flex gap-2">
          {["single", "bulk"].map((value) => (
            <button
              key={value}
              className={`${secondary} ${mode === value ? "border-primary bg-primary/15 text-primary" : ""}`}
              aria-pressed={mode === value}
              disabled={busy}
              onClick={() => {
                setMode(value);
                setError("");
                setSuccess("");
              }}
            >
              {value === "single" ? "Single student" : "Bulk enrollment"}
            </button>
          ))}
        </div>
        <form onSubmit={(event) => void submit(event)} className="space-y-4">
          {mode === "single" ? (
            <label className="block text-xs text-muted-foreground">
              Student email address
              <input
                type="email"
                required
                className={input}
                value={studentEmail}
                disabled={busy}
                onChange={(event) => setStudentEmail(event.target.value)}
                placeholder="student@example.edu"
              />
            </label>
          ) : (
            <>
              <label className="block text-xs text-muted-foreground">
                Student email addresses
                <textarea
                  className={`${input} min-h-32`}
                  value={text}
                  disabled={busy}
                  onChange={(event) => setText(event.target.value)}
                  required
                />
                <span className="mt-2 block">
                  One address per line, or separate with commas. {parsed.emails.length} unique
                  addresses.
                </span>
              </label>
              {parsed.invalid.length > 0 && (
                <p role="alert" className="text-sm text-destructive">
                  Invalid addresses: {parsed.invalid.join(", ")}
                </p>
              )}
              <label className="flex items-start gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={createAccounts}
                  disabled={busy}
                  onChange={(event) => setCreateAccounts(event.target.checked)}
                />
                <span>
                  Create accounts and email invitations
                  <span className="block text-xs text-muted-foreground">
                    New students receive a single-use link to set their password. Leave unchecked to
                    enroll existing accounts only.
                  </span>
                </span>
              </label>
            </>
          )}
          {error && (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          )}
          {success && (
            <p role="status" className="text-sm text-accent">
              {success}
            </p>
          )}
          {mode === "bulk" && result && (
            <div className="rounded-lg border border-border p-3 text-sm">
              <p>
                {result.enrolled} enrolled · {result.created} accounts created ·{" "}
                {result.already_enrolled} already enrolled · {result.not_found} unresolved
              </p>
              <ul className="mt-2 max-h-40 overflow-y-auto">
                {result.details.map((row) => (
                  <li key={row.email} className="break-all py-1">
                    {row.email}: {row.status}
                    {row.error ? ` - ${row.error}` : ""}
                    {(invitations.find((item) => item.email === row.email)?.invitation_status ??
                      row.invitation_status) && (
                      <span className="ml-2 text-muted-foreground">
                        Invitation:{" "}
                        {invitations.find((item) => item.email === row.email)?.invitation_status ??
                          row.invitation_status}
                      </span>
                    )}
                    {(invitations.find((item) => item.email === row.email)?.invitation_pending ??
                      row.invitation_pending) && (
                      <button
                        type="button"
                        className="ml-2 text-primary underline"
                        disabled={Boolean(resending)}
                        onClick={() =>
                          void onResend(row.email).catch((failure) =>
                            setError(
                              failure instanceof Error
                                ? failure.message
                                : "Could not resend invitation.",
                            ),
                          )
                        }
                      >
                        {resending === row.email ? "Queuing..." : "Resend invitation"}
                      </button>
                    )}
                    {invitations.find((item) => item.email === row.email)?.invitation_error && (
                      <span className="block text-destructive">
                        {invitations.find((item) => item.email === row.email)?.invitation_error}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}
          <div className="flex justify-end">
            <button
              className={button}
              disabled={
                busy ||
                (mode === "single"
                  ? !studentEmail.trim()
                  : !parsed.emails.length || parsed.invalid.length > 0)
              }
            >
              {busy ? "Enrolling..." : mode === "single" ? "Enroll student" : "Enroll students"}
            </button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
