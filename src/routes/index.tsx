import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { ArrowLeft, Clock, Globe, Sparkles } from "lucide-react";
import { AppHeader } from "@/components/app-header";
import { getRecentAudits, getStats, type Stats } from "@/services/api";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "تدقيق الامتثال الرقمي — فحص جديد" },
      { name: "description", content: "ابدأ فحصًا جديدًا لموقع حكومي وفق معايير هيئة الحكومة الرقمية." },
      { property: "og:title", content: "تدقيق الامتثال الرقمي — فحص جديد" },
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
        <section className="glass rounded-3xl p-6 shadow-2xl shadow-brand/5 md:p-10">
          <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-brand/15 bg-brand/5 px-3 py-1 text-xs font-medium text-brand">
            <Sparkles className="h-3.5 w-3.5" />
            أداة داخلية · وزارة البيئة والمياه والزراعة
          </div>
          <h1 className="text-3xl font-black tracking-tight text-ink md:text-[42px] md:leading-[1.15]">
            فحص الامتثال الرقمي <span className="text-brand">للمواقع الحكومية</span>
          </h1>
          <p className="mt-3 max-w-2xl text-[15px] leading-relaxed text-muted-foreground">
            أدخل رابط الموقع الحكومي لبدء تدقيقه آليًا وفق المعايير الـ27 المعتمدة من هيئة الحكومة الرقمية (DGA).
          </p>

          <form
            onSubmit={(e) => { e.preventDefault(); submit(url); }}
            className="mt-6 rounded-2xl bg-white p-2 shadow-inner ring-1 ring-hairline"
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
                className="group flex h-12 items-center justify-center gap-2 rounded-xl bg-gradient-to-br from-brand to-brand-deep px-8 font-bold text-brand-foreground shadow-lg shadow-brand/25 transition hover:shadow-xl active:scale-[0.98]"
              >
                ابدأ الفحص الذكي
                <ArrowLeft className="h-4 w-4 transition group-hover:-translate-x-0.5" />
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
                className="ltr rounded-full border border-hairline bg-white/70 px-3 py-1 font-mono text-xs text-ink transition hover:border-brand hover:bg-brand/5 hover:text-brand"
              >
                {s}
              </button>
            ))}
          </div>
        </section>

        {/* Stat strip */}
        <section className="mt-6 grid grid-cols-1 gap-3 md:grid-cols-3">
          <StatCard label="المواقع المفحوصة" value={stats ? String(stats.totalAudits) : "—"} tint="brand" />
          <StatCard label="متوسط وقت التدقيق" value={stats ? formatDuration(stats.avgDurationSec) : "—"} tint="gold" />
          <StatCard label="معدل الامتثال" value={stats && stats.totalAudits > 0 ? `${stats.avgScore}٪` : "—"} tint="brand" />
        </section>

        {/* Recent scans */}
        <section className="mt-10">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="flex items-center gap-2 text-sm font-bold text-ink">
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
                className="group flex items-center justify-between gap-4 rounded-2xl border border-white/60 bg-white/70 p-4 text-right shadow-sm backdrop-blur-md transition hover:border-brand/30 hover:bg-white hover:shadow-md"
              >
                <div className="flex min-w-0 items-center gap-4">
                  <div className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-brand/8 font-mono text-sm font-bold text-brand transition group-hover:bg-brand group-hover:text-brand-foreground">
                    {r.score}
                  </div>
                  <div className="min-w-0">
                    <div className="ltr truncate font-mono text-sm font-semibold text-ink">{r.url}</div>
                    <div className="mt-0.5 text-xs text-muted-foreground">
                      {new Date(r.scannedAt).toLocaleDateString("ar-SA", { year: "numeric", month: "long", day: "numeric" })}
                      {" · "}27 معيار
                    </div>
                  </div>
                </div>
                <ScoreBadge score={r.score} />
              </button>
            ))}
            {recent.length === 0 && (
              <div className="rounded-2xl border border-dashed border-hairline p-8 text-center text-sm text-muted-foreground">
                ما فيه فحوصات سابقة بعد — ابدأ أول فحص من الأعلى.
              </div>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}

function StatCard({ label, value, tint }: { label: string; value: string; tint: "brand" | "gold" }) {
  return (
    <div className="glass-soft flex items-center gap-4 rounded-2xl p-4">
      <div
        className="h-10 w-10 shrink-0 rounded-xl"
        style={{
          background:
            tint === "brand"
              ? "color-mix(in oklab, var(--brand) 15%, white)"
              : "color-mix(in oklab, var(--gold) 25%, white)",
        }}
      />
      <div>
        <div className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">{label}</div>
        <div className="mt-0.5 text-xl font-black text-ink">{value}</div>
      </div>
    </div>
  );
}

function formatDuration(sec: number): string {
  if (sec <= 0) return "—";
  if (sec < 60) return `${sec} ثانية`;
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return s > 0 ? `${m} د ${s} ث` : `${m} دقيقة`;
}

function ScoreBadge({ score }: { score: number }) {
  const color = score >= 85 ? "text-pass border-pass/30 bg-pass/10"
    : score >= 70 ? "text-warn border-warn/30 bg-warn/10"
    : "text-fail border-fail/30 bg-fail/10";
  const label = score >= 85 ? "متوافق كليًا" : score >= 70 ? "يحتاج تحسين" : "غير متوافق";
  return (
    <span className={`shrink-0 rounded-full border px-3 py-1 text-[11px] font-bold ${color}`}>
      {label}
    </span>
  );
}
