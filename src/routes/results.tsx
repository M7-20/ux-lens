import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { z } from "zod";
import { ArrowRight, ChevronDown, Check, AlertTriangle, X, Download, RefreshCw, Monitor, Tablet, Smartphone, ImageIcon, MapPin, Loader2 } from "lucide-react";
import { AppHeader } from "@/components/app-header";
import { ScoreGauge } from "@/components/score-gauge";
import { Button } from "@/components/ui/button";
import { getAudit, CATEGORY_LABELS, type Audit, type Rule, type Status, type Category, type Screenshot } from "@/services/api";
import { cn } from "@/lib/utils";

const searchSchema = z.object({ url: z.string() });

export const Route = createFileRoute("/results")({
  validateSearch: searchSchema,
  head: () => ({
    meta: [
      { title: "تدقيق الامتثال الرقمي — نتائج الفحص" },
      { name: "description", content: "تقرير امتثال الموقع الحكومي لمعايير هيئة الحكومة الرقمية." },
      { property: "og:title", content: "تدقيق الامتثال الرقمي — نتائج الفحص" },
      { property: "og:description", content: "تقرير مفصّل يعرض 27 معيارًا مع التوصيات." },
      { name: "robots", content: "noindex" },
    ],
  }),
  component: Results,
});

const SEVERITY: Record<Status, number> = { fail: 0, warn: 1, pass: 2 };

function Results() {
  const { url } = Route.useSearch();
  const [audit, setAudit] = useState<Audit | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | Status>("all");
  const [activeShot, setActiveShot] = useState(0);
  const [selectedRuleId, setSelectedRuleId] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setAudit(null);
    setError(null);
    getAudit(url)
      .then((a) => { if (active) setAudit(a); })
      .catch((e) => { if (active) setError(e instanceof Error ? e.message : "تعذّر تحميل نتائج الفحص."); });
    return () => { active = false; };
  }, [url]);

  const rules = useMemo(() => {
    if (!audit) return [];
    const sorted = [...audit.rules].sort((a, b) => SEVERITY[a.status] - SEVERITY[b.status] || a.id.localeCompare(b.id));
    return filter === "all" ? sorted : sorted.filter((r) => r.status === filter);
  }, [audit, filter]);

  const selectedRule = useMemo(
    () => audit?.rules.find((r) => r.id === selectedRuleId) ?? null,
    [audit, selectedRuleId]
  );

  const tally = useMemo(() => {
    if (!audit) return { pass: 0, warn: 0, fail: 0 };
    return audit.rules.reduce(
      (acc, r) => ({ ...acc, [r.status]: acc[r.status] + 1 }),
      { pass: 0, warn: 0, fail: 0 }
    );
  }, [audit]);

  const categoryStats = useMemo(() => {
    if (!audit) return [];
    const map = new Map<Category, { total: number; passWeight: number }>();
    for (const r of audit.rules) {
      const cur = map.get(r.category) ?? { total: 0, passWeight: 0 };
      cur.total += 1;
      cur.passWeight += r.status === "pass" ? 1 : r.status === "warn" ? 0.5 : 0;
      map.set(r.category, cur);
    }
    return (Object.keys(CATEGORY_LABELS) as Category[]).map((c) => {
      const v = map.get(c) ?? { total: 0, passWeight: 0 };
      return { category: c, pct: v.total ? Math.round((v.passWeight / v.total) * 100) : 0, total: v.total };
    });
  }, [audit]);

  function handleActivateRule(rule: Rule) {
    setSelectedRuleId((id) => (id === rule.id ? null : rule.id));
    if (rule.region && audit) {
      const desktopIndex = audit.screenshots.findIndex((s) => s.viewport === "desktop");
      if (desktopIndex >= 0) setActiveShot(desktopIndex);
    }
  }

  if (error) {
    return (
      <div className="min-h-screen">
        <AppHeader />
        <div className="mx-auto flex max-w-md flex-col items-center gap-4 px-4 py-24 text-center">
          <div className="grid h-12 w-12 place-items-center rounded-full bg-fail/10 text-fail">
            <AlertTriangle className="h-6 w-6" />
          </div>
          <p className="text-sm text-ink/80">{error}</p>
          <Button asChild className="rounded-xl bg-gradient-to-br from-brand to-brand-deep text-brand-foreground shadow-lg shadow-brand/20 hover:opacity-95">
            <Link to="/">فحص جديد</Link>
          </Button>
        </div>
      </div>
    );
  }

  if (!audit) {
    return (
      <div className="min-h-screen">
        <AppHeader />
        <div className="mx-auto flex max-w-4xl items-center justify-center gap-2 px-4 py-24 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          جارٍ التحميل…
        </div>
      </div>
    );
  }

  const gradeLabel =
    audit.grade === "A" ? "امتثال ممتاز"
    : audit.grade === "B" ? "امتثال جيد"
    : audit.grade === "C" ? "يحتاج تحسينات"
    : "امتثال ضعيف";

  return (
    <div className="min-h-screen">
      <AppHeader />
      <main className="mx-auto max-w-6xl px-4 py-8 md:px-6">
        {/* Header */}
        <div className="mb-6 flex flex-col justify-between gap-4 md:flex-row md:items-end">
          <div className="min-w-0">
            <div className="inline-flex items-center gap-2 rounded-full border border-brand/15 bg-brand/5 px-3 py-1 text-[11px] font-bold text-brand">
              تقرير التدقيق الرقمي
            </div>
            <div className="ltr mt-2 truncate font-mono text-lg font-semibold text-ink">{audit.url}</div>
            <div className="mt-1 text-xs text-muted-foreground">
              {new Date(audit.scannedAt).toLocaleString("ar-SA", { dateStyle: "long", timeStyle: "short" })}
              {" · "}المدة: <span className="font-mono">{audit.durationSec}s</span>
            </div>
          </div>
          <div className="flex gap-2">
            <Button asChild variant="outline" className="rounded-xl border-hairline bg-white/70 backdrop-blur">
              <Link to="/"><RefreshCw className="ml-1 h-4 w-4" />فحص جديد</Link>
            </Button>
            <Button
              className="rounded-xl bg-gradient-to-br from-brand to-brand-deep text-brand-foreground shadow-lg shadow-brand/20 hover:opacity-95"
              onClick={() => window.print()}
            >
              <Download className="ml-1 h-4 w-4" />تصدير PDF
            </Button>
          </div>
        </div>

        {/* Score + summary panel */}
        <section className="grid gap-6 md:grid-cols-12">
          <div className="glass relative overflow-hidden rounded-3xl p-8 shadow-xl shadow-brand/5 md:col-span-5">
            <div className="absolute -top-16 -left-16 h-40 w-40 rounded-full bg-brand/10 blur-2xl" />
            <div className="relative flex flex-col items-center text-center">
              <div className="text-xs font-bold uppercase tracking-widest text-muted-foreground">
                مؤشر الالتزام الكلي
              </div>
              <div className="mt-5">
                <ScoreGauge value={audit.score} grade={audit.grade} />
              </div>
              <h2 className="mt-4 text-lg font-black text-ink">{gradeLabel}</h2>
              <div className="mt-6 grid w-full grid-cols-3 gap-2">
                <Tally label="مطابق" count={tally.pass} tint="var(--pass)" />
                <Tally label="تحسين" count={tally.warn} tint="var(--warn)" />
                <Tally label="مخالف" count={tally.fail} tint="var(--fail)" />
              </div>
            </div>
          </div>

          <div className="glass-soft rounded-3xl p-6 shadow-xl shadow-brand/5 md:col-span-7">
            <h3 className="mb-4 flex items-center gap-2 text-sm font-bold text-ink">
              <span className="h-5 w-1 rounded-full bg-gold" />
              التقييم حسب الفئة
            </h3>
            <div className="grid gap-3 sm:grid-cols-2">
              {categoryStats.map((c) => (
                <div key={c.category} className="rounded-2xl border border-white/60 bg-white/70 p-4">
                  <div className="flex items-baseline justify-between">
                    <div className="text-sm font-bold text-ink">{CATEGORY_LABELS[c.category]}</div>
                    <div className="font-mono text-sm font-bold tabular-nums text-brand">{c.pct}%</div>
                  </div>
                  <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-background">
                    <div
                      className="h-full rounded-full transition-all duration-700"
                      style={{
                        width: `${c.pct}%`,
                        background: c.pct >= 85 ? "var(--pass)" : c.pct >= 60 ? "var(--warn)" : "var(--fail)",
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Results (right) + screenshots (left) */}
        <section className="mt-10 grid items-start gap-6 md:grid-cols-12">
          <div className="md:col-span-7">
            <div className="glass rounded-3xl p-6 shadow-xl shadow-brand/5">
              <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
                <h3 className="flex items-center gap-2 text-base font-bold text-ink">
                  <span className="h-6 w-1.5 rounded-full bg-gold" />
                  تفاصيل التدقيق حسب معايير (DGA) — {audit.rules.length} معيار
                </h3>
                <div className="flex flex-wrap gap-2">
                  {([
                    { k: "all", label: "الكل", n: audit.rules.length },
                    { k: "fail", label: "مخالف", n: tally.fail },
                    { k: "warn", label: "تحسين", n: tally.warn },
                    { k: "pass", label: "مطابق", n: tally.pass },
                  ] as const).map((c) => (
                    <button
                      key={c.k}
                      onClick={() => setFilter(c.k as any)}
                      className={cn(
                        "rounded-full border px-3 py-1 text-xs font-medium transition",
                        filter === c.k
                          ? "border-brand bg-brand text-brand-foreground shadow-md shadow-brand/20"
                          : "border-hairline bg-white/70 text-muted-foreground hover:border-brand/40 hover:text-brand"
                      )}
                    >
                      {c.label} <span className="font-mono tabular-nums">({c.n})</span>
                    </button>
                  ))}
                </div>
              </div>

              <div className="space-y-2">
                {rules.map((r) => (
                  <RuleRow key={r.id} rule={r} active={selectedRuleId === r.id} onActivate={handleActivateRule} />
                ))}
                {rules.length === 0 && (
                  <div className="p-10 text-center text-sm text-muted-foreground">لا توجد معايير مطابقة للفلتر.</div>
                )}
              </div>
            </div>
          </div>

          <div className="md:sticky md:top-24 md:col-span-5">
            <ScreenshotPanel
              shots={audit.screenshots}
              url={audit.url}
              active={activeShot}
              onActiveChange={setActiveShot}
              activeRule={selectedRule}
            />
          </div>
        </section>

        <footer className="mt-16 border-t border-white/60 pt-6 text-center text-xs text-muted-foreground">
          تدقيق الامتثال الرقمي · وزارة البيئة والمياه والزراعة · معايير هيئة الحكومة الرقمية
        </footer>
      </main>
    </div>
  );
}

function Tally({ label, count, tint }: { label: string; count: number; tint: string }) {
  return (
    <div className="rounded-2xl border border-white/60 bg-white/70 p-3">
      <div className="flex items-center justify-center gap-1.5">
        <span className="h-2 w-2 rounded-full" style={{ background: tint }} />
        <span className="text-[11px] font-medium text-muted-foreground">{label}</span>
      </div>
      <div className="mt-1 text-center font-mono text-2xl font-black tabular-nums text-ink">{count}</div>
    </div>
  );
}

function StatusIcon({ status }: { status: Status }) {
  const base = "grid h-10 w-10 shrink-0 place-items-center rounded-xl";
  if (status === "pass") return <div className={cn(base, "bg-pass/10 text-pass")}><Check className="h-5 w-5" /></div>;
  if (status === "warn") return <div className={cn(base, "bg-warn/10 text-warn")}><AlertTriangle className="h-5 w-5" /></div>;
  return <div className={cn(base, "bg-fail/10 text-fail")}><X className="h-5 w-5" /></div>;
}

function RuleRow({
  rule,
  active,
  onActivate,
}: {
  rule: Rule;
  active: boolean;
  onActivate: (rule: Rule) => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div
      className={cn(
        "overflow-hidden rounded-2xl border bg-white/70 shadow-sm transition",
        active ? "border-brand ring-2 ring-brand/30" : "border-white/60"
      )}
    >
      <button
        onClick={() => { setOpen((o) => !o); onActivate(rule); }}
        className="flex w-full items-center gap-4 px-4 py-3 text-right transition hover:bg-white md:px-5"
        aria-expanded={open}
      >
        <StatusIcon status={rule.status} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5 text-sm font-bold text-ink">
            <span className="truncate">{rule.title}</span>
            {rule.region && <MapPin className="h-3.5 w-3.5 shrink-0 text-brand" aria-label="محدد على الصورة" />}
          </div>
          <div className="mt-0.5 text-xs text-muted-foreground">
            {CATEGORY_LABELS[rule.category]}
          </div>
        </div>
        <span className="hidden shrink-0 rounded-lg bg-brand/8 px-2.5 py-1 font-mono text-[10px] font-bold text-brand md:inline">
          {rule.id}
        </span>
        <ChevronDown className={cn("h-4 w-4 shrink-0 text-muted-foreground transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <div className="border-t border-hairline bg-white/60 px-4 py-4 md:px-5">
          <p className="text-sm leading-relaxed text-ink/80">{rule.description}</p>
          {rule.recommendation && (
            <div className="mt-3 rounded-xl border-r-2 border-gold bg-gold/5 p-3">
              <div className="mb-1 flex items-center gap-1.5 text-xs font-bold text-gold">
                <ArrowRight className="h-3.5 w-3.5" /> التوصية
              </div>
              <div className="text-sm text-ink/90">{rule.recommendation}</div>
            </div>
          )}
          {rule.evidence && (
            <div className="mt-3">
              <div className="mb-1 text-xs text-muted-foreground">دليل تقني</div>
              <div className="ltr overflow-x-auto rounded-lg bg-panel px-3 py-2 font-mono text-xs text-panel-foreground/90">
                {rule.evidence}
              </div>
            </div>
          )}
          {rule.region && (
            <div className="mt-3 flex items-center gap-1.5 text-xs font-medium text-brand">
              <MapPin className="h-3.5 w-3.5" />
              مكان المخالفة مؤشَّر على لقطة سطح المكتب في اللوحة المقابلة
            </div>
          )}
        </div>
      )}
    </div>
  );
}

const VIEWPORT_ICON = {
  desktop: Monitor,
  tablet: Tablet,
  mobile: Smartphone,
} as const;

function ScreenshotPanel({
  shots,
  url,
  active,
  onActiveChange,
  activeRule,
}: {
  shots: Screenshot[];
  url: string;
  active: number;
  onActiveChange: (i: number) => void;
  activeRule: Rule | null;
}) {
  const [preview, setPreview] = useState<Screenshot | null>(null);
  const current = shots[active];

  if (!shots.length) return null;

  const highlight = activeRule?.region && current.viewport === "desktop" ? activeRule.region : null;

  return (
    <div className="glass rounded-3xl p-6 shadow-xl shadow-brand/5">
      <h3 className="mb-4 flex items-center gap-2 text-base font-bold text-ink">
        <span className="h-6 w-1.5 rounded-full bg-gold" />
        <ImageIcon className="h-4 w-4 text-brand" />
        لقطات الصفحة الملتقطة
      </h3>

      <div className="mb-4 flex flex-wrap gap-2">
        {shots.map((s, i) => {
          const Icon = VIEWPORT_ICON[s.viewport];
          return (
            <button
              key={s.viewport}
              onClick={() => onActiveChange(i)}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition",
                active === i
                  ? "border-brand bg-brand text-brand-foreground shadow-md shadow-brand/20"
                  : "border-hairline bg-white/70 text-muted-foreground hover:border-brand/40 hover:text-brand"
              )}
            >
              <Icon className="h-3.5 w-3.5" />
              {s.label}
              <span className="font-mono tabular-nums text-[10px] opacity-70">
                {s.width}×{s.height}
              </span>
            </button>
          );
        })}
      </div>

      {activeRule && (
        <div
          className={cn(
            "mb-3 flex items-center gap-2 rounded-xl border px-3 py-2 text-xs font-medium transition",
            highlight
              ? "border-gold/30 bg-gold/5 text-ink"
              : "border-hairline bg-white/60 text-muted-foreground"
          )}
        >
          <MapPin className="h-3.5 w-3.5 shrink-0 text-gold" />
          {highlight
            ? <span>موقع المخالفة: {activeRule.title}</span>
            : <span>حدد لقطة سطح المكتب لعرض موقع «{activeRule.title}»</span>}
        </div>
      )}

      <button
        onClick={() => setPreview(current)}
        className="group relative block w-full overflow-hidden rounded-2xl border border-white/60 bg-white/70 shadow-sm"
      >
        <div
          className="relative w-full bg-panel/5"
          style={{ aspectRatio: `${current.width} / ${current.height}` }}
        >
          <img
            src={current.url}
            alt={`لقطة ${current.label} للموقع ${url}`}
            loading="lazy"
            className="absolute inset-0 h-full w-full object-cover object-top transition-transform duration-500 group-hover:scale-[1.02]"
            onError={(e) => {
              (e.currentTarget as HTMLImageElement).style.display = "none";
            }}
          />

          {highlight && (
            <div
              className="pointer-events-none absolute rounded-lg border-2 border-gold shadow-[0_0_0_9999px_rgba(15,23,42,0.35)] transition-all duration-300"
              style={{
                left: `${highlight.x}%`,
                top: `${highlight.y}%`,
                width: `${highlight.width}%`,
                height: `${highlight.height}%`,
              }}
            >
              <span className="absolute -top-2.5 -right-2.5 grid h-5 w-5 place-items-center rounded-full bg-gold text-[10px] font-black text-ink shadow">!</span>
            </div>
          )}

          <div className="absolute inset-0 bg-gradient-to-t from-ink/30 via-transparent to-transparent opacity-0 transition-opacity group-hover:opacity-100" />
          <div className="absolute bottom-3 left-3 rounded-lg bg-ink/70 px-2.5 py-1 text-[11px] font-medium text-white opacity-0 backdrop-blur transition-opacity group-hover:opacity-100">
            اضغط للتكبير
          </div>
        </div>
      </button>

      <div className="mt-3 grid grid-cols-3 gap-2">
        {shots.map((s, i) => (
          <button
            key={s.viewport}
            onClick={() => onActiveChange(i)}
            className={cn(
              "group relative overflow-hidden rounded-xl border bg-white/70 shadow-sm transition",
              active === i
                ? "border-brand ring-2 ring-brand/30"
                : "border-hairline hover:border-brand/40"
            )}
          >
            <div
              className="relative w-full bg-panel/5"
              style={{ aspectRatio: `${s.width} / ${s.height}` }}
            >
              <img
                src={s.url}
                alt={s.label}
                loading="lazy"
                className="absolute inset-0 h-full w-full object-cover object-top"
                onError={(e) => {
                  (e.currentTarget as HTMLImageElement).style.display = "none";
                }}
              />
            </div>
            <div className="flex items-center justify-between border-t border-hairline bg-white/80 px-2 py-1 text-[10px] font-bold text-ink">
              <span>{s.label}</span>
            </div>
          </button>
        ))}
      </div>

      {preview && (
        <div
          className="fixed inset-0 z-50 grid place-items-center bg-ink/70 p-4 backdrop-blur"
          onClick={() => setPreview(null)}
        >
          <div
            className="relative max-h-[90vh] w-full max-w-5xl overflow-auto rounded-2xl bg-white shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="sticky top-0 z-10 flex items-center justify-between border-b border-hairline bg-white/95 px-4 py-2.5 backdrop-blur">
              <div className="text-sm font-bold text-ink">{preview.label}</div>
              <button
                onClick={() => setPreview(null)}
                className="rounded-full p-1 text-muted-foreground hover:bg-muted hover:text-ink"
                aria-label="إغلاق"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <img src={preview.url} alt={preview.label} className="block w-full" />
          </div>
        </div>
      )}
    </div>
  );
}
