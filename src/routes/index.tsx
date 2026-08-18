import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { ArrowLeft, Clock, Home, ListChecks, Mail } from "lucide-react";
import { AppHeader } from "@/components/app-header";
import { getRecentAudits, getStats, type Stats } from "@/services/api";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "UX LENS — فحص جديد" },
      { name: "description", content: "ابدأ فحصًا جديدًا لموقع حكومي وفق معايير هيئة الحكومة الرقمية." },
      { property: "og:title", content: "UX LENS — فحص جديد" },
      { property: "og:description", content: "أداة داخلية لفحص التزام المواقع الحكومية بمعايير DGA." },
    ],
  }),
  component: Index,
});

function Index() {
  const navigate = useNavigate();
  const [recent, setRecent] = useState<Awaited<ReturnType<typeof getRecentAudits>>>([]);
  const [stats, setStats] = useState<Stats | null>(null);

  useEffect(() => {
    getRecentAudits().then(setRecent);
    getStats().then(setStats);
  }, []);

  const submit = (raw: string) => {
    const v = raw.trim();
    if (!v) return;
    const full = /^https?:\/\//.test(v) ? v : `https://${v}`;
    navigate({ to: "/scanning", search: { url: full } });
  };

  return (
    <div className="min-h-screen">
      <AppHeader />
      <main className="mx-auto max-w-5xl px-4 py-10 md:px-6 md:py-16">
        {/* Hero panel */}
        <section className="glass rounded-lg p-6 md:p-10">
          <h1 className="text-3xl font-semibold tracking-tight text-ink md:text-[42px] md:leading-[1.15]">
            افحص التزام موقعك <span className="text-brand">بمعايير الحكومة الرقمية</span>
          </h1>
          <p className="mt-3 max-w-2xl text-[15px] leading-relaxed text-muted-foreground">
            تدقيق آلي شامل وفق معايير هيئة الحكومة الرقمية (DGA) ومعايير تجربة المستخدم (UX).
          </p>

          <div className="mt-6 flex flex-col gap-3 sm:flex-row">
            <button
              type="button"
              onClick={() => submit("https://naama.sa/")}
              className="flex h-14 flex-1 items-center justify-center gap-2 rounded-md bg-brand px-8 text-base font-semibold text-brand-foreground transition hover:bg-brand-deep active:scale-[0.98]"
            >
              <Home className="h-5 w-5" />
              فحص الصفحة الرئيسية
              <ArrowLeft className="h-4 w-4" />
            </button>
            <button
              type="button"
              onClick={() => submit("https://naama.sa/pages/contactus")}
              className="flex h-14 flex-1 items-center justify-center gap-2 rounded-md bg-brand px-8 text-base font-semibold text-brand-foreground transition hover:bg-brand-deep active:scale-[0.98]"
            >
              <Mail className="h-5 w-5" />
              فحص صفحة الاتصال
              <ArrowLeft className="h-4 w-4" />
            </button>
          </div>
        </section>

        {/* Stat strip */}
        <section className="mt-6 grid grid-cols-1 gap-3 md:grid-cols-3">
          <StatCard label="المواقع المفحوصة" value={stats ? String(stats.totalAudits) : "—"} />
          <StatCard label="متوسط وقت التدقيق" value={stats ? formatDuration(stats.avgDurationSec) : "—"} />
          <StatCard label="معدل الامتثال" value={stats && stats.totalAudits > 0 ? `${stats.avgScore}٪` : "—"} />
        </section>

        {/* Recent scans */}
        <section className="mt-10">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="flex items-center gap-2 text-sm font-semibold text-ink">
              <Clock className="h-4 w-4 text-brand" />
              الفحوصات السابقة
            </h2>
            <span className="text-xs text-muted-foreground">{recent.length} عملية</span>
          </div>
          <div className="grid gap-3">
            {recent.map((r) => (
              <button
                key={r.url + r.scannedAt}
                onClick={() => submit(r.url)}
                className="group flex items-center justify-between gap-4 rounded-md border border-hairline bg-surface px-4 py-3 text-right transition hover:border-brand/40"
              >
                {/* العمود الثالث (يمين): الرابط + التاريخ + الحالة */}
                <div className="min-w-0">
                  <div dir="ltr" className="truncate font-mono text-sm font-semibold text-ink">
                    {r.url.replace(/^https?:\/\//, "")}
                  </div>
                  <div className="mt-0.5 text-xs text-muted-foreground">
                    <span dir="ltr">{new Date(r.scannedAt).toLocaleDateString("en-GB", { year: "numeric", month: "long", day: "numeric" })}</span>
                  </div>
                  <div className="mt-1.5">
                    <ScoreBadge score={r.score} />
                  </div>
                </div>

                {/* العمود الثاني (وسط): معلومة المعايير */}
                <div className="flex shrink-0 flex-col items-center gap-1.5 border-r border-hairline pr-4">
                  <div className="flex items-center gap-1 text-sm font-bold text-brand">
                    <ListChecks className="h-4 w-4" />
                    54 <span className="font-normal text-muted-foreground">Rules</span>
                  </div>
                  <div className="flex gap-1.5">
                    <div className="w-14 rounded-md border border-brand/20 bg-brand/5 py-1 text-center">
                      <div className="font-mono text-xs font-bold text-brand">27</div>
                      <div className="text-[9px] font-bold uppercase text-muted-foreground">General</div>
                    </div>
                    <div className="w-14 rounded-md border border-brand/20 bg-brand/5 py-1 text-center">
                      <div className="font-mono text-xs font-bold text-brand">27</div>
                      <div className="text-[9px] font-bold uppercase text-muted-foreground">DGA</div>
                    </div>
                  </div>
                </div>

                {/* العمود الأول (يسار): شريطا التقدم */}
                <div className="w-36 shrink-0 space-y-2">
                  <div>
                    <div className="flex items-center justify-between text-[10px] font-bold text-muted-foreground">
                      <span className="uppercase tracking-wide">General</span>
                      <span dir="ltr" className="font-mono tabular-nums text-ink">{r.uxScore != null ? `${r.uxScore}%` : "—"}</span>
                    </div>
                    <div className="mt-0.5 flex items-center gap-2">
                      <div className="h-1 flex-1 overflow-hidden rounded-full bg-hairline">
                        {r.uxScore != null && (
                          <div className="h-full rounded-full transition-all" style={{ width: `${r.uxScore}%`, background: "var(--brand)" }} />
                        )}
                      </div>
                      {r.uxTotalCount != null && (
                        <span dir="ltr" className="shrink-0 font-mono text-[10px] tabular-nums text-muted-foreground">
                          {r.uxPassCount}/{r.uxTotalCount}
                        </span>
                      )}
                    </div>
                  </div>
                  <div>
                    <div className="flex items-center justify-between text-[10px] font-bold text-muted-foreground">
                      <span className="uppercase tracking-wide">DGA</span>
                      <span dir="ltr" className="font-mono tabular-nums text-ink">{r.dgaScore ?? r.score}%</span>
                    </div>
                    <div className="mt-0.5 flex items-center gap-2">
                      <div className="h-1 flex-1 overflow-hidden rounded-full bg-hairline">
                        <div className="h-full rounded-full transition-all" style={{ width: `${r.dgaScore ?? r.score}%`, background: "var(--brand)" }} />
                      </div>
                      {r.dgaTotalCount != null && (
                        <span dir="ltr" className="shrink-0 font-mono text-[10px] tabular-nums text-muted-foreground">
                          {r.dgaPassCount}/{r.dgaTotalCount}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              </button>
            ))}
            {recent.length === 0 && (
              <div className="rounded-md border border-dashed border-hairline p-8 text-center text-sm text-muted-foreground">
                ما فيه فحوصات سابقة بعد — ابدأ أول فحص من الأعلى.
              </div>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="glass-soft rounded-md p-4">
      <div className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">{label}</div>
      <div className="mt-1 text-xl font-semibold text-ink">{value}</div>
    </div>
  );
}

function formatDuration(sec: number): string {
  if (sec <= 0) return "—";
  if (sec < 60) return `${sec}s`;
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return s > 0 ? `${m}m ${s}s` : `${m}m`;
}

function ScoreBadge({ score }: { score: number }) {
  const color = score >= 85 ? "text-pass border-pass/30 bg-pass/10"
    : score >= 70 ? "text-warn border-warn/30 bg-warn/10"
    : "text-fail border-fail/30 bg-fail/10";
  const label = score >= 85 ? "متوافق كليًا" : score >= 70 ? "يحتاج تحسين" : "غير متوافق";
  return (
    <span className={`inline-flex shrink-0 items-center gap-1.5 rounded-md border px-2.5 py-1 text-[10px] font-bold ${color}`}>
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {label}
    </span>
  );
}
