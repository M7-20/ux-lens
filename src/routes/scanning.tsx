import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { Check, Loader2, AlertTriangle } from "lucide-react";
import { z } from "zod";
import { AppHeader, AppLogo } from "@/components/app-header";
import { getAudit } from "@/services/api";

const searchSchema = z.object({ url: z.string() });

export const Route = createFileRoute("/scanning")({
  validateSearch: searchSchema,
  head: () => ({
    meta: [
      { title: "تدقيق الامتثال الرقمي — جارٍ الفحص" },
      { name: "description", content: "جارٍ فحص الموقع وفق معايير هيئة الحكومة الرقمية." },
      { property: "og:title", content: "تدقيق الامتثال الرقمي — جارٍ الفحص" },
      { property: "og:description", content: "تحليل آلي للموقع الحكومي." },
      { name: "robots", content: "noindex" },
    ],
  }),
  component: Scanning,
});

const STEPS = [
  "فتح الصفحة عبر Playwright",
  "التقاط بنية الصفحة",
  "تحليل المحتوى عبر Gemini",
  "مطابقة المعايير الـ28",
];

function Scanning() {
  const { url } = Route.useSearch();
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    const timers: ReturnType<typeof setTimeout>[] = [];

    // Steps 0-1 (opening the page, reading its structure) are genuinely fast —
    // give them a short head start. Step 2 (the Gemini scan) is where almost all
    // the real time goes, so it stays "in progress" until the actual audit call
    // resolves — no fake timers pretending it's done before it is.
    timers.push(setTimeout(() => active && setStep((s) => Math.max(s, 1)), 900));
    timers.push(setTimeout(() => active && setStep((s) => Math.max(s, 2)), 1800));

    getAudit(url)
      .then(() => {
        if (!active) return;
        setStep(STEPS.length);
        timers.push(setTimeout(() => active && navigate({ to: "/results", search: { url } }), 400));
      })
      .catch((e) => {
        if (active) setError(e instanceof Error ? e.message : "تعذّر إتمام الفحص.");
      });

    return () => { active = false; timers.forEach(clearTimeout); };
  }, [url, navigate]);

  const progress = (step / STEPS.length) * 100;

  return (
    <div className="min-h-screen">
      <AppHeader />
      <main className="mx-auto flex max-w-2xl flex-col items-center px-4 py-16 md:py-24">
        <div className="relative mb-6">
          {!error && <div className="absolute inset-0 -m-4 animate-ping rounded-3xl bg-brand/10" />}
          <AppLogo size={72} />
        </div>
        <h1 className="text-2xl font-black text-ink">{error ? "تعذّر إتمام الفحص" : "جارٍ فحص الموقع"}</h1>
        <p className="ltr mt-1 font-mono text-sm text-muted-foreground">{url}</p>

        {error ? (
          <div className="glass mt-10 w-full space-y-4 rounded-3xl p-6 text-center shadow-xl shadow-brand/5">
            <div className="mx-auto grid h-12 w-12 place-items-center rounded-full bg-fail/10 text-fail">
              <AlertTriangle className="h-6 w-6" />
            </div>
            <p className="text-sm text-ink/80">{error}</p>
            <button
              onClick={() => navigate({ to: "/" })}
              className="rounded-xl bg-gradient-to-br from-brand to-brand-deep px-6 py-2.5 text-sm font-bold text-brand-foreground shadow-lg shadow-brand/20 hover:opacity-95"
            >
              العودة والمحاولة مجددًا
            </button>
          </div>
        ) : (
          <>
            <div className="mt-6 h-1.5 w-full max-w-xs overflow-hidden rounded-full bg-hairline">
              <div
                className="h-full rounded-full bg-gradient-to-r from-brand to-gold transition-all duration-700"
                style={{ width: `${progress}%` }}
              />
            </div>

            <ol className="glass mt-10 w-full space-y-3 rounded-3xl p-4 shadow-xl shadow-brand/5">
              {STEPS.map((label, i) => {
                const done = i < step;
                const active = i === step;
                return (
                  <li
                    key={label}
                    className={`flex items-center gap-3 rounded-2xl border bg-white/70 px-4 py-3 transition ${
                      done ? "border-pass/30" : active ? "border-brand shadow-md shadow-brand/10" : "border-hairline"
                    }`}
                  >
                    <div className={`grid h-8 w-8 place-items-center rounded-full ${
                      done ? "bg-pass text-white" : active ? "bg-brand text-brand-foreground" : "bg-background text-muted-foreground"
                    }`}>
                      {done ? <Check className="h-4 w-4" /> : active ? <Loader2 className="h-4 w-4 animate-spin" /> : <span className="font-mono text-xs font-bold">{i + 1}</span>}
                    </div>
                    <span className={`text-sm ${done ? "text-muted-foreground line-through decoration-hairline" : active ? "font-bold text-ink" : "text-muted-foreground"}`}>
                      {label}
                    </span>
                  </li>
                );
              })}
            </ol>
          </>
        )}
      </main>
    </div>
  );
}
