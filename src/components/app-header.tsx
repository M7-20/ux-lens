import { Link } from "@tanstack/react-router";

export function AppLogo({ size = 40 }: { size?: number }) {
  return <img src="/logo.svg" alt="" width={size} height={size} style={{ width: size, height: size }} aria-hidden />;
}

export function AppHeader() {
  return (
    <header className="sticky top-0 z-30 border-b border-white/40 glass">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3 md:px-6 md:py-4">
        <Link to="/" className="flex items-center gap-3">
          <AppLogo size={44} />
          <div className="leading-tight">
            <div className="text-base font-bold tracking-tight text-[#14573A]">تدقيق الامتثال الرقمي</div>
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
