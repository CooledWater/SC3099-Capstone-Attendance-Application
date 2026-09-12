export function CheckInTrend({
  data,
  approved,
  flagged,
}: {
  data: [string, number][];
  approved: number;
  flagged: number;
}) {
  const max = Math.max(1, ...data.map(([, v]) => v));
  const total = Math.max(1, approved + flagged);

  return (
    <div className="animate-rise rounded-2xl border border-border bg-glass p-5 lg:col-span-8">
      <div className="mb-4 flex items-center justify-between">
        <p className="font-display text-sm font-medium text-card-foreground">Check-ins over time</p>
        <div className="flex gap-3 text-[11px] text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <span className="size-2 rounded-full bg-primary" />
            Check-ins
          </span>
          <span className="flex items-center gap-1.5">
            <span className="size-2 rounded-full bg-warning" />
            Flagged
          </span>
        </div>
      </div>

      {data.length === 0 ? (
        <div className="grid h-44 place-items-center text-sm text-muted-foreground">
          No check-ins recorded yet.
        </div>
      ) : (
        <div className="flex h-44 items-end gap-2">
          {data.map(([hour, count]) => (
            <div key={hour} className="flex h-full flex-1 flex-col justify-end items-center gap-2">
              <span className="text-[10px] text-muted-foreground">{count}</span>
              <div
                className="w-full max-w-14 rounded-md bg-gradient-to-t from-primary/30 to-primary transition-[height] duration-700"
                style={{ height: `${Math.max(6, (count / max) * 92)}%` }}
              />
            </div>
          ))}
        </div>
      )}

      <div className="mt-3 flex justify-between text-[10px] uppercase tracking-wider text-muted-foreground">
        {data.map(([hour]) => (
          <span key={hour}>{hour}</span>
        ))}
      </div>

      <div className="mt-5 space-y-3 border-t border-border pt-4">
        <div>
          <div className="flex items-center justify-between text-xs">
            <span className="text-muted-foreground">Approved</span>
            <span className="text-accent">{approved}</span>
          </div>
          <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-secondary">
            <div
              className="h-full rounded-full bg-accent"
              style={{ width: `${(approved / total) * 100}%` }}
            />
          </div>
        </div>
        <div>
          <div className="flex items-center justify-between text-xs">
            <span className="text-muted-foreground">Flagged</span>
            <span className="text-warning">{flagged}</span>
          </div>
          <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-secondary">
            <div
              className="h-full rounded-full bg-warning"
              style={{ width: `${(flagged / total) * 100}%` }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
