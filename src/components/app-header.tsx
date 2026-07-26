import { Link } from "@tanstack/react-router";

export function AppLogo({ size = 40 }: { size?: number }) {
  return (
    <div
      className="relative grid place-items-center rounded-2xl bg-gradient-to-br from-brand to-brand-deep shadow-lg shadow-brand/20"
      style={{ width: size, height: size }}
      aria-hidden
    >
      <svg viewBox="0 0 24 24" className="text-white" width={size * 0.62} height={size * 0.62} fill="none" stroke="currentColor">
        {/* dashed outer scan ring */}
        <path
          d="M10 2C6 2 2 6 2 10s4 8 8 8"
          stroke="var(--gold)"
          strokeWidth="1.8"
          strokeDasharray="2 2"
          strokeLinecap="round"
        />
        {/* magnifier body */}
        <circle cx="10" cy="10" r="6.2" strokeWidth="1.6" />
        <circle cx="10" cy="10" r="2.6" strokeWidth="1.4" className="opacity-70" />
        {/* crosshair */}
        <path d="M10 6.5v7M6.5 10h7" strokeWidth="1.2" strokeLinecap="round" className="opacity-70" />
        {/* handle */}
        <path d="M15 15l6 6" strokeWidth="1.9" strokeLinecap="round" />
      </svg>
      <span
        className="absolute -top-1 -left-1 h-3 w-3 rounded-full border-2 border-white bg-gold"
        aria-hidden
      />
    </div>
  );
}

export function AppHeader() {
  return (
    <header className="sticky top-0 z-30 border-b border-white/40 glass">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3 md:px-6 md:py-4">
        <Link to="/" className="flex items-center gap-3">
          <AppLogo size={44} />
          <div className="leading-tight">
            <div className="text-base font-bold tracking-tight text-brand">عدسة تجربة المستخدم</div>
            <div className="text-[11px] font-medium text-muted-foreground">
              نظام تدقيق المعايير الرقمية · وزارة البيئة والمياه والزراعة
            </div>
          </div>
        </Link>
        <div className="hidden items-center gap-2 rounded-full border border-white/60 bg-white/60 px-3 py-1.5 text-[11px] font-medium text-muted-foreground md:flex">
          <span className="h-1.5 w-1.5 rounded-full bg-gold" />
          معايير هيئة الحكومة الرقمية · 27 معيارًا
        </div>
      </div>
    </header>
  );
}
