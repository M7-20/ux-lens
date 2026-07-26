import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { Check, Loader2 } from "lucide-react";
import { z } from "zod";
import { AppHeader, AppLogo } from "@/components/app-header";
import { startAudit } from "@/services/api";

const searchSchema = z.object({ url: z.string() });

export const Route = createFileRoute("/scanning")({
  validateSearch: searchSchema,
  head: () => ({
    meta: [
      { title: "عدسة تجربة المستخدم — جارٍ الفحص" },
      { name: "description", content: "جارٍ فحص الموقع وفق معايير هيئة الحكومة الرقمية." },
      { property: "og:title", content: "عدسة تجربة المستخدم — جارٍ الفحص" },
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

  const progress = (step / STEPS.length) * 100;

  return (
    <div className="min-h-screen">
      <AppHeader />
      <main className="mx-auto flex max-w-2xl flex-col items-center px-4 py-16 md:py-24">
        <div className="relative mb-6">
          <div className="absolute inset-0 -m-4 animate-ping rounded-3xl bg-brand/10" />
          <AppLogo size={72} />
        </div>
        <h1 className="text-2xl font-black text-ink">جارٍ فحص الموقع</h1>
        <p className="ltr mt-1 font-mono text-sm text-muted-foreground">{url}</p>

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
      </main>
    </div>
  );
}
