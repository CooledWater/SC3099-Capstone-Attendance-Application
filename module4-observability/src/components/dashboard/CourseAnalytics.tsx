export type CourseStat = {
  id: string;
  code: string;
  name: string;
  sessions: number;
  checkIns: number;
  expected: number | null;
  flagged: number;
  avgRisk: number;
};

export function CourseAnalytics({ stats, title }: { stats: CourseStat[]; title: string }) {
  return (
    <div className="mt-4 min-w-0 animate-rise overflow-hidden rounded-2xl border border-border bg-glass">
      <div className="border-b border-border px-5 py-4">
        <p className="font-display text-sm font-medium text-card-foreground">{title}</p>
      </div>
      <div
        className="max-h-[32rem] overflow-auto overscroll-contain focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary"
        role="region"
        aria-label={`${title} scroll area`}
        tabIndex={0}
      >
        <div className="w-max min-w-full divide-y divide-border">
          {stats.length === 0 && (
            <p className="px-5 py-6 text-sm text-muted-foreground">No courses to show yet.</p>
          )}
          {stats.map((c) => {
            const rate = c.expected != null && c.expected > 0 && c.sessions > 0
              ? Math.round((c.checkIns / c.expected) * 100) : null;
            return (
              <div key={c.id} className="min-w-[720px] px-5 py-4">
                <div className="flex items-baseline justify-between gap-6">
                  <div>
                    <p className="whitespace-nowrap text-sm font-medium text-foreground">
                      {c.code} · {c.name}
                    </p>
                    <p className="mt-0.5 whitespace-nowrap text-xs text-muted-foreground">
                      {c.sessions} sessions · {c.checkIns} check-ins · {c.flagged} flagged · avg
                      risk {c.checkIns > 0 ? c.avgRisk.toFixed(2) : "No data"}
                    </p>
                  </div>
                  <span className="shrink-0 font-display text-lg text-card-foreground tabular-nums">
                    {rate == null ? "No data" : `${rate}%`}
                  </span>
                </div>
                <div className="mt-3 h-2 overflow-hidden rounded-full bg-secondary">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-primary to-accent transition-[width] duration-700"
                    style={{ width: `${Math.min(100, rate ?? 0)}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
