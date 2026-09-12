import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api } from "@/lib/api";
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
}: {
  rows: CheckInRow[];
  canCreate: boolean;
  courseIds?: Set<string>;
}) {
  const qc = useQueryClient();
  const sessions = useQuery({ queryKey: ["sessions"], queryFn: fetchSessions });
  const courses = useQuery({
    queryKey: ["courses"],
    queryFn: fetchCourses,
  });

  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [form, setForm] = useState({
    course_id: "",
    room: "",
    starts_at: "",
    expected_attendance: "30",
    geofence_lat: "",
    geofence_lng: "",
    geofence_radius_m: "100",
  });

  const list = useMemo(() => {
    const all = (sessions.data ?? []) as SessionRow[];
    return courseIds ? all.filter((s) => courseIds.has(s.course_id)) : all;
  }, [sessions.data, courseIds]);

  const active = list.filter((s) => s.is_active).length;
  const bySession = useMemo(() => {
    const m = new Map<string, CheckInRow[]>();
    rows.forEach((r) => m.set(r.sessionId, [...(m.get(r.sessionId) ?? []), r]));
    return m;
  }, [rows]);

  async function createSession(e: React.FormEvent) {
    e.preventDefault();
    if (!form.course_id || !form.room || !form.starts_at) {
      toast.error("Course, room and start time are required.");
      return;
    }
    setSaving(true);
    try {
      const scheduledStart = new Date(form.starts_at);
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
        </div>
        {canCreate && (
          <button
            onClick={() => setOpen((v) => !v)}
            className="rounded-full bg-gradient-to-r from-primary to-accent px-3 py-1.5 text-xs font-medium text-primary-foreground transition hover:brightness-110"
          >
            {open ? "Cancel" : "New session"}
          </button>
        )}
      </div>

      {canCreate && open && (
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
              {(courses.data ?? []).map((c) => (
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
            Starts at
            <input
              type="datetime-local"
              className={`${input} mt-1`}
              value={form.starts_at}
              onChange={(e) => setForm({ ...form, starts_at: e.target.value })}
            />
          </label>
          <label className="text-xs text-muted-foreground">
            Expected attendance
            <input
              type="number"
              className={`${input} mt-1`}
              value={form.expected_attendance}
              onChange={(e) => setForm({ ...form, expected_attendance: e.target.value })}
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
          <p className="px-5 py-6 text-sm text-muted-foreground">No sessions yet.</p>
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
                    {new Date(s.starts_at).toLocaleString()} · {s.room} · expected{" "}
                    {s.expected_attendance} · geofence{" "}
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
                        : "bg-secondary text-muted-foreground"
                    }`}
                  >
                    {s.is_active ? "Active" : "Inactive"}
                  </span>
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
                            {new Date(r.time).toLocaleString()}
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
    </div>
  );
}
