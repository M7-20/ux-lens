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
        <defs>
          <linearGradient id="gauge-grad" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#166A45" />
            <stop offset="16.67%" stopColor="#1B8354" />
            <stop offset="33.33%" stopColor="#25935F" />
            <stop offset="50%" stopColor="#54C08A" />
            <stop offset="66.67%" stopColor="#88D8AD" />
            <stop offset="83.33%" stopColor="#B8EACB" />
            <stop offset="100%" stopColor="#DFF6E7" />
          </linearGradient>
        </defs>
        <circle cx={size / 2} cy={size / 2} r={r} stroke="var(--hairline)" strokeWidth={stroke} fill="none" />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          stroke="url(#gauge-grad)"
          strokeWidth={stroke}
          fill="none"
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={offset}
          className="transition-[stroke-dashoffset] duration-1000 ease-out"
        />
      </svg>
      <div className="absolute inset-0 grid place-items-center text-center">
        <div>
          <div className="font-sans text-5xl font-black tabular-nums text-brand">
            {clamped}<span className="text-2xl text-brand/60">%</span>
          </div>
          <div className="mt-1 text-[10px] font-bold uppercase tracking-[0.2em] text-muted-foreground">
            درجة {grade}
          </div>
        </div>
      </div>
    </div>
  );
}
