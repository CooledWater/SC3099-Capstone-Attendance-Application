import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { downloadCsv } from "@/lib/attendance";
import { formatSingaporeDateTime } from "@/lib/time";

type AuditRow = {
  id: string;
  timestamp: string;
  action: string;
  user_email: string | null;
  severity: string;
  details: Record<string, unknown> | null;
};

const severityStyle: Record<string, string> = {
  info: "bg-accent/10 text-accent",
  warning: "bg-warning/10 text-warning",
  critical: "bg-destructive/10 text-destructive",
};

export function AuditLogs() {
  const [type, setType] = useState("all");
  const [severity, setSeverity] = useState("all");
  const [actor, setActor] = useState("");

  const q = useQuery({
    queryKey: ["audit-logs"],
    refetchInterval: 30000,
    queryFn: async () => {
      const result = await api.request<{ items: AuditRow[] }>("/audit/?limit=200");
      return result.items;
    },
  });

  const all = q.data ?? [];
  const types = useMemo(() => ["all", ...new Set(all.map((r) => r.action))], [all]);

  const visible = all.filter(
    (r) =>
      (type === "all" || r.action === type) &&
      (severity === "all" || r.severity === severity) &&
      (actor === "" || (r.user_email ?? "system").toLowerCase().includes(actor.toLowerCase())),
  );

  function exportCsv() {
    const esc = (v: string) => `"${v.replace(/"/g, '""')}"`;
    const csv = [
      ["timestamp", "user_email", "action", "severity", "details"].map(esc).join(","),
      ...visible.map((r) =>
        [r.timestamp, r.user_email ?? "", r.action, r.severity, r.details ? JSON.stringify(r.details) : ""]
          .map(esc)
          .join(","),
      ),
    ].join("\n");
    downloadCsv("audit-trail", "\uFEFF" + csv);
  }

  return (
    <div className="animate-rise rounded-2xl border border-border bg-glass">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-5 py-4">
        <div>
          <p className="font-display text-sm font-medium text-card-foreground">Audit logs</p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {visible.length} system events · colour-coded by severity
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <input
            value={actor}
            onChange={(e) => setActor(e.target.value)}
            placeholder="Filter by user…"
            className="rounded-full border border-border bg-glass px-3 py-1.5 text-xs text-foreground outline-none placeholder:text-muted-foreground focus:border-primary/40"
          />
          <select
            value={type}
            onChange={(e) => setType(e.target.value)}
            className="rounded-full border border-border bg-glass px-3 py-1.5 text-xs text-foreground outline-none"
          >
            {types.map((t) => (
              <option key={t} value={t} className="bg-card">
                {t === "all" ? "All actions" : t}
              </option>
            ))}
          </select>
          <select
            value={severity}
            onChange={(e) => setSeverity(e.target.value)}
            className="rounded-full border border-border bg-glass px-3 py-1.5 text-xs text-foreground outline-none"
          >
            {["all", "info", "warning", "critical"].map((s) => (
              <option key={s} value={s} className="bg-card">
                {s === "all" ? "All severities" : s}
              </option>
            ))}
          </select>
          <button
            onClick={exportCsv}
            className="rounded-full bg-gradient-to-r from-primary to-accent px-3 py-1.5 text-xs font-medium text-primary-foreground transition hover:brightness-110"
          >
            Export trail
          </button>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[760px] text-left text-sm">
          <thead>
            <tr className="text-[10px] uppercase tracking-wider text-muted-foreground">
              {["Timestamp", "User email", "Action", "Severity", "Details"].map((h) => (
                <th key={h} className="px-5 py-3 font-medium">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {q.isLoading && (
              <tr>
                <td colSpan={5} className="px-5 py-6 text-sm text-muted-foreground">
                  Loading events…
                </td>
              </tr>
            )}
            {!q.isLoading && visible.length === 0 && (
              <tr>
                <td colSpan={5} className="px-5 py-6 text-sm text-muted-foreground">
                  No events match these filters.
                </td>
              </tr>
            )}
            {visible.map((r) => (
              <tr key={r.id} className="transition-colors hover:bg-secondary/50">
                <td className="px-5 py-3 text-muted-foreground">
                  {formatSingaporeDateTime(r.timestamp)} SGT
                </td>
                <td className="px-5 py-3 text-muted-foreground">{r.user_email ?? "system"}</td>
                <td className="px-5 py-3 font-medium text-foreground">{r.action}</td>
                <td className="px-5 py-3">
                  <span
                    className={`rounded-full px-2 py-0.5 text-[11px] ${
                      severityStyle[r.severity] ?? "bg-secondary text-muted-foreground"
                    }`}
                  >
                    {r.severity}
                  </span>
                </td>
                <td className="max-w-md break-words px-5 py-3 text-xs text-muted-foreground">
                  {r.details ? JSON.stringify(r.details) : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
