import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useMemo, useRef, useState } from "react";
import { z } from "zod";
import { ArrowRight, ChevronDown, Check, AlertTriangle, X, Download, RefreshCw, Monitor, Tablet, Smartphone, MapPin, Loader2, HelpCircle, Globe, Clock } from "lucide-react";
import { AppHeader } from "@/components/app-header";
import { Button } from "@/components/ui/button";
import { getAudit, CATEGORY_LABELS, type Audit, type Rule, type Status, type Screenshot } from "@/services/api";
import { cn } from "@/lib/utils";

const searchSchema = z.object({ url: z.string() });

export const Route = createFileRoute("/results")({
  validateSearch: searchSchema,
  head: () => ({
    meta: [
      { title: "UX LENS — نتائج الفحص" },
      { name: "description", content: "تقرير امتثال الموقع الحكومي لمعايير هيئة الحكومة الرقمية." },
      { property: "og:title", content: "UX LENS — نتائج الفحص" },
      { property: "og:description", content: "تقرير مفصّل يعرض 27 معيارًا مع التوصيات." },
      { name: "robots", content: "noindex" },
    ],
  }),
  component: Results,
});

const SEVERITY: Record<Status, number> = { fail: 0, warn: 1, manual_review: 2, pass: 3 };

function Results() {
  const { url } = Route.useSearch();
  const [audit, setAudit] = useState<Audit | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | Status>("all");
  const [activeShot, setActiveShot] = useState(0);
  const [selectedRuleId, setSelectedRuleId] = useState<string | null>(null);
  const [allExpanded, setAllExpanded] = useState(false);
  const [expandToken, setExpandToken] = useState(0);

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

  const regionRules = useMemo(() => rules.filter((r) => r.region), [rules]);

  const tally = useMemo(() => {
    if (!audit) return { pass: 0, warn: 0, fail: 0, manual_review: 0 };
    return audit.rules.reduce(
      (acc, r) => ({ ...acc, [r.status]: acc[r.status] + 1 }),
      { pass: 0, warn: 0, fail: 0, manual_review: 0 }
    );
  }, [audit]);


  function handleActivateRule(rule: Rule) {
    setSelectedRuleId((id) => (id === rule.id ? null : rule.id));
    if (rule.region && audit) {
      const desktopIndex = audit.screenshots.findIndex((s) => s.viewport === "desktop");
      if (desktopIndex >= 0) setActiveShot(desktopIndex);
    }
  }

  // token increments on every press so RuleRow can tell "a new bulk command arrived"
  // apart from "the same open/close value as last time" — a plain boolean prop can't do that.
  function toggleExpandAll() {
    setAllExpanded((v) => !v);
    setExpandToken((t) => t + 1);
  }
  const expandSignal = { open: allExpanded, token: expandToken };

  if (error) {
    return (
      <div className="min-h-screen">
        <AppHeader />
        <div className="mx-auto flex max-w-md flex-col items-center gap-4 px-4 py-24 text-center">
          <div className="grid h-12 w-12 place-items-center rounded-md bg-fail/10 text-fail">
            <AlertTriangle className="h-6 w-6" />
          </div>
          <p className="text-sm text-ink/80">{error}</p>
          <Button asChild className="rounded-md bg-brand text-brand-foreground hover:bg-brand-deep">
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

  const gradeTint = audit.grade === "D" ? "var(--fail)" : audit.grade === "C" ? "var(--warn)" : "var(--pass)";

  return (
    <div className="min-h-screen print:h-auto print:overflow-visible md:flex md:h-screen md:flex-col md:overflow-hidden">
      <AppHeader />
      <main className="mx-auto w-full max-w-6xl px-4 py-4 print:h-auto print:overflow-visible md:flex md:min-h-0 md:flex-1 md:flex-col md:overflow-hidden md:px-6 md:py-4">
        {/* Compact top bar: URL/meta, progress + scores + grade, tally counts, actions — all in one strip */}
        <div className="glass shrink-0 rounded-lg p-4 md:flex md:flex-wrap md:items-center md:gap-5">
          <div className="min-w-0 md:flex-1">
            <div dir="ltr" className="flex items-center gap-1.5">
              <Globe className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
              <span className="truncate font-mono text-sm font-semibold text-ink">{audit.url}</span>
            </div>
            <div dir="ltr" className="mt-0.5 flex items-center gap-1.5 text-[11px] text-muted-foreground">
              <Clock className="h-3 w-3 shrink-0" />
              <span>{new Date(audit.scannedAt).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" })}</span>
              <span>·</span>
              <span className="font-mono">{audit.durationSec}s</span>
            </div>
          </div>

          <div className="mt-3 flex items-center gap-3 md:mt-0">
            <div className="h-1.5 w-28 overflow-hidden rounded-full bg-hairline md:w-32">
              <div
                className="h-full rounded-full bg-brand transition-all duration-700"
                style={{ width: `${audit.score}%` }}
              />
            </div>
            <div dir="ltr" className="font-mono text-sm font-bold tabular-nums text-ink">{audit.score}%</div>
            <div className="hidden text-[11px] text-muted-foreground md:block">
              مؤكد · <span dir="ltr" className="inline-block font-mono">{audit.scoreEstimated}%</span> شامل
            </div>
            <div
              className="grid h-6 w-6 shrink-0 place-items-center rounded-full text-[11px] font-bold text-white"
              style={{ background: gradeTint }}
            >
              {audit.grade}
            </div>
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs md:mt-0">
            <MiniTally label="مخالف" count={tally.fail} tint="var(--fail)" />
            <MiniTally label="تحسين" count={tally.warn} tint="var(--warn)" />
            <MiniTally label="مطابق" count={tally.pass} tint="var(--pass)" />
            {tally.manual_review > 0 && (
              <MiniTally label="تحقق يدوي" count={tally.manual_review} tint="var(--muted-foreground)" />
            )}
          </div>

          <div className="mt-3 flex gap-2 md:mt-0">
            <Button asChild variant="outline" size="sm" className="rounded-md border-hairline bg-white">
              <Link to="/"><RefreshCw className="ml-1 h-3.5 w-3.5" />فحص جديد</Link>
            </Button>
            <Button
              size="sm"
              className="rounded-md bg-brand text-brand-foreground hover:bg-brand-deep"
              onClick={() => window.print()}
            >
              <Download className="ml-1 h-3.5 w-3.5" />تصدير PDF
            </Button>
          </div>
        </div>

        {/* Dashboard body: rules (right) + screenshot (left), each scrolls independently on md+ */}
        <section className="mt-4 grid gap-4 print:grid-cols-1 print:overflow-visible md:min-h-0 md:flex-1 md:grid-cols-12 md:overflow-hidden">
          <div className="md:col-span-7 md:min-h-0">
            <div className="glass rounded-lg p-6 print:overflow-visible md:flex md:h-full md:flex-col md:overflow-hidden">
              <div className="mb-5 flex flex-wrap items-center justify-between gap-3 md:shrink-0">
                <h3 className="text-base font-semibold text-ink">
                  تفاصيل التدقيق حسب معايير (DGA) — {audit.rules.length} معيار
                </h3>
                <div className="flex flex-wrap gap-2">
                  <button
                    onClick={toggleExpandAll}
                    className="rounded-md border border-hairline bg-white px-3 py-1 text-xs font-medium text-muted-foreground transition hover:border-brand/40 hover:text-brand print:hidden"
                  >
                    {allExpanded ? "طيّ الكل" : "فتح الكل"}
                  </button>
                  {([
                    { k: "all", label: "الكل", n: audit.rules.length },
                    { k: "fail", label: "مخالف", n: tally.fail },
                    { k: "warn", label: "تحسين", n: tally.warn },
                    { k: "pass", label: "مطابق", n: tally.pass },
                    { k: "manual_review", label: "تحقق يدوي", n: tally.manual_review },
                  ] as const).map((c) => (
                    <button
                      key={c.k}
                      onClick={() => setFilter(c.k as any)}
                      className={cn(
                        "rounded-md border px-3 py-1 text-xs font-medium transition",
                        filter === c.k
                          ? "border-brand bg-brand text-brand-foreground"
                          : "border-hairline bg-white text-muted-foreground hover:border-brand/40 hover:text-brand"
                      )}
                    >
                      {c.label} <span className="font-mono tabular-nums">({c.n})</span>
                    </button>
                  ))}
                </div>
              </div>

              <div className="space-y-2 print:overflow-visible md:min-h-0 md:flex-1 md:overflow-y-auto md:pl-1">
                {rules.map((r) => (
                  <RuleRow
                    key={r.id}
                    rule={r}
                    active={selectedRuleId === r.id}
                    onActivate={handleActivateRule}
                    expandSignal={expandSignal}
                  />
                ))}
                {rules.length === 0 && (
                  <div className="p-10 text-center text-sm text-muted-foreground">لا توجد معايير مطابقة للفلتر.</div>
                )}
              </div>
            </div>
          </div>

          <div className="print:hidden md:col-span-5 md:min-h-0">
            <ScreenshotPanel
              shots={audit.screenshots}
              url={audit.url}
              active={activeShot}
              onActiveChange={setActiveShot}
              activeRule={selectedRule}
              showAllRegions={allExpanded}
              regionRules={regionRules}
            />
          </div>
        </section>

        {/* Print-only: the on-screen scrollable/multi-page image causes bounding boxes
            (position:absolute) to detach from the image when Chromium paginates a tall
            element across pages — they end up floating on their own page. Scaling the
            whole image to fit one page, with page-break-inside:avoid, sidesteps that
            entirely: the image is never split, so its overlay boxes never can be either. */}
        {(() => {
          const printShot = audit.screenshots.find((s) => s.viewport === "desktop") ?? audit.screenshots[0];
          if (!printShot) return null;
          return (
            <div className="hidden print:block print:break-inside-avoid print:break-before-page">
              <h3 className="mb-3 text-sm font-semibold text-ink">لقطة الصفحة المفحوصة كاملة</h3>
              <div
                className="relative mx-auto print:h-[85vh]"
                style={{ aspectRatio: `${printShot.width} / ${printShot.height}` }}
              >
                <img
                  src={printShot.url}
                  alt={`لقطة ${printShot.label} للموقع ${audit.url}`}
                  className="absolute inset-0 h-full w-full object-contain"
                />
                {regionRules.map((r) => (
                  <div
                    key={r.id}
                    className="absolute rounded-md border-2 border-fail"
                    style={{
                      left: `${r.region!.x}%`,
                      top: `${r.region!.y}%`,
                      width: `${r.region!.width}%`,
                      height: `${r.region!.height}%`,
                    }}
                  >
                    <span className="absolute -top-2.5 -right-2.5 grid h-5 w-5 place-items-center rounded-full bg-fail text-[10px] font-black text-white">!</span>
                  </div>
                ))}
              </div>
            </div>
          );
        })()}

        <footer className="mt-6 border-t border-hairline pt-4 text-center text-xs text-muted-foreground md:hidden">
          UX LENS · معايير هيئة الحكومة الرقمية
        </footer>
      </main>
    </div>
  );
}

function MiniTally({ label, count, tint }: { label: string; count: number; tint: string }) {
  return (
    <div className="inline-flex items-center gap-1.5">
      <span className="h-2 w-2 rounded-full" style={{ background: tint }} />
      <span className="text-muted-foreground">{label}</span>
      <span className="font-mono font-bold tabular-nums text-ink">{count}</span>
    </div>
  );
}

function StatusIcon({ status }: { status: Status }) {
  const base = "grid h-10 w-10 shrink-0 place-items-center rounded-md";
  if (status === "pass") return <div className={cn(base, "bg-pass/10 text-pass")}><Check className="h-5 w-5" /></div>;
  if (status === "warn") return <div className={cn(base, "bg-warn/10 text-warn")}><AlertTriangle className="h-5 w-5" /></div>;
  if (status === "manual_review") return <div className={cn(base, "bg-slate-400/10 text-slate-500")}><HelpCircle className="h-5 w-5" /></div>;
  return <div className={cn(base, "bg-fail/10 text-fail")}><X className="h-5 w-5" /></div>;
}

function RuleRow({
  rule,
  active,
  onActivate,
  expandSignal,
}: {
  rule: Rule;
  active: boolean;
  onActivate: (rule: Rule) => void;
  expandSignal: { open: boolean; token: number };
}) {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (expandSignal.token > 0) setOpen(expandSignal.open);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [expandSignal.token]);

  const isPass = rule.status === "pass";
  const displayTitle = isPass ? (rule.titlePass ?? `${CATEGORY_LABELS[rule.category]}: مستوفٍ`) : rule.title;
  const displayDescription = isPass ? rule.descriptionPass : rule.description;
  return (
    <div
      className={cn(
        "overflow-hidden rounded-md border bg-white transition",
        active ? "border-brand ring-1 ring-brand/30" : "border-hairline"
      )}
    >
      <button
        onClick={() => { setOpen((o) => !o); onActivate(rule); }}
        className="flex w-full items-center gap-4 px-4 py-3 text-right transition hover:bg-muted md:px-5"
        aria-expanded={open}
      >
        <StatusIcon status={rule.status} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5 text-sm font-semibold text-ink">
            <span className="truncate">{displayTitle}</span>
            {rule.region && <MapPin className="h-3.5 w-3.5 shrink-0 text-muted-foreground" aria-label="محدد على الصورة" />}
          </div>
          <div className="mt-0.5 text-xs text-muted-foreground">
            {CATEGORY_LABELS[rule.category]}
          </div>
        </div>
        <span className="hidden shrink-0 rounded-md bg-brand/8 px-2.5 py-1 font-mono text-[10px] font-bold text-brand md:inline">
          {rule.id}
        </span>
        <ChevronDown className={cn("h-4 w-4 shrink-0 text-muted-foreground transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <div className="border-t border-hairline bg-muted px-4 py-4 md:px-5">
          {displayDescription ? (
            <p className="text-sm leading-relaxed text-ink/80">{displayDescription}</p>
          ) : isPass ? (
            <p className="text-sm leading-relaxed text-pass">لا توجد ملاحظات — هذا المعيار مستوفى بالكامل.</p>
          ) : null}
          {!isPass && rule.recommendation && (
            <div className="mt-3 rounded-md border-r-2 border-hairline bg-white p-3">
              <div className="mb-1 flex items-center gap-1.5 text-xs font-bold text-ink">
                <ArrowRight className="h-3.5 w-3.5" /> التوصية
              </div>
              <div className="text-sm text-ink/90">{rule.recommendation}</div>
            </div>
          )}
          {rule.evidence && (
            <div className="mt-3">
              <div className="mb-1 text-xs text-muted-foreground">دليل تقني</div>
              <div dir="rtl" className="overflow-x-auto rounded-md bg-panel px-3 py-2 text-xs text-panel-foreground/90">
                {rule.evidence}
              </div>
            </div>
          )}
          {rule.region && (
            <div className="mt-3 flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
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
  showAllRegions,
  regionRules,
}: {
  shots: Screenshot[];
  url: string;
  active: number;
  onActiveChange: (i: number) => void;
  activeRule: Rule | null;
  showAllRegions: boolean;
  regionRules: Rule[];
}) {
  const highlightRef = useRef<HTMLDivElement>(null);
  const current = shots[active];
  const highlight = activeRule?.region && current?.viewport === "desktop" ? activeRule.region : null;
  const allHighlights = showAllRegions && current?.viewport === "desktop" ? regionRules : [];

  useEffect(() => {
    if (!showAllRegions && highlight && highlightRef.current) {
      highlightRef.current.scrollIntoView({ behavior: "smooth", block: "center" });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeRule?.id]);

  if (!shots.length) return null;

  return (
    <div className="glass rounded-lg p-6 print:overflow-visible md:flex md:h-full md:flex-col md:overflow-hidden">
      {shots.length > 1 && (
        <div className="mb-4 flex flex-wrap gap-2 md:shrink-0">
          {shots.map((s, i) => {
            const Icon = VIEWPORT_ICON[s.viewport];
            return (
              <button
                key={s.viewport}
                onClick={() => onActiveChange(i)}
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-md border px-3 py-1 text-xs font-medium transition",
                  active === i
                    ? "border-brand bg-brand text-brand-foreground"
                    : "border-hairline bg-white text-muted-foreground hover:border-brand/40 hover:text-brand"
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
      )}

      {showAllRegions && (
        <div className="mb-3 flex items-center gap-2 rounded-md border border-fail/30 bg-fail/5 px-3 py-2 text-xs font-medium text-ink md:shrink-0">
          <MapPin className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
          <span>تُعرض كل مواضع المخالفات على الصورة ({allHighlights.length})</span>
        </div>
      )}

      <div className="max-h-[80vh] w-full overflow-y-auto overscroll-auto rounded-md border border-hairline print:max-h-none print:overflow-visible md:max-h-none md:min-h-0 md:flex-1">
        <div className="relative">
          <img
            src={current.url}
            alt={`لقطة ${current.label} للموقع ${url}`}
            loading="lazy"
            className="block w-full"
            onError={(e) => {
              (e.currentTarget as HTMLImageElement).style.display = "none";
            }}
          />

          {showAllRegions
            ? allHighlights.map((r) => (
                <div
                  key={r.id}
                  className="pointer-events-none absolute rounded-md border-2 border-fail bg-fail/10"
                  style={{
                    left: `${r.region!.x}%`,
                    top: `${r.region!.y}%`,
                    width: `${r.region!.width}%`,
                    height: `${r.region!.height}%`,
                  }}
                >
                  <span className="absolute -top-2.5 -right-2.5 grid h-5 w-5 place-items-center rounded-full bg-fail text-[10px] font-black text-white">!</span>
                </div>
              ))
            : highlight && (
                <div
                  ref={highlightRef}
                  className="pointer-events-none absolute rounded-md border-2 border-fail shadow-[0_0_0_9999px_rgba(31,41,55,0.35)]"
                  style={{
                    left: `${highlight.x}%`,
                    top: `${highlight.y}%`,
                    width: `${highlight.width}%`,
                    height: `${highlight.height}%`,
                  }}
                >
                  <span className="absolute -top-2.5 -right-2.5 grid h-5 w-5 place-items-center rounded-full bg-fail text-[10px] font-black text-white">!</span>
                </div>
              )}
        </div>
      </div>
    </div>
  );
}
