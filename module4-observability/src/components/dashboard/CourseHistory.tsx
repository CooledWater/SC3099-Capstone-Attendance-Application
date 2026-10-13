import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ApiError } from "@/lib/api";
import { submitCheckInAppeal } from "@/lib/attendance";
import { formatSingaporeDateTime, parseApiDateTime } from "@/lib/time";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import type { CheckInRow } from "./AttendanceTable";

const appealWindowMs = 7 * 24 * 60 * 60 * 1000;

const statusLabel: Record<CheckInRow["status"], string> = {
  approved: "Approved",
  flagged: "Flagged",
  rejected: "Rejected",
  pending: "Pending",
  appealed: "Appealed",
};

const statusTone: Record<CheckInRow["status"], string> = {
  approved: "bg-accent/15 text-accent border-accent/25",
  flagged: "bg-warning/15 text-warning border-warning/25",
  rejected: "bg-destructive/15 text-destructive border-destructive/25",
  pending: "bg-primary/15 text-primary border-primary/25",
  appealed: "bg-warning/15 text-warning border-warning/25",
};

export function CourseHistory({ rows }: { rows: CheckInRow[] }) {
  const courses = useMemo(() => [...new Set(rows.map((r) => r.course))].sort(), [rows]);
  const [course, setCourse] = useState<string>("all");
  const [selectedCheckIn, setSelectedCheckIn] = useState<CheckInRow | null>(null);
  const [appealReason, setAppealReason] = useState("");
  const queryClient = useQueryClient();
  const appeal = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) => submitCheckInAppeal(id, reason),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["my-check-ins"] });
      setSelectedCheckIn(null);
      setAppealReason("");
      toast.success("Appeal submitted.");
    },
  });

  const filtered = useMemo(
    () =>
      (course === "all" ? rows : rows.filter((r) => r.course === course))
        .slice()
        .sort((a, b) => +new Date(b.time) - +new Date(a.time)),
    [rows, course],
  );

  function canAppeal(row: CheckInRow) {
    if (row.status !== "flagged" && row.status !== "rejected") return false;
    const checkedInAt = parseApiDateTime(row.time).getTime();
    const age = Date.now() - checkedInAt;
    return Number.isFinite(checkedInAt) && age >= 0 && age <= appealWindowMs;
  }

  function submitAppeal(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const reason = appealReason.trim();
    if (!selectedCheckIn || !reason || appeal.isPending) return;
    appeal.mutate({ id: selectedCheckIn.id, reason });
  }

  const appealError =
    appeal.error instanceof ApiError && appeal.error.status === 404
      ? "The appeal endpoint or check-in record was not found. Backend appeal support may still be pending."
      : appeal.error instanceof Error
        ? appeal.error.message
        : null;

  return (
    <>
      <section className="lg:col-span-8 rounded-2xl border border-border bg-card/60 p-5 shadow-[var(--shadow-glass)] backdrop-blur">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="font-display text-base text-foreground">Check-in history</h2>
            <p className="text-xs text-muted-foreground">
              {filtered.length} record{filtered.length === 1 ? "" : "s"}
              {course === "all" ? " across your courses" : ` in ${course}`}
            </p>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {["all", ...courses].map((c) => (
              <button
                key={c}
                onClick={() => setCourse(c)}
                className={`rounded-full border px-3 py-1 text-xs transition ${
                  course === c
                    ? "border-primary/40 bg-primary/15 text-foreground"
                    : "border-border bg-background/40 text-muted-foreground hover:text-foreground"
                }`}
              >
                {c === "all" ? "All courses" : c}
              </button>
            ))}
          </div>
        </div>

        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[650px] text-left text-sm">
            <thead>
              <tr className="text-xs uppercase tracking-wide text-muted-foreground">
                <th className="pb-2 font-medium">Course</th>
                <th className="pb-2 font-medium">Checked in</th>
                <th className="pb-2 font-medium">Room</th>
                <th className="pb-2 font-medium">Status</th>
                <th className="pb-2 font-medium">Action</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((r) => {
                return (
                  <tr key={r.id} className="border-t border-border/60">
                    <td className="py-2.5 pr-3 text-foreground">{r.course}</td>
                    <td className="py-2.5 pr-3 text-muted-foreground">
                      {formatSingaporeDateTime(r.time, {
                        day: "2-digit",
                        month: "short",
                        year: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}{" "}
                      SGT
                    </td>
                    <td className="py-2.5 pr-3 text-muted-foreground">{r.room}</td>
                    <td className="py-2.5">
                      <span
                        className={`rounded-full border px-2 py-0.5 text-xs ${statusTone[r.status]}`}
                      >
                        {statusLabel[r.status]}
                      </span>
                    </td>
                    <td className="py-2.5">
                      {canAppeal(r) && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            setSelectedCheckIn(r);
                            setAppealReason("");
                            appeal.reset();
                          }}
                        >
                          Appeal
                        </Button>
                      )}
                    </td>
                  </tr>
                );
              })}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={5} className="py-8 text-center text-sm text-muted-foreground">
                    No check-ins recorded yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <Dialog
        open={selectedCheckIn !== null}
        onOpenChange={(open) => {
          if (!open && !appeal.isPending) {
            setSelectedCheckIn(null);
            setAppealReason("");
            appeal.reset();
          }
        }}
      >
        <DialogContent className="border-border bg-card text-card-foreground">
          <DialogHeader>
            <DialogTitle className="font-display">Appeal check-in</DialogTitle>
            <DialogDescription>
              Explain why this {selectedCheckIn?.status} check-in should be reviewed. Appeals must
              be submitted within 7 days of the check-in.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={submitAppeal} className="space-y-4">
            <label className="block text-sm font-medium text-foreground" htmlFor="appeal-reason">
              Reason
              <Textarea
                id="appeal-reason"
                className="mt-2 border-border bg-background text-foreground"
                value={appealReason}
                onChange={(event) => setAppealReason(event.target.value)}
                placeholder="Describe what happened and why you are appealing."
                required
                rows={5}
                disabled={appeal.isPending}
              />
            </label>
            {appealError && (
              <p
                role="alert"
                className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive"
              >
                {appealError}
              </p>
            )}
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                disabled={appeal.isPending}
                onClick={() => {
                  setSelectedCheckIn(null);
                  setAppealReason("");
                  appeal.reset();
                }}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={!appealReason.trim() || appeal.isPending}>
                {appeal.isPending ? "Submitting…" : "Submit appeal"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
