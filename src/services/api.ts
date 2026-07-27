// Typed data service.
// getAudit() calls the local FastAPI audit engine in audit-service/ (Playwright + Gemini,
// real DGA rule detection). startAudit()/getRecentAudits() stay as lightweight UI helpers.

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

export type Status = "pass" | "warn" | "fail";

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
  recommendation?: string;
  evidence?: string;
  region?: Region; // مكان المخالفة على لقطة سطح المكتب (نِسَب مئوية)
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
  score: number; // 0-100
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

const AUDIT_SERVICE_URL = "http://localhost:8000";

// The real audit takes 1-2 minutes (Playwright capture + Gemini visual scan).
// "/scanning" triggers the real call and "/results" re-requests the same url —
// caching here means results.tsx picks up the already-finished audit instantly
// instead of running the whole pipeline a second time.
const auditCache = new Map<string, Promise<Audit>>();

export async function startAudit(url: string): Promise<string> {
  // UI-only latency simulation for the "/scanning" transition screen.
  await new Promise((r) => setTimeout(r, 400));
  return `aud_${Math.abs(url.split("").reduce((a, c) => a + c.charCodeAt(0), 0))}`;
}

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

const RECENT: { url: string; scannedAt: string; score: number }[] = [
  { url: "https://mewa.gov.sa", scannedAt: "2026-07-24T09:12:00Z", score: 82 },
  { url: "https://my.gov.sa", scannedAt: "2026-07-22T14:45:00Z", score: 91 },
  { url: "https://dga.gov.sa", scannedAt: "2026-07-20T11:03:00Z", score: 76 },
  { url: "https://absher.sa", scannedAt: "2026-07-18T08:30:00Z", score: 68 },
];

export async function getRecentAudits() {
  await new Promise((r) => setTimeout(r, 100));
  return RECENT;
}
