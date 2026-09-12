type Tone = "brand" | "accent" | "warning" | "danger";

const toneText: Record<Tone, string> = {
  brand: "text-primary",
  accent: "text-accent",
  warning: "text-warning",
  danger: "text-destructive",
};

const toneBar: Record<Tone, string> = {
  brand: "bg-primary",
  accent: "bg-accent",
  warning: "bg-warning",
  danger: "bg-destructive",
};

const toneGlow: Record<Tone, string> = {
  brand: "bg-primary/20",
  accent: "bg-accent/15",
  warning: "bg-warning/20",
  danger: "bg-destructive/20",
};

export function KpiCard({
  label,
  value,
  note,
  tone,
  bars,
  progress,
}: {
  label: string;
  value: string;
  note: string;
  tone: Tone;
  bars?: number[];
  progress?: number;
}) {
  return (
    <div className="relative animate-rise overflow-hidden rounded-2xl border border-border bg-glass p-5 lg:col-span-3">
      <div
        className={`absolute right-3 top-3 size-16 -translate-y-6 animate-floaty rounded-full blur-2xl ${toneGlow[tone]}`}
      />
      <p className="text-xs uppercase tracking-wider text-muted-foreground">{label}</p>
      <p className="mt-2 font-display text-3xl font-semibold text-card-foreground">{value}</p>
      <p className={`mt-2 text-xs ${toneText[tone]}`}>{note}</p>

      {bars && (
        <div className="mt-4 flex h-10 items-end gap-1">
          {bars.map((h, i) => (
            <span
              key={i}
              className={`w-2 rounded-sm ${toneBar[tone]}`}
              style={{ height: `${h}%`, opacity: 0.35 + (i / bars.length) * 0.65 }}
            />
          ))}
        </div>
      )}

      {progress !== undefined && (
        <div className="mt-4 h-2 w-full overflow-hidden rounded-full bg-secondary">
          <div
            className={`h-full rounded-full ${toneBar[tone]} transition-[width] duration-700`}
            style={{ width: `${Math.max(0, Math.min(100, progress))}%` }}
          />
        </div>
      )}
    </div>
  );
}
