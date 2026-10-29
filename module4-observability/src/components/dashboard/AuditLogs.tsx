import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/hooks/useAuth";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { fetchUsers, type AdminUser } from "@/lib/admin";
import { downloadCsv } from "@/lib/attendance";
import { formatSingaporeDateTime } from "@/lib/time";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  auditActions,
  auditCsv,
  auditDetailPoints,
  auditFilterError,
  emptyAuditFilters,
  fetchAuditExport,
  fetchAuditPage,
  type AuditFilters,
  type AuditRow,
} from "@/lib/audit";

const control =
  "min-w-0 w-full rounded-lg border border-border bg-secondary/40 px-3 py-2 text-xs text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:opacity-50";
const button =
  "rounded-lg border border-border px-3 py-2 text-xs focus-visible:ring-2 focus-visible:ring-primary disabled:opacity-50";
const severityStyle: Record<string, string> = {
  info: "bg-accent/10 text-accent",
  warning: "bg-warning/10 text-warning",
  critical: "bg-destructive/10 text-destructive",
};

export function AuditLogs() {
  const { user, loading } = useAuth();
  const permitted = user?.role === "admin";
  const [draft, setDraft] = useState<AuditFilters>(emptyAuditFilters);
  const [filters, setFilters] = useState<AuditFilters>(emptyAuditFilters);
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(50);
  const [filterError, setFilterError] = useState("");
  const [userSearch, setUserSearch] = useState("");
  const search = useDebouncedValue(userSearch, 300).trim();
  const [userPage, setUserPage] = useState(0);
  const [pickedUser, setPickedUser] = useState<AdminUser | null>(null);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState("");
  const [selected, setSelected] = useState<AuditRow | null>(null);
  const exportController = useRef<AbortController | null>(null);
  const table = useRef<HTMLDivElement | null>(null);
  useEffect(() => () => exportController.current?.abort(), []);
  useEffect(() => {
    table.current?.scrollTo({ top: 0 });
    setSelected(null);
  }, [filters, page, pageSize]);
  const users = useQuery({
    queryKey: ["audit-user-options", user?.id, search, userPage],
    queryFn: ({ signal }) =>
      fetchUsers(
        new URLSearchParams({ search, limit: "25", offset: String(userPage * 25) }),
        signal,
      ),
    enabled: permitted && Boolean(search),
  });
  const q = useQuery({
    queryKey: ["audit-logs", user?.id, filters, pageSize, page],
    queryFn: ({ signal }) => fetchAuditPage(filters, pageSize, page * pageSize, signal),
    enabled: permitted,
    refetchInterval: 30000,
  });
  const rows = q.isError ? [] : (q.data?.items ?? []);
  const total = q.data?.total ?? 0;
  const userOptions = users.data?.items ?? [];
  const detailPoints = auditDetailPoints(selected?.details ?? null);
  function update<K extends keyof AuditFilters>(key: K, value: AuditFilters[K]) {
    setDraft((previous) => ({ ...previous, [key]: value }));
    setFilterError("");
  }
  async function exportCsv() {
    if (exportController.current) return;
    const controller = new AbortController();
    exportController.current = controller;
    setExporting(true);
    setExportError("");
    try {
      const records = await fetchAuditExport(filters, controller.signal);
      if (!controller.signal.aborted) downloadCsv("audit-trail", auditCsv(records));
    } catch (error) {
      if (!controller.signal.aborted)
        setExportError(error instanceof Error ? error.message : "Could not export audit logs.");
    } finally {
      exportController.current = null;
      setExporting(false);
    }
  }
  if (loading)
    return (
      <p role="status" className="p-5">
        Loading audit access…
      </p>
    );
  if (!permitted)
    return (
      <p role="alert" className="p-5 text-destructive">
        Audit logs are available to administrators only.
      </p>
    );
  return (
    <section className="animate-rise rounded-2xl border border-border bg-glass">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-5 py-4">
        <div>
          <h2 className="font-display text-sm font-medium text-card-foreground">Audit logs</h2>
          <p className="mt-1 text-xs text-muted-foreground">
            {q.isPending
              ? "Loading events…"
              : q.isError
                ? "Events unavailable"
                : `${total} matching events`}
          </p>
        </div>
        <button
          className="rounded-full bg-gradient-to-r from-primary to-accent px-3 py-1.5 text-xs font-medium text-primary-foreground transition hover:brightness-110 disabled:opacity-50"
          disabled={exporting || q.isPending || q.isError || total === 0}
          onClick={() => void exportCsv()}
        >
          {exporting ? "Exporting…" : "Export filtered CSV"}
        </button>
      </header>
      <form
        className="space-y-3 border-b border-border p-5"
        onSubmit={(event) => {
          event.preventDefault();
          const error = auditFilterError(draft);
          setFilterError(error);
          if (error) return;
          setFilters({ ...draft });
          setPage(0);
          setExportError("");
        }}
      >
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <label className="grid min-w-0 gap-1 text-xs">
            Find user by name or email
            <input
              className={control}
              value={userSearch}
              placeholder="Search all users"
              onChange={(event) => {
                setUserSearch(event.target.value);
                setUserPage(0);
              }}
            />
          </label>
          <label className="grid min-w-0 gap-1 text-xs">
            User
            <select
              className={control}
              value={draft.userId}
              onChange={(event) => {
                update("userId", event.target.value);
                setPickedUser(userOptions.find((item) => item.id === event.target.value) ?? null);
              }}
            >
              <option value="">All users, including system events</option>
              {pickedUser && !userOptions.some((item) => item.id === pickedUser.id) && (
                <option value={pickedUser.id}>
                  {pickedUser.full_name} · {pickedUser.email}
                </option>
              )}
              {userOptions.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.full_name} · {item.email}
                </option>
              ))}
            </select>
          </label>
          <label className="grid min-w-0 gap-1 text-xs">
            Action
            <select
              className={control}
              value={draft.action}
              onChange={(event) => update("action", event.target.value)}
            >
              <option value="">All actions</option>
              {auditActions.map((action) => (
                <option key={action} value={action}>
                  {action}
                </option>
              ))}
            </select>
          </label>
          <label className="grid min-w-0 gap-1 text-xs">
            Outcome
            <select
              className={control}
              value={draft.success}
              onChange={(event) => update("success", event.target.value)}
            >
              <option value="">All outcomes</option>
              <option value="true">Successful</option>
              <option value="false">Failed</option>
            </select>
          </label>
          <label className="grid min-w-0 gap-1 text-xs">
            Resource type
            <input
              className={control}
              list="audit-resource-types"
              value={draft.resourceType}
              placeholder="All resource types"
              onChange={(event) => update("resourceType", event.target.value)}
            />
            <datalist id="audit-resource-types">
              {[
                "user",
                "session",
                "checkin",
                "course",
                "enrollment",
                "device",
                "course_assistant",
              ].map((value) => (
                <option key={value} value={value} />
              ))}
            </datalist>
          </label>
          <label className="grid min-w-0 gap-1 text-xs">
            Resource ID
            <input
              className={control}
              value={draft.resourceId}
              placeholder="Resource UUID (optional)"
              onChange={(event) => update("resourceId", event.target.value)}
            />
          </label>
          <label className="grid min-w-0 gap-1 text-xs">
            From
            <input
              className={control}
              type="datetime-local"
              value={draft.startDate}
              onChange={(event) => update("startDate", event.target.value)}
            />
          </label>
          <label className="grid min-w-0 gap-1 text-xs">
            To
            <input
              className={control}
              type="datetime-local"
              value={draft.endDate}
              onChange={(event) => update("endDate", event.target.value)}
            />
          </label>
        </div>
        {search && (
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            {users.isPending ? (
              "Finding users…"
            ) : users.isError ? (
              <span role="alert">
                Could not find users.{" "}
                <button type="button" className={button} onClick={() => void users.refetch()}>
                  Retry user search
                </button>
              </span>
            ) : (
              <>
                <span>{users.data?.total ?? 0} matching users · select a user above</span>
                <button
                  type="button"
                  className={button}
                  disabled={userPage === 0 || users.isFetching}
                  onClick={() => setUserPage(userPage - 1)}
                >
                  Previous users
                </button>
                <button
                  type="button"
                  className={button}
                  disabled={
                    users.isFetching || !users.data || (userPage + 1) * 25 >= users.data.total
                  }
                  onClick={() => setUserPage(userPage + 1)}
                >
                  Next users
                </button>
              </>
            )}
          </div>
        )}
        {filterError && (
          <p role="alert" className="text-sm text-destructive">
            {filterError}
          </p>
        )}
        <div className="flex flex-wrap gap-2">
          <button className={button} disabled={exporting}>
            Apply filters
          </button>
          <button
            type="button"
            className={button}
            disabled={exporting}
            onClick={() => {
              setDraft({ ...emptyAuditFilters });
              setFilters({ ...emptyAuditFilters });
              setPage(0);
              setUserSearch("");
              setUserPage(0);
              setPickedUser(null);
              setFilterError("");
              setExportError("");
            }}
          >
            Reset filters
          </button>
        </div>
      </form>
      {exportError && (
        <p role="alert" className="px-5 py-3 text-sm text-destructive">
          {exportError}
        </p>
      )}
      {q.isError && (
        <p role="alert" className="px-5 py-3 text-sm text-destructive">
          Could not load audit logs. {q.error instanceof Error ? q.error.message : ""}{" "}
          <button className={button} onClick={() => void q.refetch()}>
            Retry
          </button>
        </p>
      )}
      <div className="flex items-center justify-between gap-3 border-b border-border px-5 py-3 text-xs">
        <p className="font-medium">
          Activity history{" "}
          <span className="font-normal text-muted-foreground">
            · {q.isSuccess ? `${total} events` : q.isError ? "Unavailable" : "Loading…"}
          </span>
        </p>
        <span className="text-muted-foreground">Newest first</span>
      </div>
      <div
        ref={table}
        className="max-h-[85vh] overflow-auto"
        role="region"
        aria-label="Audit events"
        tabIndex={0}
      >
        <table className="w-full min-w-[1050px] text-left text-sm">
          <thead className="sticky top-0 z-10 bg-card">
            <tr className="text-[10px] uppercase tracking-wider text-muted-foreground">
              {[
                "Timestamp",
                "User",
                "Action",
                "Resource",
                "Severity",
                "Outcome",
                "Details",
              ].map((title) => (
                <th
                  key={title}
                  className="px-5 py-3 font-medium"
                  aria-sort={title === "Timestamp" ? "descending" : undefined}
                >
                  {title}
                  {title === "Timestamp" && <span aria-hidden="true"> ↓</span>}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {q.isPending && (
              <tr>
                <td colSpan={7} className="px-5 py-6" role="status">
                  Loading events…
                </td>
              </tr>
            )}
            {q.isSuccess && !rows.length && (
              <tr>
                <td colSpan={7} className="px-5 py-6 text-muted-foreground">
                  No events match these filters.
                </td>
              </tr>
            )}
            {rows.map((row) => (
              <tr key={row.id} className="transition-colors hover:bg-secondary/50">
                <td className="whitespace-nowrap px-5 py-3 text-xs">
                  <span className="block font-medium">
                    {formatSingaporeDateTime(row.timestamp, {
                      hour: "2-digit",
                      minute: "2-digit",
                      hourCycle: "h23",
                    })}
                  </span>
                  <span className="mt-1 block text-[10px] text-muted-foreground">
                    {formatSingaporeDateTime(row.timestamp, {
                      day: "numeric",
                      month: "short",
                      year: "numeric",
                    })}
                  </span>
                </td>
                <td className="px-5 py-3 text-xs">
                  <span className="font-medium">{row.user_email ?? "System / unknown"}</span>
                </td>
                <td className="px-5 py-3 text-xs">
                  <span className="block font-medium">{row.action.replace(/_/g, " ")}</span>
                  <span className="mt-1 block text-[10px] text-muted-foreground">{row.action}</span>
                </td>
                <td className="px-5 py-3 text-xs">{row.resource_type ?? "—"}</td>
                <td className="px-5 py-3">
                  <span
                    className={`rounded-full px-2 py-0.5 text-[11px] ${severityStyle[row.severity] ?? "bg-secondary text-muted-foreground"}`}
                  >
                    {row.severity}
                  </span>
                </td>
                <td className="px-5 py-3">
                  <span
                    className={`rounded-full px-2 py-0.5 text-[11px] ${row.success ? "bg-accent/10 text-accent" : "bg-destructive/10 text-destructive"}`}
                  >
                    {row.success ? "Success" : "Failed"}
                  </span>
                </td>
                <td className="px-5 py-3 text-xs">
                  <button
                    type="button"
                    className="rounded text-primary underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                    aria-label={`View details for ${row.action} at ${row.timestamp}`}
                    onClick={() => setSelected(row)}
                  >
                    View
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-border px-5 py-4 text-xs">
        <span>
          {q.isSuccess
            ? total
              ? `${page * pageSize + 1}–${page * pageSize + rows.length} of ${total} events`
              : "0 events"
            : ""}
        </span>
        <div className="flex flex-wrap items-center gap-3">
          <label>
            Rows per page{" "}
            <select
              className={button}
              value={pageSize}
              onChange={(event) => {
                setPageSize(Number(event.target.value));
                setPage(0);
              }}
            >
              {[25, 50, 100].map((size) => (
                <option key={size} value={size}>
                  {size}
                </option>
              ))}
            </select>
          </label>
          <button
            className={button}
            disabled={page === 0 || q.isFetching}
            onClick={() => setPage(page - 1)}
          >
            Previous
          </button>
          <span>
            Page {page + 1} of {Math.max(1, Math.ceil(total / pageSize))}
          </span>
          <button
            className={button}
            disabled={!q.isSuccess || q.isFetching || (page + 1) * pageSize >= total}
            onClick={() => setPage(page + 1)}
          >
            Next
          </button>
        </div>
      </footer>
      <Dialog
        open={selected !== null}
        onOpenChange={(open) => {
          if (!open) setSelected(null);
        }}
      >
        {selected && (
          <DialogContent className="max-h-[85vh] overflow-y-auto border-border bg-card text-card-foreground sm:max-w-2xl">
            <DialogHeader>
              <DialogTitle>Event details</DialogTitle>
              <DialogDescription>
                {selected.action.replace(/_/g, " ")} · {formatSingaporeDateTime(selected.timestamp)}{" "}
                SGT
              </DialogDescription>
            </DialogHeader>
            <dl className="grid gap-3 text-xs sm:grid-cols-2">
              {[
                ["Event ID", selected.id],
                ["Timestamp (UTC)", selected.timestamp],
                ["User", selected.user_email ?? "System / unknown"],
                ["User ID", selected.user_id ?? "No user identity"],
                ["Action", selected.action],
                ["Severity", selected.severity],
                ["Resource type", selected.resource_type ?? "—"],
                ["Resource ID", selected.resource_id ?? "—"],
                ["Outcome", selected.success ? "Success" : "Failed"],
                ["IP address", selected.ip_address ?? "—"],
                ["Device ID", selected.device_id ?? "—"],
                ["User agent", selected.user_agent ?? "—"],
              ].map(([label, value]) => (
                <div key={label} className="min-w-0">
                  <dt className="text-muted-foreground">{label}</dt>
                  <dd className="mt-1 break-words">{value}</dd>
                </div>
              ))}
            </dl>
            <div>
              <h3 className="mb-2 text-xs font-medium">Details</h3>
              <div className="max-h-64 overflow-auto break-words rounded-lg border border-border bg-secondary/40 p-3 text-xs">
                {detailPoints.length ? (
                  <ul className="list-disc space-y-2 pl-4">
                    {detailPoints.map((point, index) => (
                      <li key={index}>{point}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-muted-foreground">No additional details.</p>
                )}
              </div>
            </div>
          </DialogContent>
        )}
      </Dialog>
    </section>
  );
}
