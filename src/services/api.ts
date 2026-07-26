// Typed data service. Currently returns MOCK data.
// Replace implementations with fetch() calls to the FastAPI backend when ready.

export type Category =
  | "access"
  | "usab"
  | "content"
  | "identity"
  | "lang"
  | "perf"
  | "resp"
  | "sec";

export type Status = "pass" | "warn" | "fail";

export interface Rule {
  id: number;
  category: Category;
  status: Status;
  title: string;
  description: string;
  recommendation?: string;
  evidence?: string;
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
  access: "إمكانية الوصول",
  usab: "سهولة الاستخدام",
  content: "المحتوى",
  identity: "الهوية والتصميم",
  lang: "اللغة",
  perf: "الأداء",
  resp: "التوافق",
  sec: "الأمان",
};

function gradeFromScore(score: number): Audit["grade"] {
  if (score >= 90) return "A";
  if (score >= 75) return "B";
  if (score >= 60) return "C";
  return "D";
}

const MOCK_RULES: Omit<Rule, "status">[] = [
  { id: 1, category: "access", title: "توفير نص بديل للصور", description: "يجب أن تحتوي جميع الصور غير الزخرفية على نص بديل وصفي يعبّر عن محتواها لمستخدمي قارئات الشاشة.", recommendation: "أضف سمة alt وصفية لكل صورة معلوماتية، واستخدم alt=\"\" للصور الزخرفية.", evidence: "<img src=\"/hero.png\"> — missing alt attribute" },
  { id: 2, category: "access", title: "تباين لوني كافٍ للنصوص", description: "يجب ألا تقل نسبة التباين بين النص والخلفية عن 4.5:1 للنصوص العادية.", evidence: "color: #9CA3AF on #FFFFFF → contrast 2.8:1" },
  { id: 3, category: "access", title: "دعم التنقل عبر لوحة المفاتيح", description: "جميع العناصر التفاعلية يجب أن تكون قابلة للوصول والتشغيل عبر لوحة المفاتيح.", evidence: "3 interactive elements without tabindex" },
  { id: 4, category: "access", title: "استخدام العناوين الهيكلية بشكل صحيح", description: "استخدم عناصر H1-H6 بترتيب هرمي منطقي دون تخطي مستويات.", recommendation: "استخدم H1 واحدًا للصفحة ثم H2, H3 بترتيب." },
  { id: 5, category: "usab", title: "وضوح روابط التنقل الرئيسية", description: "يجب أن تكون قائمة التنقل الرئيسية ظاهرة وواضحة في جميع الصفحات." },
  { id: 6, category: "usab", title: "توفير خاصية البحث", description: "يجب توفير حقل بحث يمكن الوصول إليه من كل صفحة." },
  { id: 7, category: "usab", title: "مؤشرات التقدم في النماذج", description: "إظهار خطوات النموذج والخطوة الحالية للمستخدم.", recommendation: "أضف مؤشر خطوات بصري أعلى النماذج متعددة الصفحات." },
  { id: 8, category: "usab", title: "رسائل خطأ واضحة", description: "توفير رسائل خطأ مفهومة قرب الحقول ذات الصلة." },
  { id: 9, category: "content", title: "تحديث تاريخ آخر مراجعة", description: "إظهار تاريخ آخر تحديث للمحتوى في كل صفحة.", evidence: "no 'last-updated' metadata found" },
  { id: 10, category: "content", title: "توفير محتوى بلغة سهلة", description: "استخدام لغة عربية فصحى مبسطة يسهل فهمها للجمهور العام." },
  { id: 11, category: "content", title: "روابط تواصل واضحة", description: "توفير معلومات التواصل بشكل بارز في التذييل وصفحة اتصل بنا." },
  { id: 12, category: "identity", title: "استخدام الشعار الرسمي بشكل صحيح", description: "يجب استخدام شعار الجهة الرسمي بحجم ووضوح مناسبين في الرأس." },
  { id: 13, category: "identity", title: "التقيد بألوان الهوية البصرية", description: "الالتزام بالنظام اللوني المعتمد في دليل الهوية." },
  { id: 14, category: "identity", title: "أيقونات متناسقة", description: "استخدام مجموعة أيقونات موحدة عبر الموقع." },
  { id: 15, category: "lang", title: "دعم اللغة العربية والإنجليزية", description: "توفير محوّل لغة واضح ومحتوى مترجم بالكامل.", evidence: "language switcher missing on 3 pages" },
  { id: 16, category: "lang", title: "اتجاه الصفحة RTL صحيح", description: "ضبط dir=\"rtl\" على العنصر html وضمان اتجاه صحيح للعناصر.", evidence: "html[dir] attribute set to \"rtl\" ✓" },
  { id: 17, category: "lang", title: "تنسيق الأرقام والتواريخ", description: "استخدام تنسيق أرقام وتواريخ يتوافق مع المعيار السعودي." },
  { id: 18, category: "perf", title: "زمن التحميل الأولي (LCP)", description: "يجب أن يكتمل عرض المحتوى الرئيسي خلال 2.5 ثانية.", evidence: "LCP = 3.8s (target ≤ 2.5s)" },
  { id: 19, category: "perf", title: "تحسين حجم الصور", description: "استخدام صيغ حديثة (WebP/AVIF) وضغط مناسب.", recommendation: "حوّل الصور إلى WebP وقلّل الحجم بنسبة 60%.", evidence: "hero.png = 1.4MB" },
  { id: 20, category: "perf", title: "تفعيل التخزين المؤقت", description: "ضبط ترويسات Cache-Control على الأصول الثابتة." },
  { id: 21, category: "resp", title: "دعم أحجام الشاشات المختلفة", description: "الموقع يعمل بشكل صحيح على شاشات الجوال، اللوحي، والحاسب." },
  { id: 22, category: "resp", title: "دعم متصفحات متعددة", description: "التوافق مع Chrome, Safari, Firefox, Edge بأحدث إصدارين." },
  { id: 23, category: "resp", title: "دعم قارئات الشاشة", description: "التوافق مع NVDA و VoiceOver." },
  { id: 24, category: "sec", title: "استخدام بروتوكول HTTPS", description: "جميع صفحات الموقع يجب أن تُقدَّم عبر HTTPS.", evidence: "https:// enabled ✓ (HSTS max-age=31536000)" },
  { id: 25, category: "sec", title: "ترويسات أمان HTTP", description: "توفير Content-Security-Policy و X-Frame-Options.", recommendation: "أضف ترويسة CSP صارمة.", evidence: "Content-Security-Policy: missing" },
  { id: 26, category: "sec", title: "حماية النماذج من CSRF", description: "استخدام رموز CSRF في جميع النماذج الحساسة." },
  { id: 27, category: "sec", title: "سياسة خصوصية واضحة", description: "توفير صفحة سياسة خصوصية محدّثة يمكن الوصول إليها من التذييل." },
];

// Deterministic pseudo-random based on url string
function seededStatuses(url: string): Status[] {
  let h = 0;
  for (let i = 0; i < url.length; i++) h = (h * 31 + url.charCodeAt(i)) | 0;
  const rng = () => {
    h = (h * 1664525 + 1013904223) | 0;
    return ((h >>> 0) % 1000) / 1000;
  };
  return MOCK_RULES.map(() => {
    const r = rng();
    if (r < 0.62) return "pass";
    if (r < 0.85) return "warn";
    return "fail";
  });
}

function buildAudit(url: string): Audit {
  const statuses = seededStatuses(url);
  const rules: Rule[] = MOCK_RULES.map((r, i) => ({ ...r, status: statuses[i] }));
  const pass = rules.filter((r) => r.status === "pass").length;
  const warn = rules.filter((r) => r.status === "warn").length;
  const score = Math.round(((pass + warn * 0.5) / rules.length) * 100);
  const encoded = encodeURIComponent(url);
  const shot = (viewport: Screenshot["viewport"], w: number, h: number) =>
    `https://image.thum.io/get/width/${w}/crop/${h}/viewportWidth/${w}/${url}`;
  return {
    id: `aud_${Math.abs(url.split("").reduce((a, c) => a + c.charCodeAt(0), 0))}`,
    url,
    scannedAt: new Date().toISOString(),
    durationSec: 12,
    score,
    grade: gradeFromScore(score),
    rules,
    screenshots: [
      { label: "سطح المكتب", viewport: "desktop", url: shot("desktop", 1440, 900), width: 1440, height: 900 },
      { label: "اللوحي", viewport: "tablet", url: shot("tablet", 900, 1200), width: 900, height: 1200 },
      { label: "الجوال", viewport: "mobile", url: shot("mobile", 480, 900), width: 480, height: 900 },
    ],
  };
  void encoded;
}

const RECENT: { url: string; scannedAt: string; score: number }[] = [
  { url: "https://mewa.gov.sa", scannedAt: "2026-07-24T09:12:00Z", score: 82 },
  { url: "https://my.gov.sa", scannedAt: "2026-07-22T14:45:00Z", score: 91 },
  { url: "https://dga.gov.sa", scannedAt: "2026-07-20T11:03:00Z", score: 76 },
  { url: "https://absher.sa", scannedAt: "2026-07-18T08:30:00Z", score: 68 },
];

export async function startAudit(url: string): Promise<string> {
  // Simulate scanning latency; real impl will POST /audits
  await new Promise((r) => setTimeout(r, 400));
  return buildAudit(url).id;
}

export async function getAudit(url: string): Promise<Audit> {
  await new Promise((r) => setTimeout(r, 200));
  return buildAudit(url);
}

export async function getRecentAudits() {
  await new Promise((r) => setTimeout(r, 100));
  return RECENT;
}
