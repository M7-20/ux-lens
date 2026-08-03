# طبقة قواعد UX العامة — معزولة تماماً عن محرك DGA (engine.py). لا شيء هنا يستورد من
# engine.py، ولا شيء في engine.py يستورد من هنا إلا عبر النقاط المعلَّمة "UX layer hook"
# خلف راية ENABLE_UX_LAYER. حذف هذا المجلد بالكامل + تعطيل الراية لا يؤثر على DGA إطلاقاً.
import json
from pathlib import Path

RULES_PATH = Path(__file__).parent / "ux-rules.json"
UX_RULES = json.load(open(RULES_PATH, encoding="utf-8"))["rules"]
RULE_BY_ID = {r["id"]: r for r in UX_RULES}

WEIGHT = {"Error": 3, "Warning": 2, "Info": 1}

# تُنفَّذ داخل الصفحة المفتوحة نفسها التي تلتقط لها DGA لقطته — بيانات مستقلة تماماً
# عن بيانات DGA (لا تُقرأ فيها ولا تُكتب إليها).
GATHER_JS = r"""() => {
    const box = (r) => ({x: r.x + scrollX, y: r.y + scrollY, w: r.width, h: r.height});

    // A11-001: صور محتوى بلا alt (نتجاهل الصور الصغيرة جداً — غالباً زخرفية/أيقونات)
    const imgs = [...document.images].filter(i => i.complete && i.naturalWidth > 40 && i.naturalHeight > 40);
    const missingAlt = imgs.filter(i => !i.alt || !i.alt.trim());
    const altSample = missingAlt.slice(0, 1).map(i => ({
        ...box(i.getBoundingClientRect()), src: (i.currentSrc || i.src || "").slice(0, 80),
    }));

    // IE-002: عناصر تفاعلية أصغر من 44x44px
    const clickable = [...document.querySelectorAll("a,button,[role=button],input[type=submit],input[type=button]")]
        .filter((e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; });
    const smallTargets = clickable.filter((e) => { const r = e.getBoundingClientRect(); return r.width < 44 || r.height < 44; });
    const smallSample = smallTargets.slice(0, 1).map((e) => ({
        ...box(e.getBoundingClientRect()), text: (e.innerText || e.value || "").trim().slice(0, 30),
    }));

    // CD-001: كثافة روابط الفوتر
    const footer = document.querySelector("footer");
    const footerLinks = footer ? [...footer.querySelectorAll("a")] : [];
    const footerBox = footer ? box(footer.getBoundingClientRect()) : null;

    // FI-001: حقول بلا تسمية مرتبطة (label[for] أو تغليف label أو aria-label/aria-labelledby)
    const inputs = [...document.querySelectorAll("input,select,textarea")]
        .filter((e) => !["hidden", "submit", "button", "checkbox", "radio"].includes(e.type))
        .filter((e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; });
    const unlabeled = inputs.filter((e) => {
        const hasFor = e.id && document.querySelector(`label[for="${CSS.escape(e.id)}"]`);
        const wrapped = e.closest("label");
        const ariaLabel = e.getAttribute("aria-label");
        const labelledbyId = e.getAttribute("aria-labelledby");
        const ariaLabelledby = labelledbyId && document.getElementById(labelledbyId);
        return !hasFor && !wrapped && !ariaLabel && !ariaLabelledby;
    });
    const unlabeledSample = unlabeled.slice(0, 1).map((e) => ({
        ...box(e.getBoundingClientRect()), placeholder: (e.placeholder || "").slice(0, 30),
    }));

    // NW-001: مؤشر الموقع الحالي في التنقل الرئيسي
    const nav = document.querySelector("nav");
    let navResult = null;
    if (nav) {
        const links = [...nav.querySelectorAll("a[href]")];
        const here = location.pathname.replace(/\/+$/, "") || "/";
        const matching = links.filter((a) => {
            try { const u = new URL(a.href, location.href); return (u.pathname.replace(/\/+$/, "") || "/") === here; }
            catch (e) { return false; }
        });
        const hasIndicator = matching.some((a) => a.matches('[aria-current], .active, [class*="active"]'));
        navResult = { matchingLinks: matching.length, hasIndicator };
    }

    return {
        totalImages: imgs.length, missingAltCount: missingAlt.length, altSample,
        totalClickable: clickable.length, smallTargetsCount: smallTargets.length, smallSample,
        footerLinkCount: footerLinks.length, footerBox,
        totalInputs: inputs.length, unlabeledCount: unlabeled.length, unlabeledSample,
        nav: navResult,
    };
}"""


async def gather_ux_data(pg):
    """يُستدعى من داخل capture_page() بينما الصفحة ما زالت مفتوحة — نفس اللقطة، مسار كود مستقل."""
    return await pg.evaluate(GATHER_JS)


def region_from_box(box, W, H):
    return {
        "x": round(box["x"] / W * 100, 2),
        "y": round(box["y"] / H * 100, 2),
        "width": round(box["w"] / W * 100, 2),
        "height": round(box["h"] / H * 100, 2),
    }


def _status(rule_id: str, violated: bool) -> str:
    if not violated:
        return "pass"
    return "fail" if RULE_BY_ID[rule_id]["severity"] == "Error" else "warn"


def run_ux_checks(ux_data: dict | None, W: int, H: int) -> list[dict]:
    """يرجع قائمة نتائج بنفس شكل مخرجات DGA (id/category/status/title/description/
    recommendation/evidence/region) مع حقل source='UX' إضافي — بلا أي استدعاء لكود DGA."""
    if not ux_data:
        return []

    out: list[dict] = []

    def add(rid: str, violated: bool, evidence: str | None = None, region: dict | None = None):
        r = RULE_BY_ID[rid]
        out.append({
            "id": r["id"], "category": r["category"], "status": _status(rid, violated),
            "title": r["title"], "description": r["description"],
            "recommendation": r.get("recommendation"),
            "evidence": evidence if violated else None,
            "region": region if violated else None,
            "source": "UX",
        })

    if ux_data["totalImages"] > 0:
        violated = ux_data["missingAltCount"] > 0
        region = region_from_box(ux_data["altSample"][0], W, H) if violated and ux_data["altSample"] else None
        evidence = f"{ux_data['missingAltCount']} من أصل {ux_data['totalImages']} صورة محتوى بلا نص بديل" if violated else None
        add("A11-001", violated, evidence, region)

    if ux_data["totalClickable"] > 0:
        violated = ux_data["smallTargetsCount"] > 0
        region = region_from_box(ux_data["smallSample"][0], W, H) if violated and ux_data["smallSample"] else None
        evidence = f"{ux_data['smallTargetsCount']} من أصل {ux_data['totalClickable']} عنصر تفاعلي أصغر من 44×44px" if violated else None
        add("IE-002", violated, evidence, region)

    if ux_data["footerLinkCount"] > 0:
        violated = ux_data["footerLinkCount"] > 30
        region = region_from_box(ux_data["footerBox"], W, H) if violated and ux_data["footerBox"] else None
        evidence = f"{ux_data['footerLinkCount']} رابطاً في الفوتر" if violated else None
        add("CD-001", violated, evidence, region)

    if ux_data["totalInputs"] > 0:
        violated = ux_data["unlabeledCount"] > 0
        region = region_from_box(ux_data["unlabeledSample"][0], W, H) if violated and ux_data["unlabeledSample"] else None
        evidence = f"{ux_data['unlabeledCount']} من أصل {ux_data['totalInputs']} حقل بلا تسمية مرتبطة" if violated else None
        add("FI-001", violated, evidence, region)

    if ux_data["nav"] and ux_data["nav"]["matchingLinks"] > 0:
        violated = not ux_data["nav"]["hasIndicator"]
        evidence = "لا يوجد aria-current أو صنف active على رابط الصفحة الحالية في التنقل" if violated else None
        add("NW-001", violated, evidence, None)

    return out
