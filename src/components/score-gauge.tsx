import { cn } from "@/lib/utils";

interface GaugeProps {
  value: number; // 0-100
  grade: string;
  size?: number;
  className?: string;
}

export function ScoreGauge({ value, grade, size = 220, className }: GaugeProps) {
  const stroke = 14;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const clamped = Math.max(0, Math.min(100, value));
  const offset = c - (clamped / 100) * c;

  return (
    <div className={cn("relative grid place-items-center", className)} style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90" aria-hidden>
        <circle cx={size / 2} cy={size / 2} r={r} stroke="oklch(1 0 0 / 0.12)" strokeWidth={stroke} fill="none" />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          stroke="currentColor"
          strokeWidth={stroke}
          fill="none"
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={offset}
          className="text-[color:var(--pass)] transition-[stroke-dashoffset] duration-1000 ease-out"
        />
        {/* aperture blades — 6 short arcs */}
        {Array.from({ length: 6 }).map((_, i) => {
          const angle = (i * 60 * Math.PI) / 180;
          const x1 = size / 2 + Math.cos(angle) * (r - 24);
          const y1 = size / 2 + Math.sin(angle) * (r - 24);
          const x2 = size / 2 + Math.cos(angle) * (r - 36);
          const y2 = size / 2 + Math.sin(angle) * (r - 36);
          return <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke="oklch(1 0 0 / 0.15)" strokeWidth="1.5" />;
        })}
      </svg>
      <div className="absolute inset-0 grid place-items-center text-center">
        <div>
          <div className="font-mono text-5xl font-semibold tabular-nums text-panel-foreground">
            {clamped}<span className="text-2xl text-panel-foreground/60">%</span>
          </div>
          <div className="mt-1 text-xs uppercase tracking-widest text-panel-foreground/60">التقييم</div>
          <div className="mt-1 font-mono text-2xl font-semibold text-panel-foreground">{grade}</div>
        </div>
      </div>
    </div>
  );
}
