import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { KpiCard } from "./KpiCard";
import type { CheckInRow } from "./AttendanceTable";

const grafanaUrl = import.meta.env["VITE_GRAFANA_URL"] ?? "http://localhost:3001";

type Metric = {
  id: string;
  recorded_at: string;
  endpoint: string;
  p95_ms: number;
  request_count: number;
  error_count: number;
  success_rate: number;
};

export function MetricsPanel({
  showGrafanaLink = false,
}: {
  rows?: CheckInRow[];
  showGrafanaLink?: boolean;
} = {}) {
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
  const errors = metrics.reduce((s, m) => s + m.error_count, 0);
  const errorRate = requests ? (errors / requests) * 100 : 0;

  const byEndpoint = [...new Set(metrics.map((m) => m.endpoint))].map((e) => {
    const list = metrics.filter((m) => m.endpoint === e);
    return {
      endpoint: e,
      p95: Math.round(list.reduce((s, m) => s + m.p95_ms, 0) / list.length),
      requests: list.reduce((s, m) => s + m.request_count, 0),
      errors: list.reduce((s, m) => s + m.error_count, 0),
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
          label="Error rate"
          value={`${errorRate.toFixed(1)}%`}
          note={`${errors} 5xx server errors`}
          tone={errorRate >= 3 ? "warning" : "accent"}
          progress={Math.min(100, errorRate * 10)}
        />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-12">
        <div className="animate-rise rounded-2xl border border-border bg-glass p-5 lg:col-span-12">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="font-display text-sm font-medium text-card-foreground">Endpoint metrics</p>
            {showGrafanaLink && (
              <a
                href={`${grafanaUrl}/d/saiv-technical/saiv-technical?kiosk=1`}
                target="_blank"
                rel="noreferrer"
                className="text-xs text-primary underline-offset-4 hover:underline"
              >
                Open Grafana technical dashboard
              </a>
            )}
          </div>
          <table className="mt-3 w-full text-left text-sm">
            <thead>
              <tr className="text-[10px] uppercase tracking-wider text-muted-foreground">
                <th className="py-2 font-medium">Endpoint</th>
                <th className="py-2 text-right font-medium">p95</th>
                <th className="py-2 text-right font-medium">Requests</th>
                <th className="py-2 text-right font-medium">Error rate</th>
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
                    {e.requests ? ((e.errors / e.requests) * 100).toFixed(1) : "0.0"}%
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

    </>
  );
}
