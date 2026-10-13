import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { X } from "lucide-react";
import { api } from "@/lib/api";
import {
  formatSingaporeDateTime,
  parseApiDateTime,
  parseSingaporeDateTimeLocal,
  toSingaporeDateTimeLocal,
} from "@/lib/time";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  checkInsToCsv,
  downloadCsv,
  fetchSessions,
  fetchCourses,
  statusText,
  type SessionRow,
} from "@/lib/attendance";
import type { CheckInRow } from "./AttendanceTable";
import { statusStyle } from "./AttendanceTable";

export function SessionsPanel({
  rows,
  canCreate,
  courseIds,
  currentUserId,
}: {
  rows: CheckInRow[];
  canCreate: boolean;
  courseIds?: Set<string>;
  currentUserId?: string;
}) {
  const qc = useQueryClient();
  const sessions = useQuery({ queryKey: ["sessions"], queryFn: fetchSessions });
  const courses = useQuery({
    queryKey: ["courses"],
    queryFn: fetchCourses,
  });
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [savingSessionId, setSavingSessionId] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<SessionRow | null>(null);
  const [form, setForm] = useState({
    course_id: "",
    room: "",
    starts_at: "",
    geofence_lat: "",
    geofence_lng: "",
    geofence_radius_m: "100",
  });
  const [editForm, setEditForm] = useState({
    course_id: "",
    room: "",
    starts_at: "",
    geofence_lat: "",
    geofence_lng: "",
    geofence_radius_m: "100",
  });
  const selectedCourseEnrollmentCount = useQuery({
    queryKey: ["course-enrollment-count", editForm.course_id],
    queryFn: () =>
      api.request<{ total_enrolled: number }>(
        `/enrollments/course/${encodeURIComponent(editForm.course_id)}`,
      ),
    enabled: Boolean(editingSessionId && editForm.course_id),
  });

  const list = useMemo(() => {
    const all = (sessions.data ?? []) as SessionRow[];
    return courseIds ? all.filter((s) => courseIds.has(s.course_id)) : all;
  }, [sessions.data, courseIds]);

  const active = list.filter((s) => s.is_active).length;
  const availableCourses = (courses.isSuccess ? courses.data : []).filter(
    (course) => !currentUserId || course.instructor_id === currentUserId,
  );
  const bySession = useMemo(() => {
    const m = new Map<string, CheckInRow[]>();
    rows.forEach((r) => m.set(r.sessionId, [...(m.get(r.sessionId) ?? []), r]));
    return m;
  }, [rows]);

  async function createSession(e: React.FormEvent) {
    e.preventDefault();
    if (
      (currentUserId && !availableCourses.some((course) => course.id === form.course_id)) ||
      (courseIds && !courseIds.has(form.course_id))
    ) {
      toast.error("Choose a course assigned to your account.");
      return;
    }
    if (!form.course_id || !form.room || !form.starts_at) {
      toast.error("Course, room and start time are required.");
      return;
    }
    setSaving(true);
    try {
      const scheduledStart = parseSingaporeDateTimeLocal(form.starts_at);
      if (!scheduledStart) {
        toast.error("Enter a valid session start time.");
        return;
      }
      await api.request("/sessions/", {
        method: "POST",
        body: JSON.stringify({
          course_id: form.course_id,
          name: `${form.room} session`,
          session_type: "lecture",
          scheduled_start: scheduledStart.toISOString(),
          scheduled_end: new Date(scheduledStart.getTime() + 60 * 60 * 1000).toISOString(),
          venue_name: form.room,
          venue_latitude: form.geofence_lat ? Number(form.geofence_lat) : null,
          venue_longitude: form.geofence_lng ? Number(form.geofence_lng) : null,
          geofence_radius_meters: Number(form.geofence_radius_m) || 100,
        }),
      });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not create session.");
      return;
    } finally {
      setSaving(false);
    }
    toast.success("Session created.");
    setOpen(false);
    setForm({ ...form, room: "", starts_at: "" });
    qc.invalidateQueries({ queryKey: ["sessions"] });
  }

  function startEditing(session: SessionRow) {
    setEditForm({
      course_id: session.course_id,
      room: session.room === "Not set" ? "" : session.room,
      starts_at: toSingaporeDateTimeLocal(session.starts_at),
      geofence_lat: session.geofence_lat == null ? "" : String(session.geofence_lat),
      geofence_lng: session.geofence_lng == null ? "" : String(session.geofence_lng),
      geofence_radius_m: String(session.geofence_radius_m),
    });
    setEditingSessionId(session.id);
  }

  async function updateSession(event: React.FormEvent<HTMLFormElement>, session: SessionRow) {
    event.preventDefault();
    if (!currentUserId || session.instructor_id !== currentUserId) {
      toast.error("Only the instructor who created this session can edit it.");
      return;
    }
    if (
      session.status !== "scheduled" ||
      !editForm.course_id ||
      !editForm.room.trim() ||
      !editForm.starts_at
    ) {
      toast.error("Choose a course, room and start time for this scheduled session.");
      return;
    }
    const scheduledStart = parseSingaporeDateTimeLocal(editForm.starts_at);
    const previousStart = parseApiDateTime(session.starts_at).getTime();
    if (!scheduledStart || !Number.isFinite(previousStart)) {
      toast.error("Enter a valid session start time.");
      return;
    }
    const shiftTime = (value: string) => {
      const timestamp = parseApiDateTime(value).getTime();
      if (!Number.isFinite(timestamp)) {
        throw new Error("Session timing data is invalid.");
      }
      return new Date(timestamp + scheduledStart.getTime() - previousStart).toISOString();
    };

    setSavingSessionId(session.id);
    try {
      const updated = await api.request<{ course_id: string }>(
        `/sessions/${encodeURIComponent(session.id)}`,
        {
          method: "PATCH",
          body: JSON.stringify({
            course_id: editForm.course_id,
            name: `${editForm.room.trim()} session`,
            scheduled_start: scheduledStart.toISOString(),
            scheduled_end: shiftTime(session.ends_at),
            checkin_opens_at: shiftTime(session.checkin_opens_at),
            checkin_closes_at: shiftTime(session.checkin_closes_at),
            venue_name: editForm.room.trim(),
            venue_latitude: editForm.geofence_lat ? Number(editForm.geofence_lat) : null,
            venue_longitude: editForm.geofence_lng ? Number(editForm.geofence_lng) : null,
            geofence_radius_meters: Number(editForm.geofence_radius_m) || 100,
          }),
        },
      );
      if (updated.course_id !== editForm.course_id) {
        await qc.invalidateQueries({ queryKey: ["sessions"] });
        await qc.invalidateQueries({ queryKey: ["check-ins"] });
        toast.error(
          "The backend did not apply the course change. Other edits may have been saved.",
        );
        return;
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not update session.");
      return;
    } finally {
      setSavingSessionId(null);
    }
    toast.success("Session updated.");
    setEditingSessionId(null);
    await qc.invalidateQueries({ queryKey: ["sessions"] });
    await qc.invalidateQueries({ queryKey: ["check-ins"] });
  }

  async function activateSession(session: SessionRow) {
    if (
      !currentUserId ||
      session.instructor_id !== currentUserId ||
      session.status !== "scheduled" ||
      savingSessionId
    ) {
      return;
    }
    setSavingSessionId(session.id);
    try {
      const updated = await api.request<{ status: string }>(
        `/sessions/${encodeURIComponent(session.id)}`,
        {
          method: "PATCH",
          body: JSON.stringify({ status: "active" }),
        },
      );
      if (updated.status !== "active") {
        throw new Error("The backend did not activate this session.");
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not activate session.");
      return;
    } finally {
      setSavingSessionId(null);
    }
    toast.success("Session activated.");
    await qc.invalidateQueries({ queryKey: ["sessions"] });
    await qc.invalidateQueries({ queryKey: ["check-ins"] });
  }

  async function deleteSession(session: SessionRow) {
    if (
      !currentUserId ||
      session.instructor_id !== currentUserId ||
      session.status !== "scheduled" ||
      savingSessionId
    ) {
      return;
    }

    setSavingSessionId(session.id);
    try {
      await api.request<void>(`/sessions/${encodeURIComponent(session.id)}`, {
        method: "DELETE",
      });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not delete session.");
      return;
    } finally {
      setSavingSessionId(null);
    }

    toast.success("Session deleted.");
    setDeleteTarget(null);
    if (editingSessionId === session.id) setEditingSessionId(null);
    if (expanded === session.id) setExpanded(null);
    await qc.invalidateQueries({ queryKey: ["sessions"] });
    await qc.invalidateQueries({ queryKey: ["check-ins"] });
  }

  const input =
    "w-full rounded-lg border border-border bg-secondary/40 px-3 py-2 text-sm text-foreground outline-none focus:border-primary/50";

  return (
    <div className="mt-4 animate-rise rounded-2xl border border-border bg-glass">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-5 py-4">
        <div>
          <p className="font-display text-sm font-medium text-card-foreground">Sessions</p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {list.length} total · {active} active · {list.length - active} inactive
          </p>
          {currentUserId && (
            <p className="mt-1 text-[11px] text-muted-foreground">
              Only scheduled sessions can be deleted. Active sessions must be closed or cancelled.
            </p>
          )}
        </div>
        {canCreate && (!currentUserId || availableCourses.length > 0) && (
          <button
            onClick={() => setOpen((v) => !v)}
            className="rounded-full bg-gradient-to-r from-primary to-accent px-3 py-1.5 text-xs font-medium text-primary-foreground transition hover:brightness-110"
          >
            {open ? "Cancel" : "New session"}
          </button>
        )}
      </div>

      {canCreate && (!currentUserId || availableCourses.length > 0) && open && (
        <form
          onSubmit={createSession}
          className="grid gap-3 border-b border-border px-5 py-4 sm:grid-cols-2 lg:grid-cols-4"
        >
          <label className="text-xs text-muted-foreground">
            Course
            <select
              className={`${input} mt-1`}
              value={form.course_id}
              onChange={(e) => setForm({ ...form, course_id: e.target.value })}
            >
              <option value="">Select course</option>
              {availableCourses.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.code} · {c.name}
                </option>
              ))}
            </select>
          </label>
          <label className="text-xs text-muted-foreground">
            Room
            <input
              className={`${input} mt-1`}
              value={form.room}
              onChange={(e) => setForm({ ...form, room: e.target.value })}
              placeholder="Hall B-204"
            />
          </label>
          <label className="text-xs text-muted-foreground">
            Starts at (Singapore time)
            <input
              type="datetime-local"
              className={`${input} mt-1`}
              value={form.starts_at}
              onChange={(e) => setForm({ ...form, starts_at: e.target.value })}
            />
          </label>
          <label className="text-xs text-muted-foreground">
            Geofence latitude
            <input
              className={`${input} mt-1`}
              value={form.geofence_lat}
              onChange={(e) => setForm({ ...form, geofence_lat: e.target.value })}
              placeholder="1.296600"
            />
          </label>
          <label className="text-xs text-muted-foreground">
            Geofence longitude
            <input
              className={`${input} mt-1`}
              value={form.geofence_lng}
              onChange={(e) => setForm({ ...form, geofence_lng: e.target.value })}
              placeholder="103.776400"
            />
          </label>
          <label className="text-xs text-muted-foreground">
            Radius (m)
            <input
              type="number"
              className={`${input} mt-1`}
              value={form.geofence_radius_m}
              onChange={(e) => setForm({ ...form, geofence_radius_m: e.target.value })}
            />
          </label>
          <div className="flex items-end">
            <button
              disabled={saving}
              className="w-full rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground transition hover:brightness-110 disabled:opacity-60"
            >
              {saving ? "Creating…" : "Create session"}
            </button>
          </div>
        </form>
      )}

      <div className="divide-y divide-border">
        {sessions.isLoading && (
          <p className="px-5 py-6 text-sm text-muted-foreground">Loading sessions…</p>
        )}
        {!sessions.isLoading && list.length === 0 && (
          <p className="px-5 py-6 text-sm text-muted-foreground">
            {currentUserId && courses.isSuccess && availableCourses.length === 0
              ? "No courses are assigned to you."
              : "No sessions yet."}
          </p>
        )}
        {list.map((s) => {
          const sessionRows = bySession.get(s.id) ?? [];
          const isOpen = expanded === s.id;
          return (
            <div key={s.id} className="px-5 py-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-medium text-foreground">
                    {s.courses?.code ?? "—"} · {s.courses?.name ?? "Course"}
                  </p>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {formatSingaporeDateTime(s.starts_at)} SGT · {s.room} · expected{" "}
                    {s.expected_attendance} enrolled · geofence{" "}
                    {s.geofence_lat != null && s.geofence_lng != null
                      ? `${s.geofence_lat.toFixed(4)}, ${s.geofence_lng.toFixed(4)} (${s.geofence_radius_m} m)`
                      : "not set"}
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <span
                    className={`rounded-full px-2 py-0.5 text-[11px] ${
                      s.is_active
                        ? "bg-accent/10 text-accent"
                        : s.status === "scheduled"
                          ? "bg-primary/10 text-primary"
                          : s.status === "cancelled"
                            ? "bg-destructive/10 text-destructive"
                            : "bg-secondary text-muted-foreground"
                    }`}
                  >
                    {s.status.charAt(0).toUpperCase() + s.status.slice(1)}
                  </span>
                  {currentUserId &&
                    s.instructor_id === currentUserId &&
                    s.status === "scheduled" && (
                      <>
                        <button
                          onClick={() =>
                            editingSessionId === s.id ? setEditingSessionId(null) : startEditing(s)
                          }
                          disabled={savingSessionId === s.id}
                          className="rounded-full border border-border bg-glass px-3 py-1.5 text-xs text-muted-foreground transition hover:text-foreground disabled:opacity-60"
                        >
                          {editingSessionId === s.id ? "Cancel edit" : "Edit"}
                        </button>
                        <button
                          onClick={() => void activateSession(s)}
                          disabled={savingSessionId !== null}
                          className="rounded-full bg-gradient-to-r from-primary to-accent px-3 py-1.5 text-xs font-medium text-primary-foreground transition hover:brightness-110 disabled:opacity-60"
                        >
                          {savingSessionId === s.id ? "Activating…" : "Activate"}
                        </button>
                        <button
                          type="button"
                          onClick={() => setDeleteTarget(s)}
                          disabled={savingSessionId !== null}
                          aria-label={`Delete ${s.name}`}
                          title="Delete scheduled session"
                          className="inline-flex size-8 items-center justify-center rounded-full border border-destructive/30 text-destructive transition hover:bg-destructive/10 disabled:opacity-60"
                        >
                          <X className="size-4" aria-hidden="true" />
                        </button>
                      </>
                    )}
                  <button
                    onClick={() => setExpanded(isOpen ? null : s.id)}
                    className="rounded-full border border-border bg-glass px-3 py-1.5 text-xs text-muted-foreground transition hover:text-foreground"
                  >
                    {sessionRows.length} check-ins {isOpen ? "▲" : "▼"}
                  </button>
                  <button
                    onClick={() =>
                      downloadCsv(
                        `session-${s.courses?.code ?? "export"}`,
                        checkInsToCsv(sessionRows),
                      )
                    }
                    className="rounded-full border border-border bg-glass px-3 py-1.5 text-xs text-muted-foreground transition hover:text-foreground"
                  >
                    Export CSV
                  </button>
                </div>
              </div>

              {editingSessionId === s.id && (
                <form
                  onSubmit={(event) => void updateSession(event, s)}
                  className="mt-4 grid gap-3 rounded-xl border border-border bg-background/40 p-4 sm:grid-cols-2 lg:grid-cols-4"
                >
                  <label className="text-xs text-muted-foreground">
                    Course
                    <select
                      className={`${input} mt-1`}
                      value={editForm.course_id}
                      onChange={(event) =>
                        setEditForm({ ...editForm, course_id: event.target.value })
                      }
                      required
                    >
                      <option value="">Select course</option>
                      {availableCourses.map((course) => (
                        <option key={course.id} value={course.id}>
                          {course.code} · {course.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="text-xs text-muted-foreground">
                    Room
                    <input
                      className={`${input} mt-1`}
                      value={editForm.room}
                      onChange={(event) => setEditForm({ ...editForm, room: event.target.value })}
                      required
                    />
                  </label>
                  <label className="text-xs text-muted-foreground">
                    Starts at (Singapore time)
                    <input
                      type="datetime-local"
                      className={`${input} mt-1`}
                      value={editForm.starts_at}
                      onChange={(event) =>
                        setEditForm({ ...editForm, starts_at: event.target.value })
                      }
                      required
                    />
                  </label>
                  <div className="rounded-lg border border-border bg-glass px-3 py-2">
                    <p className="text-xs text-muted-foreground">Expected attendance</p>
                    <p className="mt-1 text-sm text-foreground">
                      {selectedCourseEnrollmentCount.isLoading
                        ? "Loading…"
                        : selectedCourseEnrollmentCount.isError
                          ? "Unavailable"
                          : `${selectedCourseEnrollmentCount.data?.total_enrolled ?? 0} active enrollments`}
                    </p>
                    <p className="mt-0.5 text-[11px] text-muted-foreground">
                      {selectedCourseEnrollmentCount.isError
                        ? "Could not load this course’s enrollment count"
                        : "Derived from the selected course"}
                    </p>
                  </div>
                  <label className="text-xs text-muted-foreground">
                    Geofence latitude
                    <input
                      type="number"
                      step="any"
                      min="-90"
                      max="90"
                      className={`${input} mt-1`}
                      value={editForm.geofence_lat}
                      onChange={(event) =>
                        setEditForm({ ...editForm, geofence_lat: event.target.value })
                      }
                    />
                  </label>
                  <label className="text-xs text-muted-foreground">
                    Geofence longitude
                    <input
                      type="number"
                      step="any"
                      min="-180"
                      max="180"
                      className={`${input} mt-1`}
                      value={editForm.geofence_lng}
                      onChange={(event) =>
                        setEditForm({ ...editForm, geofence_lng: event.target.value })
                      }
                    />
                  </label>
                  <label className="text-xs text-muted-foreground">
                    Radius (m)
                    <input
                      type="number"
                      min="1"
                      className={`${input} mt-1`}
                      value={editForm.geofence_radius_m}
                      onChange={(event) =>
                        setEditForm({ ...editForm, geofence_radius_m: event.target.value })
                      }
                    />
                  </label>
                  <div className="flex items-end">
                    <button
                      type="submit"
                      disabled={savingSessionId !== null}
                      className="w-full rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground transition hover:brightness-110 disabled:opacity-60"
                    >
                      {savingSessionId === s.id ? "Saving…" : "Save changes"}
                    </button>
                  </div>
                </form>
              )}

              {isOpen && (
                <div className="mt-3 overflow-x-auto rounded-xl border border-border">
                  <table className="w-full min-w-[520px] text-left text-sm">
                    <thead>
                      <tr className="text-[10px] uppercase tracking-wider text-muted-foreground">
                        <th className="px-4 py-2 font-medium">Student</th>
                        <th className="px-4 py-2 font-medium">Checked in</th>
                        <th className="px-4 py-2 font-medium">Status</th>
                        <th className="px-4 py-2 text-right font-medium">Risk</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {sessionRows.length === 0 && (
                        <tr>
                          <td colSpan={4} className="px-4 py-4 text-xs text-muted-foreground">
                            No check-ins for this session.
                          </td>
                        </tr>
                      )}
                      {sessionRows.map((r) => (
                        <tr key={r.id}>
                          <td className="px-4 py-2 text-foreground">{r.student}</td>
                          <td className="px-4 py-2 text-muted-foreground">
                            {formatSingaporeDateTime(r.time)} SGT
                          </td>
                          <td className="px-4 py-2">
                            <span
                              className={`rounded-full px-2 py-0.5 text-[11px] ${statusStyle[r.status]}`}
                            >
                              {statusText[r.status]}
                            </span>
                          </td>
                          <td className="px-4 py-2 text-right tabular-nums text-muted-foreground">
                            {r.risk}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          );
        })}
      </div>
      <AlertDialog
        open={deleteTarget !== null}
        onOpenChange={(isOpen) => {
          if (!isOpen && savingSessionId === null) setDeleteTarget(null);
        }}
      >
        <AlertDialogContent className="border-border bg-card text-card-foreground">
          <AlertDialogHeader>
            <AlertDialogTitle>Delete session?</AlertDialogTitle>
            <AlertDialogDescription>
              this session will be deleted
              {deleteTarget ? `: ${deleteTarget.name}.` : "."}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={savingSessionId !== null}>Go back</AlertDialogCancel>
            <AlertDialogAction
              disabled={!deleteTarget || savingSessionId !== null}
              onSelect={(event) => {
                event.preventDefault();
                if (deleteTarget) void deleteSession(deleteTarget);
              }}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleteTarget && savingSessionId === deleteTarget.id ? "Deleting…" : "Confirm"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
