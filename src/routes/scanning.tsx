import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { Check, Loader2 } from "lucide-react";
import { z } from "zod";
import { AppHeader } from "@/components/app-header";
import { startAudit } from "@/services/api";

const searchSchema = z.object({ url: z.string() });

export const Route = createFileRoute("/scanning")({
  validateSearch: searchSchema,
  head: () => ({
    meta: [
      { title: "UX Lens — جارٍ الفحص" },
      { name: "description", content: "جارٍ فحص الموقع وفق معايير هيئة الحكومة الرقمية." },
      { property: "og:title", content: "UX Lens — جارٍ الفحص" },
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
  "مطابقة المعايير الـ27",
];

function Scanning() {
  const { url } = Route.useSearch();
  const navigate = useNavigate();
  const [step, setStep] = useState(0);

  useEffect(() => {
    let active = true;
    (async () => {
      await startAudit(url);
      for (let i = 0; i < STEPS.length; i++) {
        await new Promise((r) => setTimeout(r, 700));
        if (!active) return;
        setStep(i + 1);
      }
      await new Promise((r) => setTimeout(r, 400));
      if (active) navigate({ to: "/results", search: { url } });
    })();
    return () => { active = false; };
  }, [url, navigate]);

  return (
    <div className="min-h-screen bg-background">
      <AppHeader />
      <main className="mx-auto flex max-w-2xl flex-col items-center px-4 py-16 md:py-24">
        <div className="mb-6 grid h-16 w-16 place-items-center rounded-full bg-panel text-panel-foreground">
          <svg viewBox="0 0 24 24" className="h-8 w-8 animate-spin" style={{ animationDuration: "3s" }} fill="none" stroke="currentColor" strokeWidth="1.5">
            <circle cx="12" cy="12" r="9" />
            <circle cx="12" cy="12" r="3" />
            <path d="M12 3v3M12 18v3M3 12h3M18 12h3" />
          </svg>
        </div>
        <h1 className="text-xl font-semibold text-ink">جارٍ فحص الموقع</h1>
        <p className="ltr mt-1 font-mono text-sm text-muted-foreground">{url}</p>

        <ol className="mt-10 w-full space-y-3">
          {STEPS.map((label, i) => {
            const done = i < step;
            const active = i === step;
            return (
              <li
                key={label}
                className={`flex items-center gap-3 rounded-lg border bg-surface px-4 py-3 transition ${
                  done ? "border-pass/30" : active ? "border-brand" : "border-hairline"
                }`}
              >
                <div className={`grid h-7 w-7 place-items-center rounded-full ${
                  done ? "bg-pass text-white" : active ? "bg-brand text-brand-foreground" : "bg-background text-muted-foreground"
                }`}>
                  {done ? <Check className="h-4 w-4" /> : active ? <Loader2 className="h-4 w-4 animate-spin" /> : <span className="font-mono text-xs">{i + 1}</span>}
                </div>
                <span className={`text-sm ${done ? "text-muted-foreground line-through decoration-hairline" : active ? "text-ink font-medium" : "text-muted-foreground"}`}>
                  {label}
                </span>
              </li>
            );
          })}
        </ol>
      </main>
    </div>
  );
}
