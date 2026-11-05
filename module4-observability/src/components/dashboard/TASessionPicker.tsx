import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { assignTASessions, fetchCourseSessions, fetchTASessions } from "@/lib/admin";
import { formatSingaporeDateTime } from "@/lib/time";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

const button =
  "rounded-lg border border-border px-3 py-2 text-sm hover:bg-primary/15 disabled:opacity-50";

export function TASessionPicker({
  courseId,
  taId,
  taName,
  userId,
  disabled,
}: {
  courseId: string;
  taId: string;
  taName: string;
  userId: string;
  disabled: boolean;
}) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState<string[]>([]);
  const sessions = useQuery({
    queryKey: ["admin-course-sessions", userId, courseId],
    queryFn: ({ signal }) => fetchCourseSessions(courseId, signal),
    enabled: open,
  });
  const assignments = useQuery({
    queryKey: ["admin-ta-sessions", userId, courseId, taId],
    queryFn: ({ signal }) => fetchTASessions(courseId, taId, signal),
    enabled: open,
  });
  const assigned = new Set(assignments.data?.items.map((item) => item.session_id));
  const courseSessions = (sessions.data ?? []).filter((session) => session.course_id === courseId);
  const sessionIds = courseSessions
    .filter((session) => selected.includes(session.id) && !assigned.has(session.id))
    .map((session) => session.id);
  const ready = sessions.isSuccess && assignments.isSuccess;
  const change = useMutation({
    mutationFn: () => assignTASessions(courseId, taId, sessionIds),
    onSuccess: async () => {
      setSelected([]);
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["admin-ta-sessions", userId, courseId, taId] }),
        qc.invalidateQueries({ queryKey: ["sessions"] }),
        qc.invalidateQueries({ queryKey: ["audit-logs"] }),
      ]);
    },
  });

  return (
    <Popover
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!change.isPending) {
          setSelected([]);
          change.reset();
        }
      }}
    >
      <PopoverTrigger asChild>
        <button
          type="button"
          className={button}
          disabled={disabled || change.isPending}
          aria-label={`Assign sessions for ${taName}`}
        >
          Assign sessions
        </button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-96 max-w-[calc(100vw-2rem)] space-y-3">
        <p className="font-medium">Sessions for {taName}</p>
        <p className="text-xs text-muted-foreground">
          Select up to 200 sessions. Times are in Singapore time.
        </p>
        {(sessions.isPending || assignments.isPending) && <p role="status">Loading sessions…</p>}
        {(sessions.isError || assignments.isError) && (
          <p role="alert">
            Could not load sessions or assignments.{" "}
            <button
              type="button"
              className={button}
              onClick={() => {
                void sessions.refetch();
                void assignments.refetch();
              }}
            >
              Retry
            </button>
          </p>
        )}
        {ready && (
          <div className="max-h-64 space-y-2 overflow-y-auto">
            {!courseSessions.length && <p>No sessions in this course.</p>}
            {courseSessions.map((session) => (
              <label
                key={session.id}
                className="flex items-start gap-2 rounded-lg border border-border p-2 text-sm"
              >
                <input
                  type="checkbox"
                  className="mt-1"
                  checked={assigned.has(session.id) || selected.includes(session.id)}
                  disabled={
                    disabled ||
                    change.isPending ||
                    assigned.has(session.id) ||
                    (sessionIds.length >= 200 && !selected.includes(session.id))
                  }
                  onChange={(event) => {
                    const checked = event.target.checked;
                    setSelected((previous) =>
                      checked
                        ? [...previous, session.id]
                        : previous.filter((id) => id !== session.id),
                    );
                    change.reset();
                  }}
                />
                <span>
                  {session.name}
                  <span className="block text-xs text-muted-foreground">
                    {formatSingaporeDateTime(session.scheduled_start)} · {session.status}
                    {assigned.has(session.id) && " · Already assigned"}
                  </span>
                </span>
              </label>
            ))}
          </div>
        )}
        {change.isError && (
          <p role="alert" className="text-destructive">
            {change.error.message}
          </p>
        )}
        {change.isSuccess && (
          <p role="status" className="text-accent">
            Sessions assigned.
          </p>
        )}
        <button
          type="button"
          className={button}
          disabled={
            disabled || !ready || change.isPending || !sessionIds.length || sessionIds.length > 200
          }
          onClick={() => {
            if (
              !disabled &&
              ready &&
              !change.isPending &&
              sessionIds.length &&
              sessionIds.length <= 200
            )
              change.mutate();
          }}
        >
          {change.isPending ? "Assigning…" : `Assign selected (${sessionIds.length})`}
        </button>
      </PopoverContent>
    </Popover>
  );
}
