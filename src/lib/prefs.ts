// واحة ONBOARDING.md §9 — اللغة والثيم مصدرهما شريط واحة، لا تبديل خاص بنا.
// نقرأ فقط (لا نكتب كوكي waha_prefs أبداً) — واحة تكتبها وتبثّها، نحن مستهلك بس.
import { useEffect } from "react";

export type Locale = "ar" | "en";
export type Theme = "light" | "dark";
export interface Prefs {
  locale: Locale;
  theme: Theme;
}

export const PREFS_COOKIE_NAME = "waha_prefs";
export const DEFAULT_PREFS: Prefs = { locale: "ar", theme: "light" };

function isLocale(v: unknown): v is Locale {
  return v === "ar" || v === "en";
}
function isTheme(v: unknown): v is Theme {
  return v === "light" || v === "dark";
}

export function parsePrefsCookie(cookieString: string): Prefs | null {
  const match = cookieString.match(/(?:^|;\s*)waha_prefs=([^;]*)/);
  if (!match) return null;
  try {
    const raw = JSON.parse(decodeURIComponent(match[1]));
    if (isLocale(raw?.locale) && isTheme(raw?.theme)) {
      return { locale: raw.locale, theme: raw.theme };
    }
  } catch {
    // كوكي تالف — نتجاهله، الافتراضي يبقى كما هو
  }
  return null;
}

export function applyPrefs(prefs: Prefs): void {
  const html = document.documentElement;
  html.lang = prefs.locale;
  html.dir = prefs.locale === "ar" ? "rtl" : "ltr";
  html.dataset.theme = prefs.theme;
}

// يُحقن حرفياً كسكربت خام بـ<head> (__root.tsx) — يشتغل قبل أي رسم لمنع وميض
// الثيم/الاتجاه الافتراضي (§9: "correct from its very first paint"). IIFE مستقلة
// بدون أي استيراد — تشتغل قبل ما React يوصل، فما تقدر تستدعي الدوال أعلاه مباشرة.
export const PREFS_BOOTSTRAP_SCRIPT = `(function(){try{
  var m = document.cookie.match(/(?:^|; )waha_prefs=([^;]*)/);
  if (!m) return;
  var p = JSON.parse(decodeURIComponent(m[1]));
  if (p && (p.locale === "ar" || p.locale === "en") && (p.theme === "light" || p.theme === "dark")) {
    document.documentElement.lang = p.locale;
    document.documentElement.dir = p.locale === "ar" ? "rtl" : "ltr";
    document.documentElement.dataset.theme = p.theme;
  }
}catch(e){}})();`;

// يسجّل مستمع postMessage من واحة (§9) — يتحقق من المصدر (origin) قبل أي تطبيق،
// وهذا هو الفحص اللي يمنع أي إطار/سكربت ثاني ينتحل رسالة تفضيلات.
export function useWahaPrefs(): void {
  useEffect(() => {
    // مزامنة احتياطية بعد mount — البوتستراب بـ<head> يغطي الرسم الأول أصلاً،
    // هذي فقط تحسباً لو الكوكي تغيّر بين وقت SSR ووقت هذا التنفيذ.
    const fromCookie = parsePrefsCookie(document.cookie);
    if (fromCookie) applyPrefs(fromCookie);

    function onMessage(event: MessageEvent) {
      if (event.origin !== window.location.origin) return; // فحص إلزامي أول
      if (event.data?.source !== "waha" || event.data?.type !== "prefs") return;
      const { locale, theme } = event.data;
      if (isLocale(locale) && isTheme(theme)) applyPrefs({ locale, theme });
    }

    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, []);
}
