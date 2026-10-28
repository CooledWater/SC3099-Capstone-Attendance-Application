import { useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { toSessionRow, type ApiSession, type SessionRow } from "@/lib/attendance";
import {
  DAY,
  SLOT,
  layoutDay,
  loadCalendarSessions,
  mondayOf,
  movePayload,
} from "@/lib/session-calendar";
import { formatSingaporeDateTime, parseApiDateTime } from "@/lib/time";
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogCancel,
} from "@/components/ui/alert-dialog";

const control =
  "rounded-lg border border-border bg-secondary/40 px-3 py-2 text-xs focus-visible:ring-2 focus-visible:ring-primary disabled:opacity-50";
const clock = (value: number | string) =>
  formatSingaporeDateTime(typeof value === "number" ? new Date(value).toISOString() : value, {
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  });

export function SessionCalendar({
  courseId,
  courseIds,
  userId,
  week,
  onWeekChange,
  onEdit,
  onCreate,
  readOnly = false,
}: {
  courseId: string;
  courseIds: Set<string> | undefined;
  userId: string;
  week: number;
  onWeekChange: (week: number) => void;
  onEdit: (row: SessionRow) => void;
  onCreate: (instant: number) => void;
  readOnly?: boolean;
}) {
  const qc = useQueryClient();
  const [move, setMove] = useState<{ session: SessionRow; start: number } | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const busy = useRef(false);
  const query = useQuery({
    queryKey: ["sessions", "calendar", userId, courseId, week],
    queryFn: ({ signal }) => loadCalendarSessions(courseId, week, signal),
    refetchInterval: 15000,
  });
  const sessions = (query.data ?? []).filter((row) => !courseIds || courseIds.has(row.course_id));
  const days = Array.from({ length: 5 }, (_, i) => week + i * DAY);
  const segments = days.map((day) => layoutDay(sessions, day));
  const minHour = Math.min(
    8,
    ...segments
      .flat()
      .map((block) =>
        Math.floor(
          (block.start - days.find((day) => block.start >= day && block.start < day + DAY)!) /
            3600000,
        ),
      ),
  );
  const maxHour = Math.max(
    20,
    ...segments.flatMap((blocks, i) =>
      blocks.map((block) => Math.ceil((block.end - days[i]!) / 3600000)),
    ),
  );
  const slots = Array.from(
    { length: (maxHour - minHour) * 2 },
    (_, i) => minHour * 3600000 + i * SLOT,
  );
  const height = slots.length * 32;
  const today = formatSingaporeDateTime(new Date().toISOString(), {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
  async function confirmMove() {
    if (readOnly || !move || busy.current) return;
    busy.current = true;
    setSaving(true);
    setError(null);
    try {
      const latest = toSessionRow(
        await api.request<ApiSession>(`/sessions/${encodeURIComponent(move.session.id)}`),
      );
      if (latest.status !== "scheduled")
        throw new Error("This session is no longer Scheduled. The calendar has been refreshed.");
      if (latest.starts_at !== move.session.starts_at || latest.ends_at !== move.session.ends_at)
        throw new Error(
          "This session was changed by another request. Refresh and choose a new time.",
        );
      await api.request(`/sessions/${encodeURIComponent(latest.id)}`, {
        method: "PATCH",
        body: JSON.stringify(movePayload(latest, move.start)),
      });
      setMove(null);
      toast.success("Session moved.");
    } catch (failure) {
      setError(
        failure instanceof Error
          ? failure.message
          : "Could not move session. The original position is unchanged.",
      );
    } finally {
      busy.current = false;
      setSaving(false);
      await qc.invalidateQueries({ queryKey: ["sessions"] });
    }
  }
  function drop(event: React.DragEvent, instant: number) {
    if (readOnly) return;
    event.preventDefault();
    const row = sessions.find((item) => item.id === event.dataTransfer.getData("text/plain"));
    if (!row || row.status !== "scheduled" || row.instructor_id !== userId) return;
    setError(null);
    setMove({ session: row, start: instant });
  }
  function blockButton(
    block: ReturnType<typeof layoutDay>[number],
    calendar: boolean,
    day: number,
  ) {
    const row = block.session;
    const scheduled = row.status === "scheduled";
    const duration = Math.round(
      (parseApiDateTime(row.ends_at).getTime() - parseApiDateTime(row.starts_at).getTime()) / 60000,
    );
    return (
      <button
        key={row.id}
        data-session-id={row.id}
        type="button"
        draggable={!readOnly && scheduled && row.instructor_id === userId && !saving}
        onDragStart={(event) => {
          if (readOnly) {
            event.preventDefault();
            return;
          }
          event.dataTransfer.setData("text/plain", row.id);
          event.dataTransfer.effectAllowed = "move";
        }}
        onClick={() => {
          if (!readOnly) onEdit(row);
        }}
        aria-label={`${row.courses?.code ?? "Course"} ${row.name}, ${clock(row.starts_at)} to ${clock(row.ends_at)}, ${scheduled ? "Scheduled" : "Active"}`}
        title={`${row.name} · ${duration} min · ${readOnly ? (scheduled ? "Scheduled" : "Active") : scheduled ? "Scheduled — drag to move or click to edit" : "Active — timing locked"}`}
        className={`${calendar ? "absolute z-10" : "w-full"} overflow-auto rounded-md border-l-[3px] p-2 text-left text-[11px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary ${scheduled ? "border-violet-300 bg-violet-400/25" : "border-emerald-300 bg-emerald-400/20"}`}
        style={
          calendar
            ? {
                top: ((block.start - day - minHour * 3600000) / SLOT) * 32,
                height: ((block.end - block.start) / SLOT) * 32,
                left: `calc(${(block.lane / block.lanes) * 100}% + 3px)`,
                width: `calc(${100 / block.lanes}% - 6px)`,
              }
            : undefined
        }
      >
        <span className="block font-semibold">
          {row.courses?.code ?? "Course"} · {row.name}
        </span>
        <span className="mt-0.5 block">
          {clock(row.starts_at)}–{clock(row.ends_at)} · {duration} min
        </span>
        <span className="block">{scheduled ? "Scheduled" : "Active"}</span>
      </button>
    );
  }
  return (
    <section className="p-4 sm:p-5" aria-label="Session calendar">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex gap-1.5">
          <button
            className={control}
            aria-label="Previous week"
            onClick={() => onWeekChange(week - 7 * DAY)}
          >
            ←
          </button>
          <button
            className={control}
            aria-label="Next week"
            onClick={() => onWeekChange(week + 7 * DAY)}
          >
            →
          </button>
          <button className={control} onClick={() => onWeekChange(mondayOf(Date.now()))}>
            Today
          </button>
        </div>
        <h3 className="text-sm font-semibold" aria-live="polite">
          {formatSingaporeDateTime(new Date(week).toISOString(), {
            day: "numeric",
            month: "short",
          })}{" "}
          –{" "}
          {formatSingaporeDateTime(new Date(days.at(-1)!).toISOString(), {
            day: "numeric",
            month: "short",
            year: "numeric",
          })}
        </h3>
      </div>
      {query.isPending && (
        <p role="status" className="mb-4 text-sm text-muted-foreground">
          Loading calendar…
        </p>
      )}
      {query.isError && (
        <p role="alert" className="mb-4 text-sm text-destructive">
          Could not load sessions.{" "}
          <button className={control} onClick={() => void query.refetch()}>
            Retry
          </button>
        </p>
      )}
      {query.isSuccess && !sessions.length && (
        <p role="status" className="mb-4 text-xs text-muted-foreground">
          No Scheduled or Active sessions this week.
          {!readOnly && " Choose an empty slot to create one."}
        </p>
      )}
      <div className="hidden max-h-[650px] overflow-auto rounded-xl border border-border md:block">
        <div
          className="sticky top-0 z-20 grid bg-card"
          style={{ gridTemplateColumns: `48px repeat(${days.length}, minmax(115px, 1fr))` }}
        >
          <div className="border-b border-border" />
          {days.map((day) => (
            <h4
              key={day}
              className={`border-b border-l border-border px-2 py-3 text-center text-xs font-medium ${formatSingaporeDateTime(new Date(day).toISOString(), { year: "numeric", month: "2-digit", day: "2-digit" }) === today ? "bg-primary/20" : ""}`}
            >
              {formatSingaporeDateTime(new Date(day).toISOString(), {
                weekday: "short",
                day: "numeric",
                month: "short",
              })}
            </h4>
          ))}
        </div>
        <div
          className="grid"
          style={{ gridTemplateColumns: `48px repeat(${days.length}, minmax(115px, 1fr))` }}
        >
          <div>
            {slots.map((offset) => (
              <div key={offset} className="h-8 pr-1 text-right text-[10px] text-muted-foreground">
                {clock(week + offset)}
              </div>
            ))}
          </div>
          {days.map((day, index) => (
            <div key={day} className="relative border-l border-border" style={{ height }}>
              {slots.map((offset) => (
                <button
                  key={offset}
                  data-calendar-slot={new Date(day + offset).toISOString()}
                  type="button"
                  className="block h-8 w-full border-t border-border/50 hover:bg-primary/10 focus-visible:bg-primary/15 focus-visible:outline-none"
                  aria-label={`${readOnly ? "Time slot" : "New session"} ${formatSingaporeDateTime(new Date(day + offset).toISOString())} SGT`}
                  onClick={() => {
                    if (!readOnly) onCreate(day + offset);
                  }}
                  onDragOver={(event) => {
                    if (readOnly) return;
                    event.preventDefault();
                    event.dataTransfer.dropEffect = "move";
                  }}
                  onDrop={(event) => drop(event, day + offset)}
                  disabled={readOnly || query.isPending || query.isError}
                />
              ))}
              {segments[index]!.map((block) => blockButton(block, true, day))}
            </div>
          ))}
        </div>
      </div>
      <div className="space-y-4 md:hidden">
        {days.map((day, index) => (
          <section key={day} className="rounded-xl border border-border p-3">
            <h4 className="mb-3 text-sm font-medium">
              {formatSingaporeDateTime(new Date(day).toISOString(), {
                weekday: "long",
                day: "numeric",
                month: "short",
              })}
            </h4>
            <div className="space-y-2">
              {segments[index]!.map((block) => blockButton(block, false, day))}
              {!segments[index]!.length && (
                <p className="text-xs text-muted-foreground">No sessions</p>
              )}
              {!readOnly && (
                <button className={control} onClick={() => onCreate(day + 10 * 3600000)}>
                  New session on this day
                </button>
              )}
            </div>
          </section>
        ))}
      </div>
      <AlertDialog
        open={!readOnly && !!move}
        onOpenChange={(open) => {
          if (!open && !saving) {
            setMove(null);
            setError(null);
          }
        }}
      >
        <AlertDialogContent className="bg-card">
          <AlertDialogHeader>
            <AlertDialogTitle>Move session?</AlertDialogTitle>
            <AlertDialogDescription>
              {move?.session.name}
              <br />
              Original: {move && formatSingaporeDateTime(move.session.starts_at)} SGT
              <br />
              Proposed: {move && formatSingaporeDateTime(new Date(move.start).toISOString())} SGT
            </AlertDialogDescription>
          </AlertDialogHeader>
          {error && (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          )}
          <AlertDialogFooter>
            <AlertDialogCancel disabled={saving}>Cancel</AlertDialogCancel>
            <button
              className="rounded-lg bg-primary px-4 py-2 text-sm text-primary-foreground disabled:opacity-50"
              disabled={saving}
              onClick={() => void confirmMove()}
            >
              {saving ? "Saving…" : "Confirm move"}
            </button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  );
}
