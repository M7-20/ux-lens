// Typed data service.
// getAudit() calls the local FastAPI audit engine in audit-service/ (Playwright + Gemini,
// real DGA rule detection). getRecentAudits()/getStats() stay as lightweight UI helpers.

export type Category =
  | "Typography"
  | "Colors"
  | "Spacing"
  | "Radius"
  | "Shadows"
  | "Grid & Layout"
  | "RTL & Localization"
  | "Template Compliance"
  | "Accessibility";

export type Status = "pass" | "warn" | "fail" | "manual_review";

export interface Region {
  x: number;      // نسبة مئوية من عرض الصورة (0-100)
  y: number;      // نسبة مئوية من ارتفاع الصورة (0-100)
  width: number;  // نسبة مئوية
  height: number; // نسبة مئوية
}

export interface Rule {
  id: string;
  category: Category;
  status: Status;
  title: string;
  description: string;
  titlePass?: string; // صياغة إيجابية للعنوان تُستخدم عند status="pass" (إن توفرت من المحرك)
  descriptionPass?: string;
  recommendation?: string;
  evidence?: string;
  region?: Region; // مكان المخالفة على لقطة سطح المكتب (نِسَب مئوية)
  checkedLocations?: number | null; // إجمالي المواضع المفحوصة لهذه القاعدة (إن كانت مقيسة كوديًا)
  passedLocations?: number | null; // عدد المواضع الملتزمة من إجمالي المواضع المفحوصة
}

export interface Screenshot {
  label: string; // e.g. "سطح المكتب", "الجوال"
  viewport: "desktop" | "tablet" | "mobile";
  url: string; // image URL
  width: number;
  height: number;
}

export interface Audit {
  id: string;
  url: string;
  scannedAt: string; // ISO
  durationSec: number;
  score: number; // 0-100 — النسبة المؤكّدة (CSS/DOM + بصري بثقة عالية)
  scoreEstimated: number; // 0-100 — شاملاً كل التقديرات البصرية
  grade: "A" | "B" | "C" | "D";
  rules: Rule[];
  screenshots: Screenshot[];
}

export const CATEGORY_LABELS: Record<Category, string> = {
  "Typography": "الطباعة",
  "Colors": "الألوان",
  "Spacing": "المسافات",
  "Radius": "الزوايا",
  "Shadows": "الظلال",
  "Grid & Layout": "الشبكة والتخطيط",
  "RTL & Localization": "اتجاه RTL",
  "Template Compliance": "التزام القالب",
  "Accessibility": "إمكانية الوصول",
};

const AUDIT_SERVICE_URL = import.meta.env.VITE_AUDIT_SERVICE_URL ?? "http://localhost:8000";

// The real audit takes 1-2 minutes (Playwright capture + Gemini visual scan).
// "/scanning" triggers the real call and "/results" re-requests the same url —
// caching here means results.tsx picks up the already-finished audit instantly
// instead of running the whole pipeline a second time.
const auditCache = new Map<string, Promise<Audit>>();

async function fetchAudit(url: string): Promise<Audit> {
  const res = await fetch(`${AUDIT_SERVICE_URL}/audit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? `فشل الاتصال بخدمة التدقيق (${res.status})`);
  }
  const audit = (await res.json()) as Audit;
  return {
    ...audit,
    screenshots: audit.screenshots.map((s) => ({ ...s, url: `${AUDIT_SERVICE_URL}${s.url}` })),
  };
}

export function getAudit(url: string): Promise<Audit> {
  let pending = auditCache.get(url);
  if (!pending) {
    pending = fetchAudit(url);
    auditCache.set(url, pending);
    pending.catch(() => auditCache.delete(url)); // don't cache failures
  }
  return pending;
}

export interface RecentAudit {
  url: string;
  scannedAt: string;
  score: number;
}

export async function getRecentAudits(limit = 10): Promise<RecentAudit[]> {
  const res = await fetch(`${AUDIT_SERVICE_URL}/audits/recent?limit=${limit}`);
  if (!res.ok) return [];
  return res.json();
}

export interface Stats {
  totalAudits: number;
  avgDurationSec: number;
  avgScore: number;
}

export async function getStats(): Promise<Stats> {
  const res = await fetch(`${AUDIT_SERVICE_URL}/stats`);
  if (!res.ok) return { totalAudits: 0, avgDurationSec: 0, avgScore: 0 };
  return res.json();
}
