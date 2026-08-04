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

    // TR-004: عدد عائلات الخط المستخدمة فعلياً في الصفحة
    const fontStacks = new Set();
    for (const e of document.querySelectorAll('h1,h2,h3,h4,h5,h6,p,a,button,span,li,label,input,td,th')) {
        const r = e.getBoundingClientRect();
        if (r.width <= 0 || r.height <= 0) continue;
        const ff = getComputedStyle(e).fontFamily;
        if (ff) fontStacks.add(ff.split(',')[0].trim().replace(/^["']|["']$/g, '').toLowerCase());
    }

    // NW-002: مسار تصفح (breadcrumbs) للصفحات العميقة
    const pathDepth = location.pathname.split('/').filter(Boolean).length;
    const hasBreadcrumb = !!document.querySelector(
        '[aria-label*="breadcrumb" i], nav[aria-label*="مسار" i], .breadcrumb, .breadcrumbs, [class*="breadcrumb" i]');

    // NW-003: تكرار شريط البحث
    const searchEls = new Set([
        ...document.querySelectorAll('input[type=search], input[role=searchbox], [role=search] input, form[role=search]'),
        ...[...document.querySelectorAll('input[type=text],input:not([type])')].filter((e) => {
            const t = ((e.placeholder || '') + ' ' + (e.name || '') + ' ' + (e.id || '')).toLowerCase();
            return t.includes('search') || t.includes('بحث');
        }),
    ]);

    // NW-004: ازدحام عناصر التنقل الرئيسي
    let navItemCount = 0;
    if (nav) {
        const list = nav.querySelector('ul, ol');
        navItemCount = list ? list.querySelectorAll(':scope > li').length : nav.querySelectorAll(':scope > a').length;
    }

    // IE-003: وجود قواعد CSS لحالتَي hover/focus في الصفحة (فحص على مستوى الصفحة ككل)
    let hasHoverOrFocusCSS = false;
    try {
        outer: for (const sheet of document.styleSheets) {
            let rules;
            try { rules = sheet.cssRules; } catch (e) { continue; }
            for (const rule of rules) {
                if (rule.selectorText && (rule.selectorText.includes(':hover') || rule.selectorText.includes(':focus'))) {
                    hasHoverOrFocusCSS = true; break outer;
                }
            }
        }
    } catch (e) {}

    // IE-004: وضوح العناصر المعطّلة (disabled)
    const disabledEls = [...document.querySelectorAll('button[disabled],input[disabled],select[disabled],textarea[disabled],[aria-disabled="true"]')]
        .filter((e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; });
    const unclearDisabled = disabledEls.filter((e) => {
        const cs = getComputedStyle(e);
        return parseFloat(cs.opacity) >= 0.9 && cs.cursor !== 'not-allowed';
    });
    const unclearDisabledSample = unclearDisabled.slice(0, 1).map((e) => box(e.getBoundingClientRect()));

    // FI-003: تلميحات صيغة الإدخال للحقول ذات الصيغة المقيّدة
    const constrainedInputs = [...document.querySelectorAll('input[type=password],input[pattern],input[type=tel],input[type=email]')]
        .filter((e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; });
    const noHintInputs = constrainedInputs.filter((e) => {
        const describedById = e.getAttribute('aria-describedby');
        const hasDescribedHint = describedById && document.getElementById(describedById);
        const nextText = e.nextElementSibling && (e.nextElementSibling.textContent || '').trim().length > 0;
        const placeholder = (e.placeholder || '').trim().length > 0;
        return !hasDescribedHint && !nextText && !placeholder;
    });
    const noHintSample = noHintInputs.slice(0, 1).map((e) => box(e.getBoundingClientRect()));

    // FI-004: نماذج طويلة بلا مؤشر تقدّم (ثقة منخفضة — تقدير على تحميل ثابت واحد)
    const longFormsNoProgress = [...document.querySelectorAll('form')].filter((f) => {
        if (f.querySelectorAll('input,select,textarea').length < 6) return false;
        return !f.querySelector('[role=progressbar],progress,[class*="step" i],[class*="progress" i]');
    });
    const longFormSample = longFormsNoProgress.slice(0, 1).map((f) => box(f.getBoundingClientRect()));

    // CD-003: تكدّس البطاقات/المكوّنات بلا ترقيم صفحات
    let maxCardGroup = 0, maxCardGroupBox = null;
    for (const c of document.querySelectorAll('div,ul,section')) {
        const kids = [...c.children];
        if (kids.length < 8) continue;
        const groups = {};
        for (const k of kids) {
            const key = k.tagName + '.' + (k.className || '').toString().trim().split(/\s+/).slice(0, 2).join('.');
            groups[key] = (groups[key] || 0) + 1;
        }
        const best = Math.max(0, ...Object.values(groups));
        if (best > maxCardGroup) { maxCardGroup = best; maxCardGroupBox = c.getBoundingClientRect(); }
    }
    const hasPagination = !!document.querySelector('[class*="pagination" i], nav[class*="pag" i], [aria-label*="page" i]');

    // A11-002: رابط تخطّي إلى المحتوى كأول عنصر قابل للتركيز
    const focusable = [...document.querySelectorAll('a[href],button,input,select,textarea,[tabindex]')]
        .filter((e) => e.tabIndex >= 0);
    const firstFocusableText = focusable[0] ? (focusable[0].innerText || focusable[0].textContent || '').trim().toLowerCase() : '';
    const skipKeywords = ['skip to', 'skip navigation', 'تخطي', 'انتقال إلى المحتوى', 'تجاوز'];
    const hasSkipLink = skipKeywords.some((k) => firstFocusableText.includes(k));

    // A11-003: أزرار أيقونة بلا اسم يمكن للتقنيات المساعدة قراءته
    const iconButtons = [...document.querySelectorAll('button,[role=button],a')].filter((e) => {
        const r = e.getBoundingClientRect();
        if (r.width <= 0 || r.height <= 0) return false;
        const text = (e.innerText || e.textContent || '').trim();
        return text.length === 0 && !!e.querySelector('svg,[class*="icon" i]');
    });
    const noAccessibleName = iconButtons.filter((e) => {
        const labelledbyId = e.getAttribute('aria-labelledby');
        return !e.getAttribute('aria-label') && !(labelledbyId && document.getElementById(labelledbyId)) && !e.getAttribute('title');
    });
    const noAccessibleNameSample = noAccessibleName.slice(0, 1).map((e) => box(e.getBoundingClientRect()));

    // A11-004: عناصر بترتيب تنقّل موجب (tabindex > 0) — نمط مضاد لترتيب التنقل الطبيعي
    const positiveTabindexEls = [...document.querySelectorAll('[tabindex]')]
        .filter((e) => parseInt(e.getAttribute('tabindex'), 10) > 0);
    const positiveTabindexSample = positiveTabindexEls.slice(0, 1).map((e) => box(e.getBoundingClientRect()));

    // CS-001: تجانس أنماط الأزرار
    const buttons = [...document.querySelectorAll('button,[role=button],input[type=submit],input[type=button]')]
        .filter((e) => { const r = e.getBoundingClientRect(); return r.width > 30 && r.height > 20; });
    const buttonSigs = new Set(buttons.map((e) => {
        const cs = getComputedStyle(e);
        return [cs.backgroundColor, cs.borderRadius, cs.borderWidth, cs.fontWeight].join('|');
    }));

    return {
        totalImages: imgs.length, missingAltCount: missingAlt.length, altSample,
        totalClickable: clickable.length, smallTargetsCount: smallTargets.length, smallSample,
        footerLinkCount: footerLinks.length, footerBox,
        totalInputs: inputs.length, unlabeledCount: unlabeled.length, unlabeledSample,
        nav: navResult,
        fontFamilyCount: fontStacks.size,
        pathDepth, hasBreadcrumb,
        searchInputCount: searchEls.size,
        navItemCount,
        totalInteractive: clickable.length, hasHoverOrFocusCSS,
        disabledCount: disabledEls.length, unclearDisabledCount: unclearDisabled.length, unclearDisabledSample,
        constrainedInputCount: constrainedInputs.length, noHintCount: noHintInputs.length, noHintSample,
        formCount: document.querySelectorAll('form').length,
        longFormsNoProgressCount: longFormsNoProgress.length, longFormSample,
        cardGroupMax: maxCardGroup, cardGroupBox: maxCardGroupBox ? box(maxCardGroupBox) : null, hasPagination,
        focusableCount: focusable.length, hasSkipLink,
        iconButtonCount: iconButtons.length, noAccessibleNameCount: noAccessibleName.length, noAccessibleNameSample,
        positiveTabindexCount: positiveTabindexEls.length, positiveTabindexSample,
        buttonCount: buttons.length, distinctButtonStyles: buttonSigs.size,
    };
}"""

# تُنفَّذ بعد إعادة ضبط حجم نافذة العرض إلى مقاس الجوال — بلا لقطة شاشة إضافية، فحص DOM فقط.
MOBILE_GATHER_JS = r"""() => {
    const docEl = document.documentElement;
    // RS-001: تمرير أفقي على الجوال
    const hasHorizontalOverflow = docEl.scrollWidth > docEl.clientWidth + 2;

    // RS-002: حجم نص غير مقروء على الجوال (صغير جداً أو كبير جداً)
    const textEls = [...document.querySelectorAll('p,span,a,li,label,button,h1,h2,h3,h4,h5,h6,div')]
        .filter((e) => e.children.length === 0 && (e.textContent || '').trim().length > 0);
    let tooSmall = 0, tooLarge = 0;
    for (const e of textEls) {
        const r = e.getBoundingClientRect();
        if (r.width <= 0 || r.height <= 0) continue;
        const fs = parseFloat(getComputedStyle(e).fontSize);
        if (fs < 12) tooSmall++;
        else if (fs > 40) tooLarge++;
    }

    return {
        hasHorizontalOverflow,
        totalTextEls: textEls.length, tooSmallCount: tooSmall, tooLargeCount: tooLarge,
    };
}"""


async def gather_ux_data(pg):
    """يُستدعى من داخل capture_page() بينما الصفحة ما زالت مفتوحة — نفس اللقطة، مسار كود مستقل."""
    return await pg.evaluate(GATHER_JS)


async def gather_ux_mobile_data(pg):
    """يُعيد ضبط حجم نافذة العرض لنفس الصفحة المفتوحة إلى مقاس الجوال ويجمع بيانات RS-001/RS-002 —
    بلا تنقّل جديد وبلا لقطة شاشة إضافية (لا يمس لقطة/شاشات DGA إطلاقاً)."""
    await pg.set_viewport_size({"width": 375, "height": 800})
    return await pg.evaluate(MOBILE_GATHER_JS)


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


CODE_RULE_IDS = [r["id"] for r in UX_RULES if r.get("detection") == "code"]


def run_ux_checks(ux_data: dict | None, W: int, H: int, mobile_data: dict | None = None) -> list[dict]:
    """يرجع قائمة نتائج بنفس شكل مخرجات DGA (id/category/status/title/description/
    recommendation/evidence/region) مع حقل source='UX' إضافي — بلا أي استدعاء لكود DGA.
    يُرجِع دائماً نتيجة لكل قاعدة كودية (20 قاعدة)، حتى لو كانت الحالة not_applicable/undetermined —
    لا تُحذف أي قاعدة من الناتج أبداً، حفاظاً على مبدأ عدم التخمين (لا نفترض pass لعنصر لم نقيّمه)."""
    out: list[dict] = []

    def add(rid: str, status: str, evidence: str | None = None, region: dict | None = None):
        r = RULE_BY_ID[rid]
        out.append({
            "id": r["id"], "category": r["category"], "status": status,
            "title": r["title"], "description": r["description"],
            "recommendation": r.get("recommendation"),
            "evidence": evidence,
            "region": region if status in ("fail", "warn") else None,
            "source": "UX",
        })

    def add_checked(rid: str, violated: bool, evidence: str | None = None, region: dict | None = None):
        add(rid, _status(rid, violated), evidence if violated else None, region)

    if not ux_data:
        for rid in CODE_RULE_IDS:
            add(rid, "undetermined", "تعذّر جمع بيانات الصفحة اللازمة لتقييم هذه القاعدة.")
        return out

    if ux_data["totalImages"] == 0:
        add("A11-001", "not_applicable", "لا توجد صور محتوى (أكبر من 40×40px) في الصفحة.")
    else:
        violated = ux_data["missingAltCount"] > 0
        region = region_from_box(ux_data["altSample"][0], W, H) if violated and ux_data["altSample"] else None
        evidence = f"{ux_data['missingAltCount']} من أصل {ux_data['totalImages']} صورة محتوى بلا نص بديل"
        add_checked("A11-001", violated, evidence, region)

    if ux_data["totalClickable"] == 0:
        add("IE-002", "not_applicable", "لا توجد عناصر تفاعلية (روابط/أزرار) في الصفحة.")
    else:
        violated = ux_data["smallTargetsCount"] > 0
        region = region_from_box(ux_data["smallSample"][0], W, H) if violated and ux_data["smallSample"] else None
        evidence = f"{ux_data['smallTargetsCount']} من أصل {ux_data['totalClickable']} عنصر تفاعلي أصغر من 44×44px"
        add_checked("IE-002", violated, evidence, region)

    if ux_data["footerLinkCount"] == 0:
        add("CD-001", "not_applicable", "لا يوجد فوتر يحتوي روابط في الصفحة.")
    else:
        violated = ux_data["footerLinkCount"] > 30
        region = region_from_box(ux_data["footerBox"], W, H) if violated and ux_data["footerBox"] else None
        evidence = f"{ux_data['footerLinkCount']} رابطاً في الفوتر"
        add_checked("CD-001", violated, evidence, region)

    if ux_data["totalInputs"] == 0:
        add("FI-001", "not_applicable", "لا توجد حقول إدخال ظاهرة في الصفحة.")
    else:
        violated = ux_data["unlabeledCount"] > 0
        region = region_from_box(ux_data["unlabeledSample"][0], W, H) if violated and ux_data["unlabeledSample"] else None
        evidence = f"{ux_data['unlabeledCount']} من أصل {ux_data['totalInputs']} حقل بلا تسمية مرتبطة"
        add_checked("FI-001", violated, evidence, region)

    if ux_data["nav"] is None:
        add("NW-001", "not_applicable", "لا يوجد عنصر تنقّل رئيسي (nav) في الصفحة.")
    elif ux_data["nav"]["matchingLinks"] == 0:
        add("NW-001", "not_applicable", "لا يوجد رابط في التنقل الرئيسي يطابق مسار الصفحة الحالية.")
    else:
        violated = not ux_data["nav"]["hasIndicator"]
        evidence = "لا يوجد aria-current أو صنف active على رابط الصفحة الحالية في التنقل"
        add_checked("NW-001", violated, evidence, None)

    if ux_data["fontFamilyCount"] == 0:
        add("TR-004", "not_applicable", "لا يوجد نص ظاهر في الصفحة لقياس عدد عائلات الخط.")
    else:
        violated = ux_data["fontFamilyCount"] > 3
        evidence = f"{ux_data['fontFamilyCount']} عائلات خط مختلفة مستخدمة في الصفحة"
        add_checked("TR-004", violated, evidence, None)

    if ux_data["pathDepth"] <= 2:
        add("NW-002", "not_applicable", f"عمق مسار الصفحة {ux_data['pathDepth']} ≤ 2 — مسار التصفح غير مطلوب لهذا العمق حسب تعريف القاعدة.")
    else:
        violated = not ux_data["hasBreadcrumb"]
        evidence = f"عمق الصفحة {ux_data['pathDepth']} مستويات بلا مسار تصفح"
        add_checked("NW-002", violated, evidence, None)

    violated = ux_data["searchInputCount"] > 1
    evidence = f"{ux_data['searchInputCount']} حقول بحث ظاهرة في نفس الوقت"
    add_checked("NW-003", violated, evidence, None)

    if ux_data["nav"] is None:
        add("NW-004", "not_applicable", "لا يوجد عنصر تنقّل رئيسي (nav) في الصفحة.")
    else:
        violated = ux_data["navItemCount"] > 9
        evidence = f"{ux_data['navItemCount']} عنصراً في التنقل الرئيسي"
        add_checked("NW-004", violated, evidence, None)

    if ux_data["totalInteractive"] == 0:
        add("IE-003", "not_applicable", "لا توجد عناصر تفاعلية في الصفحة.")
    else:
        violated = not ux_data["hasHoverOrFocusCSS"]
        evidence = "لا توجد قواعد CSS لحالتَي hover أو focus في الصفحة"
        add_checked("IE-003", violated, evidence, None)

    if ux_data["disabledCount"] == 0:
        add("IE-004", "not_applicable", "لا توجد عناصر معطّلة (disabled) في الصفحة.")
    else:
        violated = ux_data["unclearDisabledCount"] > 0
        region = region_from_box(ux_data["unclearDisabledSample"][0], W, H) if violated and ux_data["unclearDisabledSample"] else None
        evidence = f"{ux_data['unclearDisabledCount']} من أصل {ux_data['disabledCount']} عنصر معطّل غير مميّز بصرياً"
        add_checked("IE-004", violated, evidence, region)

    if ux_data["constrainedInputCount"] == 0:
        add("FI-003", "not_applicable", "لا توجد حقول بصيغة مقيّدة (كلمة مرور/بريد/هاتف/pattern) في الصفحة.")
    else:
        violated = ux_data["noHintCount"] > 0
        region = region_from_box(ux_data["noHintSample"][0], W, H) if violated and ux_data["noHintSample"] else None
        evidence = f"{ux_data['noHintCount']} من أصل {ux_data['constrainedInputCount']} حقل مقيّد الصيغة بلا تلميح"
        add_checked("FI-003", violated, evidence, region)

    if ux_data["formCount"] == 0:
        add("FI-004", "not_applicable", "لا توجد نماذج (form) في الصفحة.")
    else:
        violated = ux_data["longFormsNoProgressCount"] > 0
        region = region_from_box(ux_data["longFormSample"][0], W, H) if violated and ux_data["longFormSample"] else None
        evidence = f"{ux_data['longFormsNoProgressCount']} نموذج طويل بلا مؤشر تقدّم"
        add_checked("FI-004", violated, evidence, region)

    if ux_data["cardGroupMax"] == 0:
        add("CD-003", "not_applicable", "لم يُعثر على مجموعة عناصر متكررة (8 عناصر متشابهة فأكثر) كافية للتقييم.")
    else:
        violated = ux_data["cardGroupMax"] > 20 and not ux_data["hasPagination"]
        region = region_from_box(ux_data["cardGroupBox"], W, H) if violated and ux_data["cardGroupBox"] else None
        evidence = f"{ux_data['cardGroupMax']} عنصراً متكرراً بلا ترقيم صفحات"
        add_checked("CD-003", violated, evidence, region)

    if ux_data["focusableCount"] == 0:
        add("A11-002", "not_applicable", "لا توجد عناصر قابلة للتركيز في الصفحة.")
    else:
        violated = not ux_data["hasSkipLink"]
        evidence = "لا يوجد رابط تخطي إلى المحتوى كأول عنصر قابل للتركيز"
        add_checked("A11-002", violated, evidence, None)

    if ux_data["iconButtonCount"] == 0:
        add("A11-003", "not_applicable", "لا توجد أزرار تعتمد على أيقونة فقط بلا نص في الصفحة.")
    else:
        violated = ux_data["noAccessibleNameCount"] > 0
        region = region_from_box(ux_data["noAccessibleNameSample"][0], W, H) if violated and ux_data["noAccessibleNameSample"] else None
        evidence = f"{ux_data['noAccessibleNameCount']} من أصل {ux_data['iconButtonCount']} زر أيقونة بلا اسم يمكن قراءته"
        add_checked("A11-003", violated, evidence, region)

    violated = ux_data["positiveTabindexCount"] > 0
    region = region_from_box(ux_data["positiveTabindexSample"][0], W, H) if violated and ux_data["positiveTabindexSample"] else None
    evidence = f"{ux_data['positiveTabindexCount']} عنصر بترتيب تنقّل موجب (tabindex > 0)"
    add_checked("A11-004", violated, evidence, region)

    if ux_data["buttonCount"] < 5:
        add("CS-001", "not_applicable", f"عدد الأزرار في الصفحة ({ux_data['buttonCount']}) غير كافٍ لتقييم تجانس النمط (الحد الأدنى 5).")
    else:
        violated = ux_data["distinctButtonStyles"] >= 5
        evidence = f"{ux_data['distinctButtonStyles']} نمطاً بصرياً مختلفاً بين {ux_data['buttonCount']} زر"
        add_checked("CS-001", violated, evidence, None)

    if mobile_data is None:
        add("RS-001", "undetermined", "تعذّر جمع بيانات قياس الجوال لهذه الصفحة.")
        add("RS-002", "undetermined", "تعذّر جمع بيانات قياس الجوال لهذه الصفحة.")
    else:
        violated = mobile_data["hasHorizontalOverflow"]
        evidence = "المحتوى يتجاوز عرض شاشة الجوال ويسبب تمريراً أفقياً"
        add_checked("RS-001", violated, evidence, None)

        if mobile_data["totalTextEls"] == 0:
            add("RS-002", "not_applicable", "لا يوجد نص ظاهر على مقاس الجوال لقياسه.")
        else:
            violated = mobile_data["tooSmallCount"] > 0 or mobile_data["tooLargeCount"] > 0
            n = mobile_data["tooSmallCount"] + mobile_data["tooLargeCount"]
            evidence = f"{n} من أصل {mobile_data['totalTextEls']} عنصر نصي بحجم خط غير مقروء على الجوال"
            add_checked("RS-002", violated, evidence, None)

    return out
