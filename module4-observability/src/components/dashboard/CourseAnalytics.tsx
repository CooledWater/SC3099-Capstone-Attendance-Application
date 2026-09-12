export type CourseStat = {
  id: string;
  code: string;
  name: string;
  sessions: number;
  checkIns: number;
  expected: number;
  flagged: number;
  avgRisk: number;
};

export function CourseAnalytics({ stats, title }: { stats: CourseStat[]; title: string }) {
  return (
    <div className="mt-4 animate-rise rounded-2xl border border-border bg-glass">
      <div className="border-b border-border px-5 py-4">
        <p className="font-display text-sm font-medium text-card-foreground">{title}</p>
        <p className="mt-0.5 text-xs text-muted-foreground">
          Attendance performance per course · {stats.length} courses
        </p>
      </div>
      <div className="divide-y divide-border">
        {stats.length === 0 && (
          <p className="px-5 py-6 text-sm text-muted-foreground">No courses to show yet.</p>
        )}
        {stats.map((c) => {
          const rate = c.expected > 0 ? Math.round((c.checkIns / c.expected) * 100) : 0;
          return (
            <div key={c.id} className="px-5 py-4">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <div>
                  <p className="text-sm font-medium text-foreground">
                    {c.code} · {c.name}
                  </p>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {c.sessions} sessions · {c.checkIns} check-ins · {c.flagged} flagged · avg risk{" "}
                    {c.avgRisk}
                  </p>
                </div>
                <span className="font-display text-lg text-card-foreground tabular-nums">
                  {rate}%
                </span>
              </div>
              <div className="mt-3 h-2 overflow-hidden rounded-full bg-secondary">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-primary to-accent transition-[width] duration-700"
                  style={{ width: `${Math.min(100, rate)}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
