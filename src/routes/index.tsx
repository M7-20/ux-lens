import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { ArrowLeft, Clock } from "lucide-react";
import { AppHeader } from "@/components/app-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { getRecentAudits } from "@/services/api";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "UX Lens — فحص جديد" },
      { name: "description", content: "ابدأ فحصًا جديدًا لموقع حكومي وفق معايير هيئة الحكومة الرقمية." },
      { property: "og:title", content: "UX Lens — فحص جديد" },
      { property: "og:description", content: "أداة داخلية لفحص التزام المواقع الحكومية بمعايير DGA." },
    ],
  }),
  component: Index,
});

const SAMPLES = ["mewa.gov.sa", "my.gov.sa", "dga.gov.sa"];

function Index() {
  const navigate = useNavigate();
  const [url, setUrl] = useState("");
  const [recent, setRecent] = useState<Awaited<ReturnType<typeof getRecentAudits>>>([]);

  useEffect(() => { getRecentAudits().then(setRecent); }, []);

  const submit = (raw: string) => {
    const v = raw.trim();
    if (!v) return;
    const full = /^https?:\/\//.test(v) ? v : `https://${v}`;
    navigate({ to: "/scanning", search: { url: full } });
  };

  return (
    <div className="min-h-screen bg-background">
      <AppHeader />
      <main className="mx-auto max-w-4xl px-4 py-12 md:px-6 md:py-20">
        <div className="mb-2 inline-flex items-center gap-2 rounded-full border border-hairline bg-surface px-3 py-1 text-xs text-muted-foreground">
          <span className="h-1.5 w-1.5 rounded-full bg-brand" />
          أداة داخلية · وزارة البيئة والمياه والزراعة
        </div>
        <h1 className="mt-4 text-3xl font-bold tracking-tight text-ink md:text-4xl">
          فحص الامتثال الرقمي للمواقع الحكومية
        </h1>
        <p className="mt-3 max-w-2xl text-muted-foreground">
          أدخل رابط الموقع الحكومي لبدء فحصه آليًا وفق المعايير الـ27 لهيئة الحكومة الرقمية.
        </p>

        <form
          onSubmit={(e) => { e.preventDefault(); submit(url); }}
          className="mt-8 rounded-xl border border-hairline bg-surface p-4 shadow-[0_1px_0_rgba(0,0,0,0.02)] md:p-5"
        >
          <label htmlFor="url" className="mb-2 block text-sm font-medium text-ink">رابط الموقع</label>
          <div className="flex flex-col gap-3 md:flex-row">
            <Input
              id="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://example.gov.sa"
              dir="ltr"
              className="ltr h-12 flex-1 rounded-lg border-hairline bg-background font-mono text-[15px] placeholder:text-muted-foreground/60 focus-visible:ring-brand"
              autoFocus
            />
            <Button
              type="submit"
              className="h-12 rounded-lg bg-brand px-6 text-brand-foreground hover:bg-brand/90"
            >
              ابدأ الفحص
              <ArrowLeft className="mr-1 h-4 w-4" />
            </Button>
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-2">
            <span className="text-xs text-muted-foreground">أمثلة سريعة:</span>
            {SAMPLES.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => { setUrl(`https://${s}`); submit(`https://${s}`); }}
                className="ltr rounded-full border border-hairline bg-background px-3 py-1 font-mono text-xs text-ink transition hover:border-brand hover:text-brand"
              >
                {s}
              </button>
            ))}
          </div>
        </form>

        <section className="mt-12">
          <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold text-ink">
            <Clock className="h-4 w-4 text-muted-foreground" />
            الفحوصات السابقة
          </h2>
          <div className="divide-y divide-hairline overflow-hidden rounded-xl border border-hairline bg-surface">
            {recent.map((r) => (
              <button
                key={r.url + r.scannedAt}
                onClick={() => submit(r.url)}
                className="flex w-full items-center justify-between gap-4 px-4 py-3 text-right transition hover:bg-background"
              >
                <div className="min-w-0">
                  <div className="ltr truncate font-mono text-sm text-ink">{r.url}</div>
                  <div className="mt-0.5 text-xs text-muted-foreground">
                    {new Date(r.scannedAt).toLocaleDateString("ar-SA", { year: "numeric", month: "long", day: "numeric" })}
                  </div>
                </div>
                <ScoreBadge score={r.score} />
              </button>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}

function ScoreBadge({ score }: { score: number }) {
  const color = score >= 85 ? "text-pass border-pass/30 bg-pass/10"
    : score >= 70 ? "text-warn border-warn/30 bg-warn/10"
    : "text-fail border-fail/30 bg-fail/10";
  return (
    <span className={`inline-flex shrink-0 items-center rounded-md border px-2.5 py-1 font-mono text-sm tabular-nums ${color}`}>
      {score}%
    </span>
  );
}
