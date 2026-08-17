import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  Outlet,
  createRootRouteWithContext,
  useRouter,
  HeadContent,
  Scripts,
  Link,
} from "@tanstack/react-router";
import { useEffect, type ReactNode } from "react";

import appCss from "../styles.css?url";
// تجاوز ألوان المنصة — يُحمَّل بعد appCss عمداً ليتفوّق عليه بترتيب
// الإعلان. ملف خاص بواحة لا يلمسه فريق ux-lens، فلا يتعارض عند الدمج.
import wahaThemeCss from "../waha-theme.css?url";
import { ThemedBackground } from "@/components/themed-background";
import { initWahaPrefsSync } from "@/lib/waha-prefs";

function NotFoundComponent() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="max-w-md text-center">
        <h1 className="text-7xl font-bold text-foreground">404</h1>
        <h2 className="mt-4 text-xl font-semibold">الصفحة غير موجودة</h2>
        <p className="mt-2 text-sm text-muted-foreground">الرابط المطلوب غير متاح.</p>
        <Link to="/" className="mt-6 inline-flex rounded-md bg-brand px-4 py-2 text-sm text-brand-foreground hover:opacity-90">
          العودة للرئيسية
        </Link>
      </div>
    </div>
  );
}

function ErrorComponent({ reset }: { error: Error; reset: () => void }) {
  const router = useRouter();
  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="max-w-md text-center">
        <h1 className="text-xl font-semibold">تعذّر تحميل الصفحة</h1>
        <p className="mt-2 text-sm text-muted-foreground">حدث خطأ غير متوقع.</p>
        <button
          onClick={() => { router.invalidate(); reset(); }}
          className="mt-6 rounded-md bg-brand px-4 py-2 text-sm text-brand-foreground hover:opacity-90"
        >
          إعادة المحاولة
        </button>
      </div>
    </div>
  );
}

export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()({
  head: () => ({
    meta: [
      { charSet: "utf-8" },
      { name: "viewport", content: "width=device-width, initial-scale=1" },
      { title: "UX LENS — منصة فحص الامتثال الرقمي" },
      { name: "description", content: "أداة داخلية لوزارة البيئة والمياه والزراعة لفحص التزام المواقع الحكومية بمعايير هيئة الحكومة الرقمية." },
      { name: "author", content: "MEWA" },
      { property: "og:title", content: "UX LENS — منصة فحص الامتثال الرقمي" },
      { property: "og:description", content: "فحص المواقع الحكومية السعودية وفق معايير DGA الـ27." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
    links: [
      { rel: "stylesheet", href: appCss },
      { rel: "stylesheet", href: wahaThemeCss },
      { rel: "icon", href: `${import.meta.env.BASE_URL}logo.svg`, type: "image/svg+xml" },
      // Almarai مُستضاف ذاتياً (@font-face في styles.css) بدل Google Fonts CDN —
      // التطبيق يُنشر خلف بوابة معزولة (air-gapped)؛ طلب CDN خارجي كان سيفشل بصمت
      // وقت التشغيل. IBM Plex Mono لم يعد مُحمَّلاً: لا نسخة مُستضافة ذاتياً متوفرة
      // له حالياً، فيرتد المتصفح لبقية سلسلة --font-mono (ui-monospace/SFMono-Regular/
      // monospace) — نفس الفكرة قابلة للتطبيق عليه لاحقاً إن تكرّر الاحتياج.
    ],
  }),
  shellComponent: RootShell,
  component: RootComponent,
  notFoundComponent: NotFoundComponent,
  errorComponent: ErrorComponent,
});

// lang="ar" dir="rtl" يبقى الافتراضي المُصيَّر من الخادم (SSR) — يطابق سلوك
// التطبيق قبل هذا التغيير تماماً لأي طلب بلا كوكي waha_prefs بعد. src/lib/waha-prefs.ts
// يصحّحه على العميل عند الإقلاع إن كانت الكوكي تقول غير ذلك (راجع RootComponent
// أدناه) — قد يظهر ومضة بسيطة قبل تشغيل جافاسكربت في حالة locale=en/theme=dark
// من واحة، وهذا محدود حالياً بغياب قراءة الكوكي على الخادم (SSR) لهذا المكوّن.
function RootShell({ children }: { children: ReactNode }) {
  return (
    <html lang="ar" dir="rtl">
      <head><HeadContent /></head>
      <body>{children}<Scripts /></body>
    </html>
  );
}

function RootComponent() {
  const { queryClient } = Route.useRouteContext();

  // waha ONBOARDING.md §9 — يقرأ كوكي waha_prefs عند الإقلاع + يستمع لبثّ
  // postMessage اللاحق من rail واحة، بلا إعادة تحميل. راجع src/lib/waha-prefs.ts
  // للعقد الكامل (التحقق من event.origin + data.source معاً، الخ).
  useEffect(() => initWahaPrefsSync(), []);

  return (
    <QueryClientProvider client={queryClient}>
      <ThemedBackground />
      <Outlet />
    </QueryClientProvider>
  );
}
