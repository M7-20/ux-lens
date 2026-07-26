import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { z } from "zod";
import { ArrowRight, ChevronDown, Check, AlertTriangle, X, Download, RefreshCw } from "lucide-react";
import { AppHeader } from "@/components/app-header";
import { ScoreGauge } from "@/components/score-gauge";
import { Button } from "@/components/ui/button";
import { getAudit, CATEGORY_LABELS, type Audit, type Rule, type Status, type Category } from "@/services/api";
import { cn } from "@/lib/utils";

const searchSchema = z.object({ url: z.string() });

export const Route = createFileRoute("/results")({
  validateSearch: searchSchema,
  head: () => ({
    meta: [
      { title: "UX Lens — نتائج الفحص" },
      { name: "description", content: "تقرير امتثال الموقع الحكومي لمعايير هيئة الحكومة الرقمية." },
      { property: "og:title", content: "UX Lens — نتائج الفحص" },
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
  const [filter, setFilter] = useState<"all" | Status>("all");

  useEffect(() => { getAudit(url).then(setAudit); }, [url]);

  const rules = useMemo(() => {
    if (!audit) return [];
    const sorted = [...audit.rules].sort((a, b) => SEVERITY[a.status] - SEVERITY[b.status] || a.id - b.id);
    return filter === "all" ? sorted : sorted.filter((r) => r.status === filter);
  }, [audit, filter]);

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

  if (!audit) {
    return (
      <div className="min-h-screen bg-background">
        <AppHeader />
        <div className="mx-auto max-w-4xl px-4 py-24 text-center text-sm text-muted-foreground">جارٍ التحميل…</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <AppHeader />
      <main className="mx-auto max-w-6xl px-4 py-8 md:px-6">
        {/* Header */}
        <div className="mb-6 flex flex-col justify-between gap-4 md:flex-row md:items-end">
          <div className="min-w-0">
            <div className="text-xs text-muted-foreground">تقرير الفحص</div>
            <div className="ltr mt-1 truncate font-mono text-lg text-ink">{audit.url}</div>
            <div className="mt-1 text-xs text-muted-foreground">
              {new Date(audit.scannedAt).toLocaleString("ar-SA", { dateStyle: "long", timeStyle: "short" })}
              {" · "}المدة: <span className="font-mono">{audit.durationSec}s</span>
            </div>
          </div>
          <div className="flex gap-2">
            <Button asChild variant="outline" className="border-hairline">
              <Link to="/"><RefreshCw className="ml-1 h-4 w-4" />فحص جديد</Link>
            </Button>
            <Button className="bg-brand text-brand-foreground hover:bg-brand/90" onClick={() => window.print()}>
              <Download className="ml-1 h-4 w-4" />تصدير PDF
            </Button>
          </div>
        </div>

        {/* Score panel */}
        <section className="grid gap-6 rounded-2xl bg-panel p-6 text-panel-foreground md:grid-cols-[auto_1fr] md:p-8">
          <div className="mx-auto md:mx-0">
            <ScoreGauge value={audit.score} grade={audit.grade} />
          </div>
          <div className="flex flex-col justify-center gap-6">
            <div>
              <div className="text-sm text-panel-foreground/70">نتيجة الامتثال الإجمالية</div>
              <h2 className="mt-1 text-2xl font-semibold">
                {audit.grade === "A" ? "امتثال ممتاز" : audit.grade === "B" ? "امتثال جيد" : audit.grade === "C" ? "يحتاج تحسينات" : "امتثال ضعيف"}
              </h2>
              <p className="mt-1 max-w-lg text-sm text-panel-foreground/70">
                نتيجة الموقع من مطابقته للمعايير الـ27 المعتمدة من هيئة الحكومة الرقمية.
              </p>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <Tally label="مطابق" count={tally.pass} color="var(--pass)" />
              <Tally label="يحتاج تحسين" count={tally.warn} color="var(--warn)" />
              <Tally label="مخالف" count={tally.fail} color="var(--fail)" />
            </div>
          </div>
        </section>

        {/* Category breakdown */}
        <section className="mt-10">
          <h3 className="mb-3 text-sm font-semibold text-ink">التقييم حسب الفئة</h3>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {categoryStats.map((c) => (
              <div key={c.category} className="rounded-xl border border-hairline bg-surface p-4">
                <div className="flex items-baseline justify-between">
                  <div className="text-sm font-medium text-ink">{CATEGORY_LABELS[c.category]}</div>
                  <div className="font-mono text-sm tabular-nums text-muted-foreground">{c.pct}%</div>
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
        </section>

        {/* Filters + rules */}
        <section className="mt-10">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <h3 className="text-sm font-semibold text-ink">تفاصيل المعايير ({audit.rules.length})</h3>
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
                    "rounded-full border px-3 py-1 text-xs transition",
                    filter === c.k
                      ? "border-ink bg-ink text-background"
                      : "border-hairline bg-surface text-muted-foreground hover:border-ink/40 hover:text-ink"
                  )}
                >
                  {c.label} <span className="font-mono tabular-nums">({c.n})</span>
                </button>
              ))}
            </div>
          </div>

          <div className="divide-y divide-hairline overflow-hidden rounded-xl border border-hairline bg-surface">
            {rules.map((r) => <RuleRow key={r.id} rule={r} />)}
            {rules.length === 0 && (
              <div className="p-10 text-center text-sm text-muted-foreground">لا توجد معايير مطابقة للفلتر.</div>
            )}
          </div>
        </section>

        <footer className="mt-16 border-t border-hairline pt-6 text-xs text-muted-foreground">
          UX Lens · وزارة البيئة والمياه والزراعة · معايير هيئة الحكومة الرقمية
        </footer>
      </main>
    </div>
  );
}

function Tally({ label, count, color }: { label: string; count: number; color: string }) {
  return (
    <div className="rounded-lg border border-white/10 bg-white/5 p-3">
      <div className="flex items-center gap-2">
        <span className="h-2 w-2 rounded-full" style={{ background: color }} />
        <span className="text-xs text-panel-foreground/70">{label}</span>
      </div>
      <div className="mt-1 font-mono text-2xl font-semibold tabular-nums">{count}</div>
    </div>
  );
}

function StatusIcon({ status }: { status: Status }) {
  const base = "grid h-8 w-8 shrink-0 place-items-center rounded-full";
  if (status === "pass") return <div className={cn(base, "bg-pass/10 text-pass")}><Check className="h-4 w-4" /></div>;
  if (status === "warn") return <div className={cn(base, "bg-warn/10 text-warn")}><AlertTriangle className="h-4 w-4" /></div>;
  return <div className={cn(base, "bg-fail/10 text-fail")}><X className="h-4 w-4" /></div>;
}

function RuleRow({ rule }: { rule: Rule }) {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-4 px-4 py-3 text-right transition hover:bg-background md:px-5"
        aria-expanded={open}
      >
        <StatusIcon status={rule.status} />
        <span className="font-mono text-xs tabular-nums text-muted-foreground">
          {String(rule.id).padStart(2, "0")}
        </span>
        <span className="min-w-0 flex-1 truncate text-sm font-medium text-ink">{rule.title}</span>
        <span className="hidden shrink-0 rounded-md border border-hairline bg-background px-2 py-0.5 text-xs text-muted-foreground md:inline">
          {CATEGORY_LABELS[rule.category]}
        </span>
        <ChevronDown className={cn("h-4 w-4 shrink-0 text-muted-foreground transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <div className="border-t border-hairline bg-background/50 px-4 py-4 md:px-5 md:pr-16">
          <p className="text-sm leading-relaxed text-ink/80">{rule.description}</p>
          {rule.recommendation && (
            <div className="mt-3 rounded-lg border-r-2 border-brand bg-brand/5 p-3">
              <div className="mb-1 flex items-center gap-1.5 text-xs font-semibold text-brand">
                <ArrowRight className="h-3.5 w-3.5" /> التوصية
              </div>
              <div className="text-sm text-ink/90">{rule.recommendation}</div>
            </div>
          )}
          {rule.evidence && (
            <div className="mt-3">
              <div className="mb-1 text-xs text-muted-foreground">دليل تقني</div>
              <div className="ltr overflow-x-auto rounded-md bg-panel px-3 py-2 font-mono text-xs text-panel-foreground/90">
                {rule.evidence}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
