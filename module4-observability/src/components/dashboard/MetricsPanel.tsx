import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { KpiCard } from "./KpiCard";
import type { CheckInRow } from "./AttendanceTable";

type Metric = {
  id: string;
  recorded_at: string;
  endpoint: string;
  p95_ms: number;
  request_count: number;
  success_rate: number;
};

export function MetricsPanel({ rows }: { rows: CheckInRow[] }) {
  const q = useQuery({
    queryKey: ["api-metrics"],
    refetchInterval: 30000,
    queryFn: async () => {
      const result = await api.request<{ items: Metric[] }>("/metrics/?limit=120");
      return result.items;
    },
  });

  const metrics = q.data ?? [];
  const p95 = metrics.length
    ? Math.round(metrics.reduce((s, m) => s + m.p95_ms, 0) / metrics.length)
    : 0;
  const requests = metrics.reduce((s, m) => s + m.request_count, 0);
  const success = metrics.length
    ? metrics.reduce((s, m) => s + Number(m.success_rate), 0) / metrics.length
    : 0;
  const healthy = p95 < 400 && success > 97;

  const buckets = [
    { label: "0–20", min: 0, max: 20, dot: "bg-accent" },
    { label: "21–40", min: 21, max: 40, dot: "bg-accent" },
    { label: "41–60", min: 41, max: 60, dot: "bg-warning" },
    { label: "61–80", min: 61, max: 80, dot: "bg-warning" },
    { label: "81–100", min: 81, max: 100, dot: "bg-destructive" },
  ].map((b) => ({ ...b, count: rows.filter((r) => r.risk >= b.min && r.risk <= b.max).length }));
  const maxBucket = Math.max(1, ...buckets.map((b) => b.count));
  const highRisk = rows.filter((r) => r.risk > 70);

  const byEndpoint = [...new Set(metrics.map((m) => m.endpoint))].map((e) => {
    const list = metrics.filter((m) => m.endpoint === e);
    return {
      endpoint: e,
      p95: Math.round(list.reduce((s, m) => s + m.p95_ms, 0) / list.length),
      requests: list.reduce((s, m) => s + m.request_count, 0),
      success: list.reduce((s, m) => s + Number(m.success_rate), 0) / list.length,
    };
  });

  return (
    <>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        <KpiCard
          label="API p95 latency"
          value={`${p95} ms`}
          note="across all endpoints, last 12h"
          tone={p95 > 400 ? "warning" : "accent"}
          progress={Math.min(100, (p95 / 600) * 100)}
        />
        <KpiCard
          label="Request rate"
          value={`${Math.round(requests / 12)}/h`}
          note={`${requests} requests in 12 hours`}
          tone="brand"
          bars={[40, 62, 51, 78, 66, 100]}
        />
        <KpiCard
          label="Success rate"
          value={`${success.toFixed(1)}%`}
          note="successful API responses"
          tone={success < 97 ? "warning" : "accent"}
          progress={success}
        />
        <KpiCard
          label="System health"
          value={healthy ? "Healthy" : "Degraded"}
          note={`${highRisk.length} high-risk alerts`}
          tone={healthy ? "accent" : "danger"}
          progress={healthy ? 100 : 55}
        />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-12">
        <div className="animate-rise rounded-2xl border border-border bg-glass p-5 lg:col-span-5">
          <p className="font-display text-sm font-medium text-card-foreground">
            Risk score distribution
          </p>
          <div className="mt-4 space-y-3">
            {buckets.map((b) => (
              <div key={b.label} className="flex items-center gap-3 text-xs">
                <span className="w-14 text-muted-foreground">{b.label}</span>
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-secondary">
                  <div
                    className={`h-full rounded-full ${b.dot}`}
                    style={{ width: `${(b.count / maxBucket) * 100}%` }}
                  />
                </div>
                <span className="w-6 text-right tabular-nums text-foreground">{b.count}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="animate-rise rounded-2xl border border-border bg-glass p-5 lg:col-span-7">
          <p className="font-display text-sm font-medium text-card-foreground">Endpoint metrics</p>
          <table className="mt-3 w-full text-left text-sm">
            <thead>
              <tr className="text-[10px] uppercase tracking-wider text-muted-foreground">
                <th className="py-2 font-medium">Endpoint</th>
                <th className="py-2 text-right font-medium">p95</th>
                <th className="py-2 text-right font-medium">Requests</th>
                <th className="py-2 text-right font-medium">Success</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {byEndpoint.map((e) => (
                <tr key={e.endpoint}>
                  <td className="py-2.5 text-foreground">{e.endpoint}</td>
                  <td className="py-2.5 text-right tabular-nums text-muted-foreground">
                    {e.p95} ms
                  </td>
                  <td className="py-2.5 text-right tabular-nums text-muted-foreground">
                    {e.requests}
                  </td>
                  <td className="py-2.5 text-right tabular-nums text-accent">
                    {e.success.toFixed(1)}%
                  </td>
                </tr>
              ))}
              {byEndpoint.length === 0 && (
                <tr>
                  <td colSpan={4} className="py-4 text-xs text-muted-foreground">
                    No metrics recorded yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="mt-4 animate-rise rounded-2xl border border-border bg-glass p-5">
        <p className="font-display text-sm font-medium text-card-foreground">High-risk alerts</p>
        <p className="mt-0.5 text-xs text-muted-foreground">Check-ins scoring above 70</p>
        <ul className="mt-3 space-y-2">
          {highRisk.slice(0, 8).map((r) => (
            <li
              key={r.id}
              className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-destructive/20 bg-destructive/5 px-4 py-2.5 text-xs"
            >
              <span className="text-foreground">
                {r.student} · {r.course}
              </span>
              <span className="text-muted-foreground">
                liveness {r.liveness} · face match {r.faceMatch}
              </span>
              <span className="tabular-nums text-destructive">risk {r.risk}</span>
            </li>
          ))}
          {highRisk.length === 0 && (
            <li className="text-xs text-muted-foreground">No high-risk check-ins right now.</li>
          )}
        </ul>
      </div>
    </>
  );
}
