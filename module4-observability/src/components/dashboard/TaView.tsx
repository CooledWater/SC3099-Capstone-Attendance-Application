import { useQuery } from "@tanstack/react-query";
import { fetchSessions, fetchCheckIns, toRows } from "@/lib/attendance";
import { CheckInsPanel } from "./CheckInsPanel";

/** The API has no course-staff mutation endpoint, so this is intentionally read-only. */
export function TaView({ userId: _userId }: { userId: string }) {
  const sessions = useQuery({ queryKey: ["sessions"], queryFn: fetchSessions });
  const checkIns = useQuery({
    queryKey: ["check-ins"],
    queryFn: fetchCheckIns,
    refetchInterval: 30000,
  });
  const rows = toRows(checkIns.data ?? []);
  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-border bg-glass p-5">
        <p className="font-display text-sm font-medium text-card-foreground">
          Teaching assistant console
        </p>
        <p className="mt-1 text-xs text-muted-foreground">
          Sessions and check-ins are loaded from the SAIV API. Course-assignment management will
          appear when your backend exposes it.
        </p>
      </div>
      {sessions.isError || checkIns.isError ? (
        <p className="rounded-xl border border-warning/30 bg-warning/10 p-4 text-sm text-warning">
          Your backend has not granted this account access to the required session data yet.
        </p>
      ) : (
        <CheckInsPanel rows={rows} loading={checkIns.isLoading} />
      )}
    </div>
  );
}
