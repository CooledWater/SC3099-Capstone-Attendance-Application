import { useEffect, useMemo, useRef, useState } from "react";
import { SessionCalendar } from "./SessionCalendar";
import { mondayOf } from "@/lib/session-calendar";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { MoreHorizontal } from "lucide-react";
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
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  downloadCsv,
  fetchSessions,
  fetchCourses,
  statusText,
  type SessionRow,
} from "@/lib/attendance";
import type { CheckInRow } from "./AttendanceTable";
import { statusStyle } from "./AttendanceTable";

type Venue = { code: string; name: string };

function venueCode(venues: Venue[], value: string) {
  return venues.find((venue) => venue.code === value || venue.name === value)?.code ?? "";
}

export function SessionsPanel({
  rows,
  canCreate,
  courseIds,
  currentUserId,
  selectedCourseId: controlledCourseId,
  onCourseChange,
  onViewSession,
}: {
  rows: CheckInRow[];
  canCreate: boolean;
  courseIds?: Set<string>;
  currentUserId?: string;
  selectedCourseId?: string;
  onCourseChange?: (id: string) => void;
  onViewSession?: (session: SessionRow) => void;
}) {
  const qc = useQueryClient();
  const sessions = useQuery({
    queryKey: ["sessions"],
    queryFn: fetchSessions,
    refetchInterval: 5000,
  });
  const courses = useQuery({
    queryKey: ["courses"],
    queryFn: fetchCourses,
  });
  const venues = useQuery({
    queryKey: ["venues", currentUserId],
    queryFn: ({ signal }) => api.request<{ items: Venue[] }>("/venues/", { signal }),
    enabled: canCreate,
  });
  const venueOptions = venues.data?.items ?? [];
  const venuePlaceholder = venues.isPending
    ? "Loading venues…"
    : venues.isError
      ? "Could not load venues"
      : venueOptions.length ? "Select venue" : "No venues available";
  const venueFeedback = venues.isError ? (
    <span role="alert" className="mt-1 block text-xs text-destructive">
      Could not load venues.{" "}
      <button type="button" className="underline" onClick={() => void venues.refetch()}>Retry</button>
    </span>
  ) : null;
  const [open, setOpen] = useState(false);
  const [view, setView] = useState<"list" | "calendar">("list");
  const [week, setWeek] = useState(() => mondayOf(Date.now()));
  const newFormRef = useRef<HTMLFormElement>(null);
  useEffect(() => {
    if (open) {
      newFormRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      newFormRef.current?.querySelector("select")?.focus();
    }
  }, [open]);
  const [saving, setSaving] = useState(false);
  const [savingSessionId, setSavingSessionId] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [localCourseId, setLocalCourseId] = useState("all");
  const selectedCourseId = controlledCourseId ?? localCourseId;
  const setSelectedCourseId = onCourseChange ?? setLocalCourseId;
  useEffect(() => {
    setEditingSessionId(null);
    setDeleteTarget(null);
    setOpen(false);
  }, [selectedCourseId]);
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<SessionRow | null>(null);
  const [exportingSessionId, setExportingSessionId] = useState<string | null>(null);
  async function exportSession(session: SessionRow) {
    setExportingSessionId(session.id);
    try {
      const csv = await api.text(`/export/session/${encodeURIComponent(session.id)}?format=csv`);
      downloadCsv(`session-${session.id}`, csv);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not export session attendance.");
    } finally {
      setExportingSessionId(null);
    }
  }
  const [form, setForm] = useState({
    course_id: "",
    session_name: "",
    session_type: "lecture",
    venue: "",
    starts_at: "",
    duration_minutes: "60",
    geofence_radius_m: "100",
    require_liveness_check: true,
  });
  const [editForm, setEditForm] = useState({
    course_id: "",
    venue: "",
    starts_at: "",
    duration_minutes: "60",
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
    return all.filter(
      (session) =>
        (!courseIds || courseIds.has(session.course_id)) &&
        (selectedCourseId === "all" || session.course_id === selectedCourseId),
    );
  }, [sessions.data, courseIds, selectedCourseId]);

  const editingSession = list.find((session) => session.id === editingSessionId) ?? null;
  const availableCourses = (courses.isSuccess ? courses.data : []).filter(
    (course) => !currentUserId || course.instructor_id === currentUserId,
  );
  const bySession = useMemo(() => {
    const m = new Map<string, CheckInRow[]>();
    rows.forEach((r) => m.set(r.sessionId, [...(m.get(r.sessionId) ?? []), r]));
    return m;
  }, [rows]);
  const sessionGroups = useMemo(() => {
    const groups = [
      {
        status: "active",
        title: "Active",
        sessions: list.filter((session) => session.status === "active"),
        timestamp: (session: SessionRow) => session.actual_start ?? session.starts_at,
        direction: -1,
      },
      {
        status: "scheduled",
        title: "Scheduled",
        sessions: list.filter((session) => session.status === "scheduled"),
        timestamp: (session: SessionRow) => session.starts_at,
        direction: 1,
      },
      {
        status: "closed",
        title: "Closed",
        sessions: list.filter((session) => session.status === "closed"),
        timestamp: (session: SessionRow) => session.actual_end ?? session.ends_at,
        direction: -1,
      },
      {
        status: "cancelled",
        title: "Cancelled",
        sessions: list.filter((session) => session.status === "cancelled"),
        timestamp: (session: SessionRow) => session.starts_at,
        direction: -1,
      },
    ];

    return groups
      .filter((group) => group.sessions.length > 0)
      .map((group) => ({
        ...group,
        sessions: [...group.sessions].sort((a, b) => {
          const aTime = parseApiDateTime(group.timestamp(a)).getTime();
          const bTime = parseApiDateTime(group.timestamp(b)).getTime();
          if (!Number.isFinite(aTime)) return Number.isFinite(bTime) ? 1 : 0;
          if (!Number.isFinite(bTime)) return -1;
          return (aTime - bTime) * group.direction;
        }),
      }));
  }, [list]);

  async function createSession(e: React.FormEvent) {
    e.preventDefault();
    if (
      (currentUserId && !availableCourses.some((course) => course.id === form.course_id)) ||
      (courseIds && !courseIds.has(form.course_id))
    ) {
      toast.error("Choose a course assigned to your account.");
      return;
    }
    if (
      !form.course_id ||
      !form.session_name.trim() ||
      !form.session_type ||
      !venueCode(venueOptions, form.venue) || venues.isError ||
      !form.starts_at
    ) {
      toast.error("Course, session name, session type, venue and start time are required.");
      return;
    }
    setSaving(true);
    try {
      const scheduledStart = parseSingaporeDateTimeLocal(form.starts_at);
      if (
        !scheduledStart ||
        !Number.isSafeInteger(Number(form.duration_minutes)) ||
        Number(form.duration_minutes) <= 0
      ) {
        toast.error("Enter a valid start time and a positive duration.");
        return;
      }
      await api.request("/sessions/", {
        method: "POST",
        timeoutMs: 60000,
        body: JSON.stringify({
          course_id: form.course_id,
          name: form.session_name.trim(),
          session_type: form.session_type,
          scheduled_start: scheduledStart.toISOString(),
          checkin_opens_at: scheduledStart.toISOString(),
          checkin_closes_at: new Date(
            scheduledStart.getTime() + Number(form.duration_minutes) * 60000,
          ).toISOString(),
          scheduled_end: new Date(
            scheduledStart.getTime() + Number(form.duration_minutes) * 60000,
          ).toISOString(),
          venue_name: venueCode(venueOptions, form.venue),
          geofence_radius_meters: Number(form.geofence_radius_m) || 100,
          require_motion_check: form.require_liveness_check,
          require_liveness_check: form.require_liveness_check,
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
    setForm({
      ...form,
      session_name: "",
      session_type: "lecture",
      venue: "",
      starts_at: "",
      require_liveness_check: true,
    });
    qc.invalidateQueries({ queryKey: ["sessions"] });
  }

  function startEditing(session: SessionRow) {
    setEditForm({
      course_id: session.course_id,
      venue: session.room === "Not set" ? "" : session.room,
      starts_at: toSingaporeDateTimeLocal(session.starts_at),
      duration_minutes: String(
        (parseApiDateTime(session.ends_at).getTime() -
          parseApiDateTime(session.starts_at).getTime()) /
          60000,
      ),
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
      !venueCode(venueOptions, editForm.venue) || venues.isError ||
      !editForm.starts_at
    ) {
      toast.error("Choose a course, venue and start time for this scheduled session.");
      return;
    }
    const scheduledStart = parseSingaporeDateTimeLocal(editForm.starts_at);
    if (
      !scheduledStart ||
      !Number.isSafeInteger(Number(editForm.duration_minutes)) ||
      Number(editForm.duration_minutes) <= 0
    ) {
      toast.error("Enter a valid start time and a positive duration.");
      return;
    }

    const scheduledEnd = new Date(
      scheduledStart.getTime() + Number(editForm.duration_minutes) * 60000,
    );
    const shiftedOpen = new Date(
      parseApiDateTime(session.checkin_opens_at).getTime() +
        scheduledStart.getTime() -
        parseApiDateTime(session.starts_at).getTime(),
    );
    const shiftedClose = new Date(
      parseApiDateTime(session.checkin_closes_at).getTime() +
        scheduledEnd.getTime() -
        parseApiDateTime(session.ends_at).getTime(),
    );

    setSavingSessionId(session.id);
    try {
      const updated = await api.request<{ course_id: string }>(
        `/sessions/${encodeURIComponent(session.id)}`,
        {
          method: "PATCH",
          body: JSON.stringify({
            course_id: editForm.course_id,
            name: session.name,
            scheduled_start: scheduledStart.toISOString(),
            scheduled_end: scheduledEnd.toISOString(),
            checkin_opens_at: shiftedOpen.toISOString(),
            checkin_closes_at: shiftedClose.toISOString(),
            venue_name: venueCode(venueOptions, editForm.venue),
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
      await qc.invalidateQueries({ queryKey: ["sessions"] });
      return;
    } finally {
      setSavingSessionId(null);
    }
    toast.success("Session updated.");
    setEditingSessionId(null);
    await qc.invalidateQueries({ queryKey: ["sessions"] });
    await qc.invalidateQueries({ queryKey: ["check-ins"] });
  }

  async function closeSession(session: SessionRow) {
    if (
      !currentUserId ||
      session.instructor_id !== currentUserId ||
      session.status !== "active" ||
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
          body: JSON.stringify({ status: "closed" }),
        },
      );
      if (updated.status !== "closed") {
        throw new Error("The backend did not close this session.");
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not close session.");
      await qc.invalidateQueries({ queryKey: ["sessions"] });
      return;
    } finally {
      setSavingSessionId(null);
    }
    toast.success("Session closed.");
    setEditingSessionId(null);
    await qc.invalidateQueries({ queryKey: ["sessions"] });
    await qc.invalidateQueries({ queryKey: ["check-ins"] });
  }

  async function cancelSession(session: SessionRow) {
    if (
      !currentUserId ||
      session.instructor_id !== currentUserId ||
      (session.status !== "active" && session.status !== "closed") ||
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
          body: JSON.stringify({ status: "cancelled" }),
        },
      );
      if (updated.status !== "cancelled") {
        throw new Error("The backend did not cancel this session.");
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not cancel session.");
      return;
    } finally {
      setSavingSessionId(null);
    }
    toast.success("Session cancelled.");
    setEditingSessionId(null);
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
  const activeCount = list.filter((session) => session.status === "active").length;
  const scheduledCount = list.filter((session) => session.status === "scheduled").length;
  const closedCount = list.filter((session) => session.status === "closed").length;
  const cancelledCount = list.filter((session) => session.status === "cancelled").length;

  return (
    <div className="mt-4 animate-rise rounded-2xl border border-border bg-glass">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-5 py-4">
        <div>
          <h2 className="font-display text-lg font-semibold">Session management</h2>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {view === "calendar" ? null : (
              <>
                {list.length} total · {activeCount} active · {scheduledCount} scheduled ·{" "}
                {closedCount} closed{cancelledCount > 0 ? ` · ${cancelledCount} cancelled` : ""}
              </>
            )}
          </p>
        </div>
        {currentUserId && (
          <div
            role="group"
            aria-label="Session view"
            className="ml-auto flex rounded-lg border border-border p-1"
          >
            {(["list", "calendar"] as const).map((mode) => (
              <button
                key={mode}
                type="button"
                aria-pressed={view === mode}
                onClick={() => setView(mode)}
                className={`rounded-md px-3 py-1.5 text-xs capitalize ${view === mode ? "bg-primary/20 text-primary" : "text-muted-foreground"}`}
              >
                {mode === "list" ? "List" : "Calendar"}
              </button>
            ))}
          </div>
        )}
        {canCreate && (!currentUserId || availableCourses.length > 0) && (
          <button
            onClick={() => {
              setForm({
                ...form,
                require_liveness_check: true,
                course_id:
                  selectedCourseId === "all" ? (availableCourses[0]?.id ?? "") : selectedCourseId,
              });
              setOpen((v) => !v);
            }}
            className="rounded-full bg-gradient-to-r from-primary to-accent px-3 py-1.5 text-xs font-medium text-primary-foreground transition hover:brightness-110"
          >
            {open ? "Cancel" : "New session"}
          </button>
        )}
      </div>

      {canCreate && (!currentUserId || availableCourses.length > 0) && open && (
        <form
          ref={newFormRef}
          onSubmit={createSession}
          className="grid gap-3 border-b border-border px-5 py-4 sm:grid-cols-2 lg:grid-cols-4"
        >
          <label className="text-xs text-muted-foreground">
            Course
            <select
              className={`${input} mt-1`}
              required
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
            Session name
            <input
              required
              className={`${input} mt-1`}
              value={form.session_name}
              onChange={(e) => setForm({ ...form, session_name: e.target.value })}
              placeholder="Lecture 5: Neural Networks"
            />
          </label>
          <label className="text-xs text-muted-foreground">
            Session type
            <select
              required
              className={`${input} mt-1`}
              value={form.session_type}
              onChange={(e) => setForm({ ...form, session_type: e.target.value })}
            >
              <option value="lecture">Lecture</option>
              <option value="tutorial">Tutorial</option>
              <option value="lab">Lab</option>
              <option value="exam">Exam</option>
            </select>
          </label>
          <label className="text-xs text-muted-foreground">
            Venue
            <select
              className={`${input} mt-1`}
              required
              disabled={venues.isPending || venues.isError || !venueOptions.length}
              value={venueCode(venueOptions, form.venue)}
              onChange={(e) => setForm({ ...form, venue: e.target.value })}
            >
              <option value="">{venuePlaceholder}</option>
              {venueOptions.map((venue) => (
                <option key={venue.code} value={venue.code}>{venue.code} · {venue.name}</option>
              ))}
            </select>
            {venueFeedback}
          </label>
          <label className="text-xs text-muted-foreground">
            Starts at (Singapore time)
            <input
              type="datetime-local"
              className={`${input} mt-1`}
              required
              value={form.starts_at}
              onChange={(e) => setForm({ ...form, starts_at: e.target.value })}
            />
          </label>
          <label className="text-xs text-muted-foreground">
            Duration (minutes)
            <input
              type="number"
              min="1"
              step="1"
              required
              className={`${input} mt-1`}
              value={form.duration_minutes}
              onChange={(event) => setForm({ ...form, duration_minutes: event.target.value })}
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
          <label className="flex items-start gap-2 text-xs text-muted-foreground sm:col-span-2 lg:col-span-4">
            <input
              type="checkbox"
              className="mt-0.5"
              checked={form.require_liveness_check}
              disabled={saving}
              onChange={(event) => setForm({ ...form, require_liveness_check: event.target.checked })}
            />
            <span>
              Require liveness check
              <small className="mt-1 block">
                When enabled, students complete the configured liveness challenge before checking in.
              </small>
            </span>
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

      <div className="border-b border-border px-5 py-4">
        <label className="block max-w-xs text-xs text-muted-foreground">
          Filter by course
          <select
            className={`${input} mt-1`}
            value={selectedCourseId}
            onChange={(event) => setSelectedCourseId(event.target.value)}
          >
            <option value="all">All courses</option>
            {availableCourses.map((course) => (
              <option key={course.id} value={course.id}>
                {course.code} · {course.name}
              </option>
            ))}
          </select>
        </label>
      </div>
      {view === "calendar" && currentUserId && (
        <SessionCalendar
          key={`${selectedCourseId}:${week}`}
          courseId={selectedCourseId}
          courseIds={courseIds}
          userId={currentUserId}
          week={week}
          onWeekChange={setWeek}
          onEdit={(row) => startEditing(row)}
          onCreate={(instant) => {
            setForm({
              ...form,
              require_liveness_check: true,
              course_id:
                selectedCourseId === "all" ? (availableCourses[0]?.id ?? "") : selectedCourseId,
              starts_at: toSingaporeDateTimeLocal(new Date(instant).toISOString()),
            });
            setOpen(true);
          }}
        />
      )}
      <div className={view === "calendar" ? "hidden" : "space-y-4 px-5 py-4"}>
        {sessions.isLoading && (
          <p className="py-2 text-sm text-muted-foreground">Loading sessions…</p>
        )}
        {sessions.isError && (
          <p role="alert" className="py-2 text-sm text-destructive">
            Could not load sessions.{" "}
            <button type="button" className="underline" onClick={() => void sessions.refetch()}>
              Retry
            </button>
          </p>
        )}
        {!sessions.isLoading && !sessions.isError && list.length === 0 && (
          <p className="py-2 text-sm text-muted-foreground">
            {currentUserId && courses.isSuccess && availableCourses.length === 0
              ? "No courses are assigned to you."
              : "No sessions yet."}
          </p>
        )}
        {!sessions.isLoading &&
          list.length > 0 &&
          sessionGroups.map((group) => (
            <div key={group.status} className="space-y-2">
              <h3
                className={`px-1 text-sm font-medium ${group.status === "active" ? "text-emerald-400" : group.status === "closed" ? "text-red-400" : "text-primary"}`}
              >
                {group.title}
              </h3>
              {group.sessions.map((s) => {
                const sessionRows = bySession.get(s.id) ?? [];
                const isOpen = !onViewSession && expanded === s.id;
                const canManage = currentUserId !== undefined && s.instructor_id === currentUserId;
                return (
                  <div key={s.id} className="rounded-xl border border-border bg-card/40 px-5 py-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className="text-sm font-medium text-foreground">
                          {s.courses?.code ?? "—"} · {s.courses?.name ?? "Course"}
                        </p>
                        <p className="mt-0.5 text-xs text-muted-foreground">
                          {formatSingaporeDateTime(s.starts_at, {
                            month: "short",
                            day: "numeric",
                            year: "numeric",
                            hour: "numeric",
                            minute: "2-digit",
                            hour12: true,
                          })}{" "}
                          -{" "}
                          {formatSingaporeDateTime(s.ends_at, {
                            hour: "numeric",
                            minute: "2-digit",
                            hour12: true,
                          })}{" "}
                          · {s.room}{" "}
                          {s.status === "scheduled" && <> · {s.expected_attendance} enrolled</>}
                          {s.status !== "scheduled" && (
                            <button
                              type="button"
                              aria-label={`View check-ins for ${s.name}`}
                              aria-expanded={onViewSession ? undefined : isOpen}
                              onClick={() =>
                                onViewSession ? onViewSession(s) : setExpanded(isOpen ? null : s.id)
                              }
                              disabled={
                                !!onViewSession && s.status !== "active" && s.status !== "closed"
                              }
                              className="text-primary underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                            >
                              {sessionRows.length} / {s.expected_attendance} checked in →
                            </button>
                          )}
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
                        {((canManage && (s.status === "scheduled" || s.status === "active")) ||
                          s.status === "closed") && (
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <button
                                type="button"
                                aria-label={`More actions for ${s.name}`}
                                disabled={savingSessionId !== null}
                                className="inline-flex size-9 items-center justify-center rounded-full border border-border bg-glass text-muted-foreground transition hover:text-foreground disabled:opacity-60"
                              >
                                <MoreHorizontal className="size-4" aria-hidden="true" />
                              </button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              {s.status === "scheduled" && (
                                <>
                                  <DropdownMenuItem onSelect={() => startEditing(s)}>
                                    Edit
                                  </DropdownMenuItem>
                                  <DropdownMenuItem
                                    onSelect={() => setDeleteTarget(s)}
                                    className="text-destructive focus:bg-destructive/10 focus:text-destructive"
                                  >
                                    Delete
                                  </DropdownMenuItem>
                                </>
                              )}
                              {s.status === "active" && (
                                <DropdownMenuItem onSelect={() => void closeSession(s)}>
                                  {savingSessionId === s.id ? "Closing…" : "Close session"}
                                </DropdownMenuItem>
                              )}
                              {s.status === "closed" && (
                                <DropdownMenuItem
                                  disabled={exportingSessionId !== null}
                                  onSelect={() => void exportSession(s)}
                                >
                                  {exportingSessionId === s.id
                                    ? "Exporting…"
                                    : "Export session CSV"}
                                </DropdownMenuItem>
                              )}
                              {canManage && (s.status === "active" || s.status === "closed") && (
                                <DropdownMenuItem
                                  onSelect={() => void cancelSession(s)}
                                  className="text-destructive focus:bg-destructive/10 focus:text-destructive"
                                >
                                  {savingSessionId === s.id ? "Cancelling…" : "Cancel session"}
                                </DropdownMenuItem>
                              )}
                            </DropdownMenuContent>
                          </DropdownMenu>
                        )}
                      </div>
                    </div>

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
                                  {r.riskScore ?? r.risk / 100}
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
          ))}
      </div>
      <Dialog
        open={Boolean(editingSession)}
        onOpenChange={(isOpen) => {
          if (!isOpen && savingSessionId === null) setEditingSessionId(null);
        }}
      >
        <DialogContent className="max-h-[90vh] overflow-y-auto border-border bg-card text-card-foreground">
          <DialogHeader>
            <DialogTitle>
              {editingSession?.status === "active"
                ? "Active session details"
                : "Edit scheduled session"}
            </DialogTitle>
          </DialogHeader>
          {editingSession && (
            <form
              id="edit-session-form"
              onSubmit={(event) => void updateSession(event, editingSession)}
              className="space-y-3"
            >
              <fieldset
                disabled={
                  editingSession.status !== "scheduled" ||
                  savingSessionId !== null ||
                  editingSession.instructor_id !== currentUserId
                }
                className="grid gap-3 sm:grid-cols-2"
              >
                <label className="text-xs text-muted-foreground sm:col-span-2">
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
                <label className="text-xs text-muted-foreground sm:col-span-2">
                  Venue
                  <select
                    className={`${input} mt-1`}
                    value={venueCode(venueOptions, editForm.venue)}
                    disabled={venues.isPending || venues.isError || !venueOptions.length}
                    onChange={(event) => setEditForm({ ...editForm, venue: event.target.value })}
                    required
                  >
                    <option value="">{venuePlaceholder}</option>
                    {venueOptions.map((venue) => (
                      <option key={venue.code} value={venue.code}>{venue.code} · {venue.name}</option>
                    ))}
                  </select>
                  {venueFeedback}
                </label>
                <label className="text-xs text-muted-foreground sm:col-span-2">
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
                <div className="rounded-lg border border-border bg-glass px-3 py-2 sm:col-span-2">
                  <p className="text-xs text-muted-foreground">Expected attendance</p>
                  <p className="mt-1 text-sm text-foreground">
                    {selectedCourseEnrollmentCount.isLoading
                      ? "Loading…"
                      : selectedCourseEnrollmentCount.isError
                        ? "Unavailable"
                        : `${selectedCourseEnrollmentCount.data?.total_enrolled ?? 0} active enrollments`}
                  </p>
                  {selectedCourseEnrollmentCount.isError && (
                    <p className="mt-0.5 text-[11px] text-muted-foreground">
                      Could not load this course’s enrollment count
                    </p>
                  )}
                </div>
                <label className="text-xs text-muted-foreground">
                  Duration (minutes)
                  <input
                    type="number"
                    min="1"
                    step="1"
                    required
                    className={`${input} mt-1`}
                    value={editForm.duration_minutes}
                    onChange={(event) =>
                      setEditForm({ ...editForm, duration_minutes: event.target.value })
                    }
                  />
                </label>
                <label className="text-xs text-muted-foreground sm:col-span-2">
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
              </fieldset>
            </form>
          )}
          <DialogFooter>
            <button
              type="button"
              onClick={() => setEditingSessionId(null)}
              disabled={savingSessionId !== null}
              className="rounded-full border border-border bg-glass px-4 py-2 text-sm text-muted-foreground disabled:opacity-60"
            >
              Cancel
            </button>
            {editingSession?.status === "scheduled" && (
              <button
                type="submit"
                form="edit-session-form"
                disabled={
                  savingSessionId !== null || editingSession.instructor_id !== currentUserId
                }
                className="rounded-full bg-accent px-4 py-2 text-sm font-medium text-accent-foreground disabled:opacity-60"
              >
                {savingSessionId === editingSessionId ? "Saving?" : "Save changes"}
              </button>
            )}
            {editingSession?.status === "active" && (
              <button
                type="button"
                disabled={
                  savingSessionId !== null || editingSession.instructor_id !== currentUserId
                }
                onClick={() => void cancelSession(editingSession)}
                className="rounded-full border border-destructive/40 px-4 py-2 text-sm text-destructive disabled:opacity-50"
              >
                {savingSessionId === editingSessionId ? "Cancelling…" : "Cancel session"}
              </button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
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
              onClick={(event) => {
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
