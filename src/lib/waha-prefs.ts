// waha ONBOARDING.md §9 — waha's shell rail is the SINGLE control for
// language + theme across every framed app; this app never had its own
// toggle (no localStorage, no in-app switch), so the contract is applied
// unconditionally rather than gated behind "only when running under waha"
// the way a system migrating an existing toggle would need to (compare
// ../sahem/ui/src/utils/wahaPrefs.ts, which guards against clobbering
// sahem's own pre-existing preference store). A missing/malformed cookie or
// message here is simply "nothing to apply" — ux-lens keeps rendering its
// current default (lang="ar" dir="rtl", light theme) exactly as before this
// module existed, so standalone dev/testing (no waha in front) is
// unaffected.

export const WAHA_PREFS_COOKIE = "waha_prefs";

export type Locale = "ar" | "en";
export type Theme = "light" | "dark";

export interface WahaPrefs {
  locale: Locale;
  theme: Theme;
}

const isValidLocale = (v: unknown): v is Locale => v === "ar" || v === "en";
const isValidTheme = (v: unknown): v is Theme => v === "light" || v === "dark";

function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const escaped = name.replace(/[.$?*|{}()[\]\\/+^]/g, "\\$&");
  const match = document.cookie.match(new RegExp(`(?:^|; )${escaped}=([^;]*)`));
  return match ? match[1] : null;
}

/**
 * يقرأ ويتحقق من كوكي `waha_prefs` (`Path=/`، غير httpOnly، نفس الأصل دائماً
 * خلف بوابة واحة — راجع ONBOARDING.md §9). يرجّع null لكوكي غائب/تالف/جزئي
 * الشكل بدل رمي خطأ — المستدعي يبقي الافتراضي الحالي بدلاً من اعتباره عطلاً.
 */
export function readWahaPrefsCookie(): WahaPrefs | null {
  const raw = readCookie(WAHA_PREFS_COOKIE);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(decodeURIComponent(raw));
    if (isValidLocale(parsed?.locale) && isValidTheme(parsed?.theme)) {
      return { locale: parsed.locale, theme: parsed.theme };
    }
  } catch {
    // كوكي تالف — يُعامل كأنه غائب، لا كخطأ.
  }
  return null;
}

/** lang + dir فقط — لا ترجمة نصوص (راجع ملاحظة "ما زال عربي بالكامل" في
 * تقرير الانضمام: هذا يبدّل اتجاه/سمة الصفحة، لا محتواها). */
export function applyLocale(locale: Locale): void {
  const root = document.documentElement;
  root.lang = locale;
  root.dir = locale === "ar" ? "rtl" : "ltr";
}

/** يبدّل صنف Tailwind `.dark` (`@custom-variant dark (&:is(.dark *))` في
 * styles.css يعتمد عليه) + يضبط `data-theme` كسمة عامة لأي CSS مستقبلي لا
 * يريد الاعتماد على صنف Tailwind تحديداً. */
export function applyTheme(theme: Theme): void {
  const root = document.documentElement;
  root.classList.toggle("dark", theme === "dark");
  root.dataset.theme = theme;
}

/**
 * يهيّئ اللغة/الثيم من كوكي واحة عند الإقلاع، ثم يبقى متزامناً حياً مع أي
 * `postMessage` لاحق من الـshell بلا إعادة تحميل — راجع ONBOARDING.md §9
 * الكامل. استدعِها مرة واحدة من أعلى تأثير في الشجرة (RootComponent)؛ ترجع
 * دالة تنظيف لإزالة المستمع عند الفكّ.
 *
 * الأمان: التحقّقان أدناه إلزاميان معاً — `event.origin` يمنع أي إطار/سكربت
 * آخر على نفس الأصل من انتحال رسالة تفضيلات (واحة وكل نظام مندمج يتشاركون
 * أصلاً واحداً خلف البوابة، فهذا فحص فعلي لا شكلي)، و`data.source`/`type`
 * يمنعان تعارضاً مع أي حركة `postMessage` أخرى غير متعلقة بهذا العقد.
 */
export function initWahaPrefsSync(): () => void {
  const cookiePrefs = readWahaPrefsCookie();
  if (cookiePrefs) {
    applyLocale(cookiePrefs.locale);
    applyTheme(cookiePrefs.theme);
  }

  const handleMessage = (event: MessageEvent): void => {
    if (event.origin !== window.location.origin) return;
    const data = event.data as { source?: unknown; type?: unknown; locale?: unknown; theme?: unknown } | null;
    if (!data || data.source !== "waha" || data.type !== "prefs") return;
    if (isValidLocale(data.locale)) applyLocale(data.locale);
    if (isValidTheme(data.theme)) applyTheme(data.theme);
  };

  window.addEventListener("message", handleMessage);
  return () => window.removeEventListener("message", handleMessage);
}
