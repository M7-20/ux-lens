import { Link } from "@tanstack/react-router";


export function AppHeader() {
  return (
    <header className="border-b border-hairline bg-surface">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4 md:px-6">
        <Link to="/" className="flex items-center gap-3">
          <div className="grid h-9 w-9 place-items-center rounded-md bg-panel text-panel-foreground">
            <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8">
              <circle cx="12" cy="12" r="9" />
              <circle cx="12" cy="12" r="3.5" />
              <path d="M12 3v4M12 17v4M3 12h4M17 12h4M5.6 5.6l2.8 2.8M15.6 15.6l2.8 2.8M18.4 5.6l-2.8 2.8M8.4 15.6l-2.8 2.8" />
            </svg>
          </div>
          <div className="leading-tight">
            <div className="text-sm font-semibold text-ink">UX Lens</div>
            <div className="text-xs text-muted-foreground">وزارة البيئة والمياه والزراعة</div>
          </div>
        </Link>
        <div className="hidden text-xs text-muted-foreground md:block">
          فحص الامتثال لمعايير هيئة الحكومة الرقمية · 27 معيارًا
        </div>
      </div>
    </header>
  );
}
