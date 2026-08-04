import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { ArrowLeft, Clock, Globe } from "lucide-react";
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

const SAMPLES = ["naama.sa"];

function Index() {
  const navigate = useNavigate();
  const [url, setUrl] = useState("");
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

          <form
            onSubmit={(e) => { e.preventDefault(); submit(url); }}
            className="mt-6 rounded-md bg-white p-2 ring-1 ring-hairline"
          >
            <div className="flex flex-col gap-2 md:flex-row md:items-center">
              <div className="flex flex-1 items-center gap-3 px-4 py-2">
                <Globe className="h-5 w-5 shrink-0 text-muted-foreground/70" />
                <input
                  id="url"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="أدخل رابط الموقع الحكومي للفحص..."
                  dir="ltr"
                  className="ltr h-11 w-full bg-transparent font-mono text-[15px] text-ink placeholder:text-right placeholder:font-sans placeholder:text-muted-foreground/70 focus:outline-none"
                  autoFocus
                />
              </div>
              <button
                type="submit"
                className="flex h-12 items-center justify-center gap-2 rounded-md bg-brand px-8 font-semibold text-brand-foreground transition hover:bg-brand-deep active:scale-[0.98]"
              >
                ابدأ الفحص
                <ArrowLeft className="h-4 w-4" />
              </button>
            </div>
          </form>

          <div className="mt-5 flex flex-wrap items-center gap-2">
            <span className="text-xs text-muted-foreground">أمثلة سريعة:</span>
            {SAMPLES.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => { setUrl(`https://${s}`); submit(`https://${s}`); }}
                className="ltr rounded-md border border-hairline bg-white px-3 py-1 font-mono text-xs text-ink transition hover:border-brand hover:text-brand"
              >
                {s}
              </button>
            ))}
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
                className="group flex flex-col gap-3 rounded-md border border-hairline bg-white px-4 py-3 text-right transition hover:border-brand/40"
              >
                {/* الصف الأول: الرابط والتاريخ يمين + الحالة يسار */}
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <div dir="ltr" className="truncate font-mono text-sm font-semibold text-ink">
                      {r.url.replace(/^https?:\/\//, "")}
                    </div>
                    <div className="mt-0.5 text-xs text-muted-foreground/70">
                      <span dir="ltr">{new Date(r.scannedAt).toLocaleDateString("en-GB", { year: "numeric", month: "long", day: "numeric" })}</span>
                    </div>
                  </div>
                  <ScoreBadge score={r.score} />
                </div>

                {/* الصف الثاني: شريطا DGA وGeneral بعرض كامل */}
                <div className="space-y-2">
                  <div className="flex items-center gap-3">
                    <span className="w-16 shrink-0 text-[10px] font-bold uppercase tracking-wide text-muted-foreground">DGA</span>
                    <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-hairline">
                      <div
                        className="h-full rounded-full transition-all"
                        style={{ width: `${r.dgaScore ?? r.score}%`, background: "var(--brand)" }}
                      />
                    </div>
                    <span dir="ltr" className="shrink-0 font-mono text-xs font-bold text-ink">
                      {r.dgaScore ?? r.score}%
                      {r.dgaTotalCount != null && (
                        <span className="font-normal text-muted-foreground"> ({r.dgaPassCount}/{r.dgaTotalCount})</span>
                      )}
                    </span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="w-16 shrink-0 text-[10px] font-bold uppercase tracking-wide text-muted-foreground">General</span>
                    <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-hairline">
                      {r.uxScore != null && (
                        <div
                          className="h-full rounded-full transition-all"
                          style={{ width: `${r.uxScore}%`, background: "var(--brand)" }}
                        />
                      )}
                    </div>
                    <span dir="ltr" className="shrink-0 font-mono text-xs font-bold text-ink">
                      {r.uxScore != null ? `${r.uxScore}%` : "—"}
                      {r.uxTotalCount != null && (
                        <span className="font-normal text-muted-foreground"> ({r.uxPassCount}/{r.uxTotalCount})</span>
                      )}
                    </span>
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
