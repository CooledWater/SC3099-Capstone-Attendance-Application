import { Check, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { parseApiDateTime } from "@/lib/time";
import type { SessionStats } from "@/lib/ta-overview";

type ReviewEvent = SessionStats["recent_review_activity"][number];

function timestampLabel(value: string, timeZone: string) {
  const date = parseApiDateTime(value);
  if (Number.isNaN(date.getTime())) return "Time unavailable";
  const day = new Intl.DateTimeFormat("en-SG", { timeZone, day: "numeric", month: "short" }).format(
    date,
  );
  const time = new Intl.DateTimeFormat("en-SG", {
    timeZone,
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  })
    .format(date)
    .toLowerCase()
    .replace(/\s+/g, " ");
  const zone =
    timeZone === "Asia/Singapore"
      ? "SGT"
      : (new Intl.DateTimeFormat("en-SG", { timeZone, timeZoneName: "short" })
          .formatToParts(date)
          .find((part) => part.type === "timeZoneName")?.value ?? timeZone);
  return `${day} · ${time} ${zone}`;
}

export function RecentReviewActivity({
  sessionId,
  sessionName,
  courseCode,
  timeZone = "Asia/Singapore",
  events,
  loading,
  error,
  onRetry,
}: {
  sessionId: string;
  sessionName: string;
  courseCode?: string;
  timeZone?: string;
  events: ReviewEvent[];
  loading: boolean;
  error: boolean;
  onRetry: () => void;
}) {
  const shown = events
    .filter(
      (event) =>
        event.session_id === sessionId &&
        event.action === "checkin_reviewed" &&
        (event.decision === "approved" || event.decision === "rejected"),
    )
    .slice()
    .sort((a, b) => {
      const first = parseApiDateTime(a.timestamp).getTime();
      const second = parseApiDateTime(b.timestamp).getTime();
      if (!Number.isFinite(first)) return Number.isFinite(second) ? 1 : 0;
      if (!Number.isFinite(second)) return -1;
      return second - first || b.id.localeCompare(a.id);
    })
    .slice(0, 5);

  return (
    <section
      aria-label="Recent review activity"
      className="min-w-0 rounded-2xl border border-border bg-card p-5"
    >
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="font-display text-sm font-semibold text-card-foreground">
            Recent review activity
          </h2>
          <p className="mt-1 break-words text-xs text-muted-foreground">
            {sessionName}
            {!loading &&
              !error &&
              ` · ${shown.length} ${shown.length === 1 ? "review" : "reviews"} shown`}
          </p>
        </div>
        {courseCode && (
          <Badge
            variant="outline"
            className="max-w-full break-all border-transparent bg-primary/15 text-[10px] font-medium text-primary"
          >
            {courseCode}
          </Badge>
        )}
      </header>
      {loading ? (
        <div
          role="status"
          aria-label="Loading review activity"
          className="mt-4 space-y-4 border-t border-border pt-4"
        >
          {[0, 1].map((index) => (
            <div key={index} className="flex items-start gap-3" aria-hidden="true">
              <Skeleton className="size-8 shrink-0 rounded-lg" />
              <div className="min-w-0 flex-1 space-y-2">
                <Skeleton className="h-3 w-36 max-w-full" />
                <Skeleton className="h-2.5 w-24 max-w-full" />
                <Skeleton className="h-2.5 w-32 max-w-full" />
              </div>
            </div>
          ))}
        </div>
      ) : error ? (
        <div
          role="alert"
          className="mt-4 border-t border-border pt-4 text-xs text-muted-foreground"
        >
          <p>Could not load review activity.</p>
          <button
            type="button"
            onClick={onRetry}
            className="mt-2 rounded text-primary underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          >
            Retry
          </button>
        </div>
      ) : !shown.length ? (
        <p className="mt-4 border-t border-border pt-4 text-xs text-muted-foreground">
          No review activity yet
        </p>
      ) : (
        <ul className="mt-4 divide-y divide-border border-t border-border">
          {shown.map((event) => {
            const approved = event.decision === "approved";
            const Icon = approved ? Check : X;
            const color = approved
              ? "bg-emerald-400/15 text-emerald-300"
              : "bg-rose-400/15 text-rose-300";
            return (
              <li key={event.id} className="flex items-start gap-3 py-4 last:pb-0">
                <span
                  aria-hidden="true"
                  className={`grid size-8 shrink-0 place-items-center rounded-lg ${color}`}
                >
                  <Icon className="size-4" />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-2">
                    <p className="min-w-0 flex-1 break-words text-xs font-semibold text-foreground">
                      Check-in {event.decision}
                      {event.student_name && ` · ${event.student_name}`}
                    </p>
                    <Badge
                      variant="outline"
                      className={`shrink-0 border-transparent text-[10px] font-medium ${color}`}
                    >
                      {approved ? "Approved" : "Rejected"}
                    </Badge>
                  </div>
                  <p className="mt-1 break-words text-xs text-muted-foreground">
                    {event.session_name}
                  </p>
                  <time
                    dateTime={event.timestamp}
                    className="mt-1.5 block text-[11px] text-muted-foreground"
                  >
                    {timestampLabel(event.timestamp, timeZone)}
                  </time>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
