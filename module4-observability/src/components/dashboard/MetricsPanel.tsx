import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { KpiCard } from "./KpiCard";

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

export function MetricsPanel() {
  const q = useQuery({
    queryKey: ["api-metrics"],
    refetchInterval: 30000,
    queryFn: async () => {
      const result = await api.request<{ items: Metric[] }>("/metrics/?limit=120");
      return result.items;
    },
  });

  const latency = useQuery({
    queryKey: ["api-latency", 1],
    queryFn: () => api.request<{ p95_ms: number | null }>("/metrics/latency"),
    refetchInterval: 30000,
  });
  const p95 = latency.data?.p95_ms;
  const requestRate = useQuery({
    queryKey: ["api-request-rate", 1],
    queryFn: () => api.request<{ requests_per_hour: number | null }>("/metrics/request-rate"),
    refetchInterval: 30000,
  });
  const hourlyRate = requestRate.data?.requests_per_hour;
  const errorRateQuery = useQuery({
    queryKey: ["api-error-rate", 1],
    queryFn: () => api.request<{ error_rate_percent: number | null }>("/metrics/error-rate"),
    refetchInterval: 30000,
  });
  const errorRate = errorRateQuery.data?.error_rate_percent;
  const metrics = q.data ?? [];

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
          value={
            latency.isError
              ? "Unavailable"
              : latency.isPending
                ? "Loading…"
                : p95 == null
                  ? "No data"
                  : `${Math.round(p95)} ms`
          }
          note="across all endpoints, last 1h"
          tone={p95 != null && p95 > 400 ? "warning" : "accent"}
        />
        {latency.isError && (
          <p role="alert" className="lg:col-span-12 text-sm text-destructive">
            Could not load latency.{" "}
            <button type="button" className="underline" onClick={() => void latency.refetch()}>
              Retry
            </button>
          </p>
        )}
        <KpiCard
          label="Request rate"
          value={
            requestRate.isError
              ? "Unavailable"
              : requestRate.isPending
                ? "Loading…"
                : hourlyRate == null
                  ? "No data"
                  : `${Math.round(hourlyRate)}/h`
          }
          note="across all endpoints, last 1h"
          tone="brand"
          bars={[40, 62, 51, 78, 66, 100]}
        />
        {requestRate.isError && (
          <p role="alert" className="lg:col-span-12 text-sm text-destructive">
            Could not load request rate.{" "}
            <button type="button" className="underline" onClick={() => void requestRate.refetch()}>
              Retry
            </button>
          </p>
        )}
        <KpiCard
          label="Error rate"
          value={
            errorRateQuery.isError
              ? "Unavailable"
              : errorRateQuery.isPending
                ? "Loading…"
                : errorRate == null
                  ? "No data"
                  : `${errorRate.toFixed(1)}%`
          }
          note="5xx errors across all endpoints, last 1h"
          tone={errorRate != null && errorRate >= 3 ? "warning" : "accent"}
          progress={Math.min(100, (errorRate ?? 0) * 10)}
        />
        {errorRateQuery.isError && (
          <p role="alert" className="lg:col-span-12 text-sm text-destructive">
            Could not load error rate.{" "}
            <button
              type="button"
              className="underline"
              onClick={() => void errorRateQuery.refetch()}
            >
              Retry
            </button>
          </p>
        )}
      </div>

      <section className="mt-4 overflow-hidden rounded-2xl border border-border bg-glass">
        <h2 className="px-5 pt-5 font-display text-sm font-medium text-card-foreground">
          Technical monitoring
        </h2>
        <p className="px-5 py-3 text-xs text-muted-foreground">
          Live graphs from Prometheus. Sign in to Grafana below if prompted.
        </p>
        <iframe
          title="Grafana technical monitoring graphs"
          src={`${grafanaUrl.replace(/\/$/, "")}/d/saiv-technical/saiv-technical?orgId=1&from=now-12h&to=now&refresh=15s&theme=dark&kiosk`}
          className="h-[1050px] w-full border-0 md:h-[850px]"
          loading="lazy"
        />
      </section>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-12">
        <div className="animate-rise rounded-2xl border border-border bg-glass p-5 lg:col-span-12">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="font-display text-sm font-medium text-card-foreground">
              Endpoint metrics
            </p>
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
