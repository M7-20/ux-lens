# ============================================================
#  UX Lens — محرك تدقيق DGA (نسخة خدمة v3.8، بدون Colab)
#  من CSS/DOM (يقين): الخط · الزوايا · المسافات · الألوان التفاعلية ·
#    تباين النص (WCAG) · تتبّع العناوين · عرض الفقرات · أحجام الخط ·
#    التدرجات · تباين حقول الإدخال · RTL · شريط الحالة
#  من الصورة (مزوّد رؤية قابل للتبديل — Gemini أو بوابة الوزارة، راجع
#    vision_provider.py): بقية القواعد، بمستوى ثقة ودليل
# ============================================================
import asyncio
import hashlib
import json
import logging
import re
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from PIL import Image
from playwright.async_api import async_playwright
from pydantic import BaseModel

import vision_provider
from vision_provider import VisionProvider

logger = logging.getLogger("uxlens")
logger.setLevel(logging.INFO)
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s [%(name)s] %(message)s", "%H:%M:%S"))
    logger.addHandler(_handler)
    logger.propagate = False

BASE_DIR = Path(__file__).parent
SHOTS_DIR = BASE_DIR / "shots"
DATA_DIR = BASE_DIR / "data"
CACHE_PATH = DATA_DIR / "site_cache.json"
SHOTS_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

APPROVED_FONT = "IBM Plex Sans Arabic"
TILE_HEIGHT = 1600
OVERLAP = 200
DEDUP_IOU = 0.5      # عتبة اعتبار إطارين "نفس المخالفة"
IMG_OVERLAP = 0.7    # نسبة وقوع المخالفة داخل صورة محتوى لاستبعادها
MAX_TILES = 4        # سقف الشرائح — يضمن بقاء التحليل ضمن الوقت
MODEL = vision_provider.cache_key_id()  # لتوقيع الكاش فقط — الموديل الفعلي يقرره VisionProvider (VISION_PROVIDER)

with open(BASE_DIR / "dga" / "dga-rules.json", encoding="utf-8") as f:
    DGA = json.load(f)
with open(BASE_DIR / "dga" / "dga-tokens.json", encoding="utf-8") as f:
    TOKENS = json.load(f)

RULE = {r["id"]: r for r in DGA["rules"]}
CODE_CHECKED = {"DGA-TYP-001", "DGA-RAD-001", "DGA-SPC-001", "DGA-TPL-001",
                "DGA-CLR-001", "DGA-ACC-001", "DGA-TYP-005", "DGA-SPC-004",
                "DGA-TYP-002", "DGA-CLR-004", "DGA-ACC-002", "DGA-RTL-002"}
VISUAL_RULES = [r for r in DGA["rules"] if r["id"] not in CODE_CHECKED]
# قواعد العناصر العامة (هيدر/شريط حالة/قالب): تُقيَّم في شريحتها الأولى فقط
GLOBAL_TOP = {r["id"] for r in DGA["rules"]
              if any(k in (r.get("title", "") + r.get("category", "")).lower()
                     for k in ("header", "status bar", "template"))}

RADIUS_TOKEN = {float(v): k for k, v in TOKENS["radius"].items()}
ALLOWED_RADIUS = sorted(RADIUS_TOKEN)

# ============================================================
#  طبقة UX العامة — معزولة بالكامل في ux/، لا تلمس منطق DGA أعلاه.
#  مفعّلة دائماً (2026-08-04) بعد اكتمال الـ27 قاعدة واختبارها حياً على naama.sa.
#  تعطيلها مؤقتاً: أعد القيمة لـFalse (ملفات ux/ لا تُحذف، ترجع النتيجة لـ27 DGA فقط).
#  حذفها نهائياً: احذف مجلد ux/ بالكامل + هذا السطر + نقطتَي "UX layer hook" أدناه
#  (داخل capture_page وrun_audit) — لا أثر آخر على أي مكان في هذا الملف.
# ============================================================
ENABLE_UX_LAYER = True
BASE_UNIT = int(TOKENS["spacing"].get("base_unit", 4))
SPC_EXTRA = {2.0, 6.0}
ALLOWED_FS = sorted({d["size_px"] for d in TOKENS["typography"]["scale"].values()})
TRACK_MIN = min((d["size_px"] for d in TOKENS["typography"]["scale"].values()
                 if str(d.get("tracking", "0")).startswith("-")), default=36)
ACC_REQ = TOKENS.get("accessibility", {}).get("contrast_requirements", {
    "small_text_min_ratio": 4.5, "large_text_min_ratio": 3.0,
    "large_text_threshold_px": 24, "ui_components_min_ratio": 3.0,
})
GRAD_PAIRS = [tuple(tuple(int(g[k][i:i + 2], 16) for i in (1, 3, 5)) for k in ("from", "to"))
              for g in TOKENS["colors"].get("gradients", [])]
prop_ar = lambda p: re.sub(r"([A-Z])", r"-\1", p).lower()

COLOR_TOL = 10  # أقصى فرق مقبول لكل قناة لونية


def _hexes(node, path=""):
    if isinstance(node, dict):
        for k, v in node.items():
            yield from _hexes(v, k if not path else f"{path}-{k}")
    elif isinstance(node, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", node.strip()):
        yield path, node.strip().upper()


PALETTE = {}
for _name, _hx in _hexes(TOKENS["colors"]):
    PALETTE[tuple(int(_hx[i:i + 2], 16) for i in (1, 3, 5))] = _name
PALETTE.setdefault((255, 255, 255), "white")
PALETTE.setdefault((0, 0, 0), "black")


def nearest_token(rgb):
    p = min(PALETTE, key=lambda k: sum((a - b) ** 2 for a, b in zip(k, rgb)))
    return f"{PALETTE[p]} (#%02X%02X%02X)" % p


def safe_name(url: str) -> str:
    p = urlparse(url)
    host = re.sub(r"[^A-Za-z0-9-]+", "_", p.netloc.replace("www.", ""))[:30]
    path = re.sub(r"[^A-Za-z0-9_-]+", "_", p.path.strip("/") or "home")[:40]
    name = f"{host}__{path}"
    if p.query:
        keys = "_".join(sorted({q.split("=")[0] for q in p.query.split("&") if q}))
        name += f"__{re.sub(r'[^A-Za-z0-9_-]+', '', keys)[:20]}_{hashlib.md5(p.query.encode()).hexdigest()[:6]}"
    return name


def save_cache(cache: dict) -> None:
    tmp = CACHE_PATH.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)
    tmp.replace(CACHE_PATH)


# ============ 1) التقاط الصفحة ============
async def capture_page(url: str) -> dict:
    name = safe_name(url)
    shot = str(SHOTS_DIR / f"raw_{name}.png")
    ux_data = None
    ux_mobile_data = None
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--no-sandbox"])
        pg = await b.new_page(viewport={"width": 1440, "height": 900})
        try:
            await pg.goto(url, wait_until="domcontentloaded", timeout=75000)

            await pg.add_style_tag(content="""*,*::before,*::after{
                animation:none!important; transition:none!important;
                animation-play-state:paused!important; scroll-behavior:auto!important}""")
            await pg.wait_for_timeout(1500)

            await pg.evaluate("""() => {
                const words = ['موافقة','أوافق','اوافق','قبول','accept','agree','allow'];
                for (const e of document.querySelectorAll('button,a,[role=button],input[type=button],input[type=submit]')) {
                    const t = ((e.innerText||e.value||'') + ' ' + e.id + ' ' + e.className).toLowerCase();
                    const r = e.getBoundingClientRect();
                    if (words.some(w => t.includes(w)) && r.width > 0 && r.height > 0) { e.click(); break; }
                }
                const kw = ['cookie','الارتباط','الكوكيز','consent'];
                for (const e of document.querySelectorAll('div,section,aside')) {
                    const t = ((e.textContent||'').slice(0,300) + ' ' + e.id + ' ' + e.className).toLowerCase();
                    if (!kw.some(k => t.includes(k))) continue;
                    const pos = getComputedStyle(e).position;
                    if (pos === 'fixed' || pos === 'sticky') e.style.display = 'none';
                }
                document.querySelectorAll('img').forEach(i => {
                    i.loading = 'eager';
                    for (const a of ['data-src','data-original','data-lazy-src']) {
                        const u = i.getAttribute(a);
                        if (u && !i.src.endsWith(u)) i.src = u;
                    }
                });
            }""")

            await pg.evaluate("""async () => {
                await new Promise(r => { let t=0; const s=700;
                    const i=setInterval(()=>{ window.scrollBy(0,s); t+=s;
                        if(t>=document.body.scrollHeight){clearInterval(i);window.scrollTo(0,0);r();}},120); });
            }""")
            await pg.wait_for_timeout(1200)
            try:
                await pg.wait_for_function(
                    "() => [...document.images].every(i => i.complete && i.naturalWidth > 0)", timeout=5000)
            except Exception:
                pass
            try:
                await pg.wait_for_function("() => document.fonts.status === 'loaded'", timeout=5000)
            except Exception:
                pass

            broken = await pg.evaluate("""() => [...document.images]
                .filter(i => !i.complete || !i.naturalWidth)
                .map(i => { const r = i.getBoundingClientRect();
                            return {src:i.currentSrc||i.src||'', alt:(i.alt||'').slice(0,60),
                                    x:r.x+scrollX, y:r.y+scrollY, w:r.width, h:r.height}; })
                .filter(o => o.w > 20 && o.h > 20)""")

            # صور المحتوى (فوتوغرافية/إعلامية): مرجع لاستبعاد مخالفات الألوان فوقها
            imgs = await pg.evaluate("""() => [...document.images]
                .filter(i => i.complete && i.naturalWidth)
                .map(i => { const r = i.getBoundingClientRect();
                            return {x:r.x+scrollX, y:r.y+scrollY, w:r.width, h:r.height}; })
                .filter(o => o.w >= 48 && o.h >= 48)""")

            # شريط الحالة الحكومي من الـ DOM — يقين بدل تقدير بصري
            statusbar = await pg.evaluate("""() => {
                const norm = s => s.replace(/[\\u064B-\\u0652\\u0640]/g, '').replace(/\\s+/g, ' ');
                let top = '';
                const walk = (root) => {
                    let els;
                    try { els = root.querySelectorAll('*'); } catch(e) { return; }
                    for (const e of els) {
                        if (e.shadowRoot) walk(e.shadowRoot);
                        if (e.tagName === 'IFRAME') {
                            try { if (e.contentDocument) walk(e.contentDocument); } catch(x) {}
                            continue;
                        }
                        let r;
                        try { r = e.getBoundingClientRect(); } catch(x) { continue; }
                        if (r.width <= 0 || r.height <= 0) continue;
                        if (r.y + scrollY >= 400) continue;
                        for (const n of e.childNodes)
                            if (n.nodeType === 3) top += n.textContent + ' ';
                    }
                };
                walk(document);
                top = norm(top).toLowerCase();
                const kw = ['موقع حكومي رسمي','موقع حكومي مسجل','هيئة الحكومة الرقمية',
                            'official saudi government','registered with the digital government'];
                const hit = kw.find(k => top.includes(norm(k).toLowerCase()));
                return hit ? {found:true, text:hit} : {found:false, sample:top.slice(0, 120)};
            }""")

            # ألوان خلفيات العناصر التفاعلية — تُقارن لاحقاً بباليتة DGA
            colors = await pg.evaluate("""() => {
                const out = [];
                for (const e of document.querySelectorAll("button,[role=button],input[type=submit],input[type=button],a")) {
                    const r = e.getBoundingClientRect();
                    if (r.width < 20 || r.height < 12) continue;
                    const cs = getComputedStyle(e);
                    const m = (cs.backgroundColor||'').match(/rgba?\\(([\\d.]+),\\s*([\\d.]+),\\s*([\\d.]+)(?:,\\s*([\\d.]+))?\\)/);
                    if (!m) continue;
                    const a = m[4] === undefined ? 1 : parseFloat(m[4]);
                    if (a < 0.99) continue;
                    out.push({x:r.x+scrollX, y:r.y+scrollY, w:r.width, h:r.height,
                              rgb:[+m[1],+m[2],+m[3]].map(Math.round),
                              text:((e.innerText||e.value||'').trim()).slice(0,30)});
                }
                return out;
            }""")

            # حقن CSS أعلاه يوقف animation/transition لكن لا يوقف الحركة المدفوعة بمؤقّتات JS
            # (كاروسيل Swiper وأمثاله يستخدمون setInterval/setTimeout لجدولة autoplay) — هذا عام
            # ويعمل على أي موقع، ليس Swiper فقط، لأنه يعطّل كل المؤقّتات النشطة مباشرة.
            await pg.evaluate("""() => {
                document.querySelectorAll('.swiper').forEach(el => {
                    try { el.swiper?.autoplay?.stop(); } catch(e) {}
                });
                const maxId = setTimeout(() => {}, 0);
                for (let id = maxId; id >= 0; id--) { clearTimeout(id); clearInterval(id); }
                document.querySelectorAll('video').forEach(v => { try { v.pause(); } catch(e) {} });
            }""")
            await pg.wait_for_timeout(500)

            # مكوّنات كاروسيل مخصّصة (بلا Swiper ولا مؤقّتات) قد تتحرك عبر requestAnimationFrame
            # بدل setInterval — وهذا لا يوقفه أي مما سبق. نؤجّل تعطيله لآخر لحظة قبل الالتقاط
            # مباشرة (بعد كل الانتظارات أعلاه) حتى نعطي أي استخدام مشروع لـrAF (رسم تدريجي،
            # تحميل محتوى) فرصة كاملة لينهي عمله أولاً، فلا نجمّد إلا الإطار الأخير المستقر.
            # نُبدّل requestAnimationFrame بدالة فارغة أيضاً حتى لا تعيد أي حلقة ذاتية الجدولة
            # (نمط tick() { ...; requestAnimationFrame(tick); }) جدولة نفسها بعد الإلغاء مباشرة.
            await pg.evaluate("""() => {
                const maxRAF = requestAnimationFrame(() => {});
                for (let id = maxRAF; id >= 0; id--) { cancelAnimationFrame(id); }
                window.requestAnimationFrame = () => 0;
            }""")

            with open(shot, "wb") as f:
                f.write(await pg.screenshot(full_page=True))

            m = await pg.evaluate("""() => {
                const FONT = new Set(['h1','h2','h3','h4','p','a','button','span','li','label','input']);
                const BOX  = new Set(['button','a','input','select','textarea','div','section','article','li','img']);
                const SPC  = new Set(['button','a','input','select','textarea','section','article','li',
                                      'header','footer','nav','div','p','h1','h2','h3','ul','form']);
                const PROPS=['paddingTop','paddingRight','paddingBottom','paddingLeft',
                             'marginTop','marginRight','marginBottom','marginLeft','rowGap','columnGap'];
                const GENERIC = new Set(['serif','sans-serif','monospace','cursive','fantasy',
                                         'system-ui','ui-sans-serif','ui-serif','ui-monospace','ui-rounded']);
                const rcache = {};
                const renderedFont = (stack) => {
                    if (rcache[stack] !== undefined) return rcache[stack];
                    const fams = stack.split(',').map(s => s.trim().replace(/^["']|["']$/g, ''));
                    let out = fams[fams.length-1] || '';
                    for (const f of fams) {
                        if (GENERIC.has(f.toLowerCase())) { out = f; break; }
                        try { if (document.fonts.check(`12px "${f}"`)) { out = f; break; } } catch(e) {}
                    }
                    rcache[stack] = out; return out;
                };
                const parseC = s => {
                    const m = (s||'').match(/rgba?\\(([\\d.]+),\\s*([\\d.]+),\\s*([\\d.]+)(?:,\\s*([\\d.]+))?\\)/);
                    return m ? [+m[1], +m[2], +m[3], m[4] === undefined ? 1 : +m[4]] : null;
                };
                const effBg = (e) => {
                    const layers = [];
                    for (let p = e; p && p !== document.documentElement; p = p.parentElement) {
                        const s = getComputedStyle(p);
                        if (s.backgroundImage && s.backgroundImage !== 'none') return {v:false};
                        const c = parseC(s.backgroundColor);
                        if (c && c[3] > 0) { layers.push(c); if (c[3] >= 1) break; }
                    }
                    let r = 255, g = 255, b = 255;
                    for (const [cr,cg,cb,ca] of layers.reverse()) {
                        r = cr*ca + r*(1-ca); g = cg*ca + g*(1-ca); b = cb*ca + b*(1-ca);
                    }
                    return {v:true, c:[Math.round(r), Math.round(g), Math.round(b)]};
                };
                const fonts=[], radii=[], spacing=[], paras=[];
                for (const e of document.body.getElementsByTagName('*')) {
                    const tag = e.tagName.toLowerCase();
                    const inF = FONT.has(tag), inB = BOX.has(tag), inS = SPC.has(tag);
                    if (!inF && !inB && !inS) continue;
                    const r = e.getBoundingClientRect();
                    if (r.width <= 0 || r.height <= 0) continue;
                    const cs = getComputedStyle(e);
                    const base = {x:r.x+scrollX, y:r.y+scrollY, w:r.width, h:r.height};
                    if (tag === 'p') {
                        const full = (e.textContent||'').trim();
                        if (full.length >= 80) paras.push({...base});
                    }

                    if (inF) {
                        let direct = '';
                        for (const n of e.childNodes) if (n.nodeType === 3) direct += n.textContent;
                        if (tag === 'input' && e.value) direct = e.value;
                        direct = direct.trim();
                        if (direct.length > 1) {
                            const bg = effBg(e);
                            fonts.push({...base, text:direct.slice(0,40),
                                        font:cs.fontFamily, rendered:renderedFont(cs.fontFamily),
                                        fs:parseFloat(cs.fontSize)||0, fw:parseInt(cs.fontWeight)||400,
                                        ls:cs.letterSpacing, col:cs.color,
                                        bg:bg.v ? bg.c : null, bgv:bg.v});
                        }
                    }
                    if (inB && r.width > 4 && r.height > 4) {
                        const c=[cs.borderTopLeftRadius, cs.borderTopRightRadius,
                                 cs.borderBottomLeftRadius, cs.borderBottomRightRadius];
                        if (c.some(v => v && v !== '0px')) radii.push({...base, corners:c});
                    }
                    if (inS && r.width > 8 && r.height > 8) {
                        const props={};
                        for (const p of PROPS) { const v=cs[p];
                            if (v && v.charCodeAt(0) !== 48 && v.endsWith('px')) {
                                const n=parseFloat(v); if (n>0) props[p]=n; } }
                        if (Object.keys(props).length) spacing.push({...base, props});
                    }
                }
                const grads = [];
                for (const e of document.body.getElementsByTagName('*')) {
                    const r = e.getBoundingClientRect();
                    if (r.width < 60 || r.height < 40) continue;
                    const bi = getComputedStyle(e).backgroundImage || '';
                    if (!bi.includes('linear-gradient')) continue;
                    const stops = [...bi.matchAll(/rgba?\\([^)]+\\)/g)]
                        .map(m => parseC(m[0])).filter(Boolean);
                    if (stops.length >= 2)
                        grads.push({x:r.x+scrollX, y:r.y+scrollY, w:r.width, h:r.height, stops: stops});
                }
                const controls = [];
                for (const e of document.querySelectorAll('input,select,textarea')) {
                    const r = e.getBoundingClientRect();
                    if (r.width < 40 || r.height < 16) continue;
                    const cs = getComputedStyle(e);
                    const surround = e.parentElement ? effBg(e.parentElement) : {v:false};
                    if (!surround.v) continue;
                    let bsrc = {border: null, bw: 0};
                    for (let p = e, d = 0; p && d < 3; p = p.parentElement, d++) {
                        const s = d === 0 ? cs : getComputedStyle(p);
                        const bc = parseC(s.borderTopColor);
                        const bwv = parseFloat(s.borderTopWidth) || 0;
                        if (bc && bc[3] >= 0.5 && bwv >= 1) { bsrc = {border: bc, bw: bwv}; break; }
                    }
                    controls.push({x:r.x+scrollX, y:r.y+scrollY, w:r.width, h:r.height,
                                   border: bsrc.border, bw: bsrc.bw,
                                   bg: parseC(cs.backgroundColor), surround: surround.c});
                }
                const rtl = {
                    dir: (document.documentElement.getAttribute('dir')
                          || getComputedStyle(document.body).direction || '').toLowerCase(),
                    lang: (document.documentElement.lang || '').toLowerCase(),
                    arrows: [...document.querySelectorAll('a,button')]
                        .filter(e => (e.innerText || '').includes('\\u2192'))
                        .slice(0, 20)
                        .map(e => { const r = e.getBoundingClientRect();
                                    return {x:r.x+scrollX, y:r.y+scrollY, w:r.width, h:r.height,
                                            text:(e.innerText||'').trim().slice(0,40)}; })
                };
                let approvedLoaded = false;
                try { approvedLoaded = document.fonts.check(`12px "__APPROVED__"`); } catch(e) {}
                return {fonts, radii, spacing, paras, grads, controls, rtl, approvedLoaded};
            }""".replace("__APPROVED__", APPROVED_FONT))

            # UX layer hook — نفس الصفحة المفتوحة، مسار جمع بيانات مستقل تماماً (ux/ux_checks.py).
            # إعادة ضبط حجم نافذة العرض للجوال (لقواعد RS-*) تحدث هنا، بعد أن التقطت DGA لقطتها
            # ومقاييسها بالكامل أعلاه — لا تؤثر على أي بيانات DGA محسوبة مسبقاً.
            if ENABLE_UX_LAYER:
                from ux.ux_checks import gather_ux_data, gather_ux_mobile_data
                ux_data = await gather_ux_data(pg)
                ux_mobile_data = await gather_ux_mobile_data(pg)
        finally:
            await b.close()

    with Image.open(shot) as im:
        width, height = im.size
    return {"url": url, "name": name, "shot": shot, "shot_width": width, "shot_height": height,
            "broken": broken, "imgs": imgs, "statusbar": statusbar, "colors": colors,
            "ux_data": ux_data, "ux_mobile_data": ux_mobile_data, **m}


# ============ 2) الفحوص الكودية (CSS/DOM) ============
def parse_radius(val, w, h):
    if not val:
        return None
    val = val.split()[0]
    try:
        if val.endswith("%"):
            pct = float(val[:-1])
            return 9999.0 if pct >= 45 else pct / 100 * min(w, h)
        if val.endswith("px"):
            px = float(val[:-2])
            return 9999.0 if px >= min(w, h) / 2 else px
    except ValueError:
        pass
    return None


def check_radius(radii):
    out = []
    for el in radii:
        bad = {round(px, 1) for c in el["corners"]
               if (px := parse_radius(c, el["w"], el["h"])) is not None
               and not any(abs(px - a) <= 0.5 for a in ALLOWED_RADIUS)}
        if bad:
            out.append({**el, "bad": sorted(bad)})
    return out


spacing_ok = lambda v: (any(abs(v - e) <= 0.5 for e in SPC_EXTRA)
                        or abs(v - round(v / BASE_UNIT) * BASE_UNIT) <= 0.5)


def check_spacing(spacing):
    out = []
    for el in spacing:
        bad = {prop_ar(p): round(v, 1) for p, v in el["props"].items() if not spacing_ok(v)}
        if bad:
            out.append({**el, "bad": bad})
    return out


def check_colors(colors):
    out = []
    for el in colors:
        rgb = tuple(el["rgb"])
        if any(max(abs(a - b) for a, b in zip(p, rgb)) <= COLOR_TOL for p in PALETTE):
            continue
        out.append({**el, "hex": "#%02X%02X%02X" % rgb, "near": nearest_token(rgb)})
    return out


def _lum(rgb):
    f = lambda c: (c / 255) / 12.92 if c / 255 <= 0.03928 else (((c / 255) + 0.055) / 1.055) ** 2.4
    r, g, b = (f(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def wcag_ratio(c1, c2):
    l1, l2 = sorted((_lum(c1), _lum(c2)), reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)


_CRE = re.compile(r"rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)")


def check_contrast(fonts):
    out, n_unv = [], 0
    for e in fonts:
        if not e.get("bgv") or not e.get("bg"):
            n_unv += 1
            continue
        m = _CRE.match(e.get("col") or "")
        if not m:
            continue
        fg = tuple(int(m.group(i)) for i in (1, 2, 3))
        a = float(m.group(4) or 1)
        if a < 1:
            fg = tuple(round(f * a + b * (1 - a)) for f, b in zip(fg, e["bg"]))
        big = (e["fs"] >= ACC_REQ["large_text_threshold_px"]
               or (e["fs"] >= 18.66 and e["fw"] >= 700))
        req = ACC_REQ["large_text_min_ratio"] if big else ACC_REQ["small_text_min_ratio"]
        r = wcag_ratio(fg, tuple(e["bg"]))
        if r < req - 0.05:
            out.append({**e, "ratio": round(r, 2), "req": req})
    return out, n_unv


def check_tracking(fonts):
    out = []
    for e in fonts:
        if e.get("fs", 0) < TRACK_MIN:
            continue
        ls = e.get("ls", "normal")
        try:
            px = 0.0 if ls in ("normal", "") else float(ls[:-2]) if ls.endswith("px") else 0.0
        except ValueError:
            px = 0.0
        if px > -0.005:
            out.append({**e, "ls_px": px, "want": round(-0.02 * e["fs"], 2)})
    return out


def check_parawidth(paras, max_w=720):
    return [{**e, "over": round(e["w"] - max_w)} for e in paras if e["w"] > max_w + 4]


def check_fontsize(fonts):
    out = []
    for e in fonts:
        fs = e.get("fs", 0)
        if fs <= 0:
            continue
        if not any(abs(fs - a) <= 0.5 for a in ALLOWED_FS):
            near = min(ALLOWED_FS, key=lambda a: abs(a - fs))
            out.append({**e, "near_fs": near})
    return out


def _near(c1, c2, tol=COLOR_TOL):
    return max(abs(a - b) for a, b in zip(c1, c2)) <= tol


def check_gradients(grads):
    out, n_unv = [], 0
    for el in grads:
        if any(len(s) > 3 and s[3] < 0.9 for s in el["stops"]):
            n_unv += 1
            continue
        cols = []
        for s in el["stops"]:
            c = tuple(int(v) for v in s[:3])
            if not any(_near(c, x, 3) for x in cols):
                cols.append(c)
        if len(cols) < 2:
            if cols and not any(_near(cols[0], p) for p in PALETTE):
                out.append({**el, "hexes": ["#%02X%02X%02X" % cols[0] + " (لون صلب)"]})
            continue
        ok = any(all(_near(c, a) or _near(c, b) for c in cols)
                 and any(_near(c, a) for c in cols)
                 and any(_near(c, b) for c in cols)
                 for a, b in GRAD_PAIRS)
        if not ok:
            out.append({**el, "hexes": ["#%02X%02X%02X" % c for c in cols[:3]]})
    return out, n_unv


def check_controls(controls):
    req = ACC_REQ["ui_components_min_ratio"]
    out, n_unv = [], 0
    for el in controls:
        sur = tuple(el["surround"])
        measurable = False
        best = 0.0
        if el["border"] and el["bw"] >= 1 and el["border"][3] >= 0.5:
            measurable = True
            best = wcag_ratio(tuple(int(v) for v in el["border"][:3]), sur)
        if el["bg"] and el["bg"][3] >= 0.99:
            measurable = True
            best = max(best, wcag_ratio(tuple(int(v) for v in el["bg"][:3]), sur))
        if not measurable:
            n_unv += 1
            continue
        if best < req - 0.05:
            out.append({**el, "ratio": round(best, 2)})
    return out, n_unv


def check_rtl(rtl):
    out = []
    if rtl.get("dir") != "rtl":
        out.append({"x": 0, "y": 0, "w": 1440, "h": 40, "kind": "dir",
                    "text": f"اتجاه الوثيقة: {rtl.get('dir') or 'غير محدد'} — المطلوب dir=rtl"})
    for a in rtl.get("arrows", []):
        out.append({**a, "kind": "arrow"})
    return out


def rect_of(el):
    return (int(el["x"]), int(el["y"]), int(el["x"] + el["w"]), int(el["y"] + el["h"]))


def _over_img(e, imgs):
    return overlap_frac((e["x"], e["y"], e["x"] + e["w"], e["y"] + e["h"]), imgs, "box") >= 0.5


def run_checks(page: dict) -> dict:
    fviol = [e for e in page["fonts"] if APPROVED_FONT.lower() not in e.get("rendered", e["font"]).lower()]
    logger.info(f"fonts: {len(fviol)}/{len(page['fonts'])} violations")

    rviol = check_radius(page["radii"])
    logger.info(f"radius: {len(rviol)}/{len(page['radii'])} violations")

    sviol = check_spacing(page["spacing"])
    logger.info(f"spacing: {len(sviol)}/{len(page['spacing'])} violations")

    cviol = check_colors(page["colors"])
    logger.info(f"colors: {len(cviol)}/{len(page['colors'])} violations")

    tpl_ok = bool(page["statusbar"].get("found"))
    if tpl_ok:
        logger.info("statusbar: found via DOM")
    else:
        sample = page["statusbar"].get("sample", "")
        logger.info(f"statusbar: not found, sample={sample[:80]!r}")

    aviol, a_unv = check_contrast(page["fonts"])
    a_img = [e for e in aviol if _over_img(e, page["imgs"])]
    if a_img:
        aviol = [e for e in aviol if not _over_img(e, page["imgs"])]
        a_unv += len(a_img)
        logger.info(f"excluded {len(a_img)} contrast checks over content images")
    logger.info(f"contrast: {len(aviol)}/{len(page['fonts']) - a_unv} violations ({a_unv} unmeasurable)")

    kviol = check_tracking(page["fonts"])
    k_total = sum(1 for e in page["fonts"] if e.get("fs", 0) >= TRACK_MIN)
    logger.info(f"tracking: {len(kviol)}/{k_total} violations")

    pviol = check_parawidth(page["paras"])
    logger.info(f"paragraphs: {len(pviol)}/{len(page['paras'])} violations")

    fzv = check_fontsize(page["fonts"])
    logger.info(f"fontsize: {len(fzv)}/{len(page['fonts'])} violations")

    grv, g_unv = check_gradients(page["grads"])
    logger.info(f"gradients: {len(grv)}/{len(page['grads']) - g_unv} violations ({g_unv} unmeasurable)")

    uiv, u_unv = check_controls(page["controls"])
    u_img = [e for e in uiv if _over_img(e, page["imgs"])]
    if u_img:
        uiv = [e for e in uiv if not _over_img(e, page["imgs"])]
        u_unv += len(u_img)
        logger.info(f"excluded {len(u_img)} control-contrast checks over content images")
    logger.info(f"controls: {len(uiv)}/{len(page['controls']) - u_unv} violations ({u_unv} unmeasurable)")

    rtv = check_rtl(page["rtl"])
    logger.info(f"rtl: {len(rtv)} violations")

    return {"fviol": fviol, "rviol": rviol, "sviol": sviol, "cviol": cviol, "tpl_ok": tpl_ok,
            "aviol": aviol, "a_unv": a_unv, "kviol": kviol, "pviol": pviol,
            "fzv": fzv, "grv": grv, "g_unv": g_unv, "uiv": uiv, "u_unv": u_unv, "rtv": rtv}


# ============ 3) الفحص البصري (مزوّد رؤية قابل للتبديل — vision_provider.py) ============
class Violation(BaseModel):
    box_2d: list[int]
    rule_id: str
    severity: Literal["Error", "Warning", "Info"]
    confidence: Literal["عالية", "متوسطة", "منخفضة"]
    evidence: str
    recommendation: str


def build_prompt() -> str:
    return f"""دقّق هذا الجزء من صفحة حكومية سعودية مقابل قواعد DGA البصرية باللغة العربية.
قارن القيم الفعلية (ألوان، مسافات) مقابل المعتمدة:
{json.dumps({"الأخضر السعودي": TOKENS["colors"]["primary"],
             "الذهبي الثانوي": TOKENS["colors"].get("secondary_gold", {}),
             "شبكة المسافات (px)": TOKENS["spacing"]}, ensure_ascii=False)}
القواعد:
{chr(10).join(f"- {r['id']} ({r['category']}, {r['severity']}): {r['title']} — {r['detection_visual']} | المتوقّع: {r.get('expected', '')}" for r in VISUAL_RULES)}
تنبيهات إلزامية — تمنع الأخطاء الشائعة على المواقع المختلفة:
1. الصور الفوتوغرافية وصور الأخبار والمحتوى الإعلامي: ألوانها ومحتواها ليست جزءاً من واجهة الموقع — لا تُبلّغ عن مخالفات ألوان أو تدرجات أو طباعة داخلها.
2. لا تُبلّغ عن عنصر بأنه "مفقود" (Missing) إلا إذا فحصت الشريحة كاملة وتأكدت من غيابه. شريط الحالة الحكومي هو شريط رفيع أعلى الصفحة فيه نص مثل "موقع حكومي رسمي/مسجل لدى هيئة الحكومة الرقمية" — إن رأيت هذا النص فالقاعدة ملتزم بها ولا تذكرها.
3. إن لم تكن متأكداً من مخالفة، اجعل confidence "منخفضة" أو لا تذكرها إطلاقاً — الدقة أهم من العدد.
لكل مخالفة: box_2d [ymin,xmin,ymax,xmax] 0-1000 + rule_id + severity + confidence + evidence + recommendation.
لا تُرجِع مخالفة بدون دليل بصري واضح في evidence."""


PROMPT = build_prompt()
RULES_SIG = hashlib.md5((MODEL + PROMPT).encode()).hexdigest()[:10]
# ملاحظة: استدعاء النموذج نفسه (بإعادة المحاولة عند الأخطاء العابرة) انتقل إلى
# VisionProvider.analyze_tile() (vision_provider.py) — معزول هناك مع كل تفاصيل
# Gemini الأخرى (thinking_config، response_schema، الخ).


def make_tiles(h, th, ov):
    ys = range(0, max(h - ov, 1), th - ov)
    return [(y, min(y + th, h)) for y in ys]


def to_box(it, W, th, y0):
    """يرجّع (box, had_box_field).

    had_box_field=False يعني المزوّد ما رجّع box_2d أصلاً (متوقّع مع مزوّد
    الوزارة — راجع vision_provider.py) — المخالفة تُحفظ بلا box بدل إسقاطها.
    had_box_field=True مع box=None يعني box_2d كان موجوداً لكنه غير منطقي
    (حارس هلوسة Gemini الأصلي) — هذه الحالة تُسقَط كما كانت دائماً."""
    raw = it.get("box_2d")
    if not (isinstance(raw, (list, tuple)) and len(raw) == 4):
        return None, False
    try:
        ymin, xmin, ymax, xmax = (float(v) for v in raw)
    except (TypeError, ValueError):
        return None, False
    if xmin > xmax:
        xmin, xmax = xmax, xmin
    if ymin > ymax:
        ymin, ymax = ymax, ymin
    bx = (int(xmin / 1000 * W), int(ymin / 1000 * th) + y0, int(xmax / 1000 * W), int(ymax / 1000 * th) + y0)
    bw, bh = bx[2] - bx[0], bx[3] - bx[1]
    if bw < 2 or bh < 2:
        return None, True
    if bh > 0.35 * th and bw < 0.20 * W and bh / max(bw, 1) > 4:
        return None, True
    if bw > 0.9 * W and bh < 12:
        return None, True
    return bx, True


def overlap_frac(box, rects, mode="box"):
    x1, y1, x2, y2 = box
    area = max((x2 - x1) * (y2 - y1), 1)
    best = 0.0
    for b in rects:
        ox = max(0, min(x2, b["x"] + b["w"]) - max(x1, b["x"]))
        oy = max(0, min(y2, b["y"] + b["h"]) - max(y1, b["y"]))
        if ox <= 0 or oy <= 0:
            continue
        denom = area if mode == "box" else max(b["w"] * b["h"], 1)
        best = max(best, ox * oy / denom)
    return best


def on_broken(box, broken):
    return (overlap_frac(box, broken, "box") >= 0.5
            or overlap_frac(box, broken, "rect") >= 0.8)


def iou(a, b):
    ox = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    oy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ox * oy
    if inter <= 0:
        return 0.0
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / max(ua, 1)


def dedup(viols, thr):
    conf_rank = {"عالية": 3, "متوسطة": 2, "منخفضة": 1}
    boxed = [v for v in viols if v["box"]]
    boxless = [v for v in viols if not v["box"]]
    kept = []
    for v in sorted(boxed, key=lambda v: -(v["box"][2] - v["box"][0]) * (v["box"][3] - v["box"][1])):
        dup = next((k for k in kept if k["rule_id"] == v["rule_id"]
                    and iou(k["box"], v["box"]) >= thr), None)
        if dup:
            if conf_rank.get(v["conf"], 0) > conf_rank.get(dup["conf"], 0):
                dup["conf"], dup["rec"] = v["conf"], v["rec"]
            continue
        kept.append(dict(v))
    # بلا box: لا معلومة مكانية لدمجها عبر IoU — نُبقي واحدة فقط لكل rule_id
    # (الأعلى ثقة) بدل تكرار نفس المخالفة لكل شريحة رصدتها فيها (مزوّد الوزارة
    # غير المؤكَّد فقط يصل لهذا المسار — راجع vision_provider.py).
    best_boxless: dict[str, dict] = {}
    for v in boxless:
        cur = best_boxless.get(v["rule_id"])
        if cur is None or conf_rank.get(v["conf"], 0) > conf_rank.get(cur["conf"], 0):
            best_boxless[v["rule_id"]] = v
    kept.extend(best_boxless.values())
    return kept


def _run_visual_scan_sync(provider: VisionProvider, page: dict) -> tuple[list[dict], list[dict]]:
    W, H = page["shot_width"], page["shot_height"]
    th = TILE_HEIGHT
    tiles = make_tiles(H, th, OVERLAP)
    if len(tiles) > MAX_TILES:
        th = -(-H // MAX_TILES) + OVERLAP
        tiles = make_tiles(H, th, OVERLAP)
    logger.info(f"visual scan: {len(tiles)} tiles (page height={H}px)")

    cache = json.load(open(CACHE_PATH, encoding="utf-8")) if CACHE_PATH.exists() else {}
    full_image = Image.open(page["shot"]).convert("RGB")

    def analyze(i, y0, y1):
        crop = full_image.crop((0, y0, W, y1))
        key = (f"{page['name']}|{W}x{H}|{i}|{RULES_SIG}|"
               + hashlib.md5(crop.tobytes()).hexdigest()[:10])
        if key in cache:
            return i, key, cache[key], True
        tile_note = (f"\n(هذه الشريحة {i + 1} من {len(tiles)} من صفحة طويلة"
                     + ("" if i == 0 else " — أعلى الصفحة ليس فيها؛ لا تُقيّم قواعد الهيدر أو شريط الحالة")
                     + ")")
        time.sleep(0.8 * i)
        items, _ok = provider.analyze_tile(
            crop, PROMPT + tile_note,
            system_instruction="Return violations as JSON array in Arabic. No masks. Max 15.",
            response_model=Violation, max_output_tokens=8192, timeout_s=30.0,
        )
        return i, key, items, False

    with ThreadPoolExecutor(max_workers=min(4, len(tiles))) as ex:
        results = sorted(ex.map(lambda a: analyze(*a),
                                 [(i, y0, y1) for i, (y0, y1) in enumerate(tiles)]))

    fresh = [(k, it) for _, k, it, cached in results if not cached]
    if fresh:
        for k, it in fresh:
            cache[k] = it
        save_cache(cache)

    cached_n = sum(1 for _, _, _, c in results if c)
    logger.info(f"visual scan: {cached_n}/{len(results)} tiles from cache, {len(results) - cached_n} analyzed fresh")
    for i, _key, items, cached in results:
        logger.info(f"visual scan tile {i + 1}/{len(tiles)}: {len(items)} raw findings ({'cache' if cached else 'fresh'})")

    vv, on_imgs = [], []
    excluded_code = excluded_global = excluded_box = excluded_broken = 0
    for i, key, items, cached in results:
        y0, y1 = tiles[i]
        for it in items:
            rid = it.get("rule_id", "")
            if rid in CODE_CHECKED:
                excluded_code += 1
                continue
            if i > 0 and rid in GLOBAL_TOP:
                excluded_global += 1
                continue
            box, had_box = to_box(it, W, y1 - y0, y0)
            if had_box and box is None:
                excluded_box += 1  # box_2d كان موجوداً لكنه غير منطقي — يُسقط كما كان دائماً
                continue
            # box=None وhad_box=False: المزوّد لم يرجّع box_2d أصلاً (متوقّع مع
            # مزوّد الوزارة غير المؤكَّد) — تُحفظ المخالفة بلا موضع بدل إسقاطها.
            if box and on_broken(box, page["broken"]):
                excluded_broken += 1
                continue
            v = {"box": box, "rule_id": rid, "sev": it["severity"],
                 "conf": it["confidence"], "rec": it.get("recommendation"),
                 "evidence": it.get("evidence")}
            if box and rid.startswith("DGA-CLR") and overlap_frac(box, page["imgs"], "box") >= IMG_OVERLAP:
                on_imgs.append(v)
                continue
            vv.append(v)

    if excluded_code:
        logger.info(f"excluded {excluded_code} visual findings already covered by code checks")
    if excluded_global:
        logger.info(f"excluded {excluded_global} header/template findings outside the first tile")
    if excluded_box:
        logger.info(f"excluded {excluded_box} findings with invalid bounding box")
    if excluded_broken:
        logger.info(f"excluded {excluded_broken} findings overlapping broken/unloaded images")
    if on_imgs:
        logger.info(f"excluded {len(on_imgs)} color violations over content images")

    deduped = dedup(vv, DEDUP_IOU)
    logger.info(f"dedup: {len(vv)} raw findings -> {len(deduped)} unique ({len(vv) - len(deduped)} merged)")

    return deduped, dedup(on_imgs, DEDUP_IOU)


# ============ 4) النتيجة والتجميع بشكل الواجهة (Audit) ============
WEIGHT = {"Error": 3, "Warning": 2, "Info": 1}
TOTAL_W = sum(WEIGHT.get(r["severity"], 1) for r in DGA["rules"])


def score_of(rule_ids) -> int:
    lost = sum(WEIGHT.get(RULE.get(r, {}).get("severity", "Warning"), 1) for r in rule_ids)
    return max(0, round(100 * (1 - lost / max(TOTAL_W, 1))))


def grade_of(score: int) -> str:
    return "A" if score >= 90 else "B" if score >= 75 else "C" if score >= 60 else "D"


def region_from_box(box, W, H):
    x1, y1, x2, y2 = box
    return {
        "x": round(x1 / W * 100, 2),
        "y": round(y1 / H * 100, 2),
        "width": round((x2 - x1) / W * 100, 2),
        "height": round((y2 - y1) / H * 100, 2),
    }


def _status_for(rule: dict, violated: bool) -> str:
    if not violated:
        return "pass"
    return "fail" if rule.get("severity") == "Error" else "warn"


def assemble_audit(url: str, page: dict, checks: dict, vv: list[dict], elapsed: float | None = None) -> dict:
    W, H = page["shot_width"], page["shot_height"]
    fviol, rviol, sviol, cviol = checks["fviol"], checks["rviol"], checks["sviol"], checks["cviol"]
    tpl_ok, aviol, kviol, pviol = checks["tpl_ok"], checks["aviol"], checks["kviol"], checks["pviol"]
    fzv, grv, uiv, rtv = checks["fzv"], checks["grv"], checks["uiv"], checks["rtv"]

    by_rule = defaultdict(list)
    for v in vv:
        by_rule[v["rule_id"]].append(v)

    # عدد المواضع المفحوصة/الملتزمة لكل قاعدة مقيسة كوديًا (بيانات محسوبة أصلاً أعلاه — عرض فقط، بلا فحص جديد)
    k_total = sum(1 for e in page["fonts"] if e.get("fs", 0) >= TRACK_MIN)
    grad_checked = max(len(page["grads"]) - checks["g_unv"], 0)
    acc_checked = max(len(page["fonts"]) - checks["a_unv"], 0)
    ui_checked = max(len(page["controls"]) - checks["u_unv"], 0)
    locations = {
        "DGA-TYP-001": (len(page["fonts"]), len(page["fonts"]) - len(fviol)),
        "DGA-TYP-002": (len(page["fonts"]), len(page["fonts"]) - len(fzv)),
        "DGA-TYP-005": (k_total, k_total - len(kviol)),
        "DGA-RAD-001": (len(page["radii"]), len(page["radii"]) - len(rviol)),
        "DGA-SPC-001": (len(page["spacing"]), len(page["spacing"]) - len(sviol)),
        "DGA-SPC-004": (len(page["paras"]), len(page["paras"]) - len(pviol)),
        "DGA-CLR-001": (len(page["colors"]), len(page["colors"]) - len(cviol)),
        "DGA-CLR-004": (grad_checked, grad_checked - len(grv)),
        "DGA-ACC-001": (acc_checked, acc_checked - len(aviol)),
        "DGA-ACC-002": (ui_checked, ui_checked - len(uiv)),
        "DGA-TPL-001": (1, 1 if tpl_ok else 0),
    }

    conf_ids, all_ids = set(), set()
    if fviol: conf_ids.add("DGA-TYP-001"); all_ids.add("DGA-TYP-001")
    if rviol: conf_ids.add("DGA-RAD-001"); all_ids.add("DGA-RAD-001")
    if sviol: conf_ids.add("DGA-SPC-001"); all_ids.add("DGA-SPC-001")
    if cviol: conf_ids.add("DGA-CLR-001"); all_ids.add("DGA-CLR-001")
    if aviol: conf_ids.add("DGA-ACC-001"); all_ids.add("DGA-ACC-001")
    if kviol: conf_ids.add("DGA-TYP-005"); all_ids.add("DGA-TYP-005")
    if pviol: conf_ids.add("DGA-SPC-004"); all_ids.add("DGA-SPC-004")
    if fzv: conf_ids.add("DGA-TYP-002"); all_ids.add("DGA-TYP-002")
    if grv: conf_ids.add("DGA-CLR-004"); all_ids.add("DGA-CLR-004")
    if uiv: conf_ids.add("DGA-ACC-002"); all_ids.add("DGA-ACC-002")
    if rtv: conf_ids.add("DGA-RTL-002"); all_ids.add("DGA-RTL-002")
    if not tpl_ok: all_ids.add("DGA-TPL-001")  # غير مؤكّد — لا يدخل النسبة المؤكّدة

    for rid, items in by_rule.items():
        all_ids.add(rid)
        if any(v["conf"] == "عالية" for v in items):
            conf_ids.add(rid)

    score_conf = score_of(conf_ids)
    score_all = score_of(all_ids)
    grade = "A" if score_conf >= 90 else "B" if score_conf >= 75 else "C" if score_conf >= 60 else "D"

    rules_out = []
    for r in DGA["rules"]:
        rid = r["id"]
        region = None
        evidence = None
        recommendation = r.get("recommendation")

        if rid == "DGA-TYP-001":
            status = _status_for(r, bool(fviol))
            if fviol:
                region = region_from_box(rect_of(fviol[0]), W, H)
                used = Counter(e.get("rendered", e["font"]).split(",")[0].strip(" \"'") for e in fviol)
                top = " · ".join(f"{f} ×{n}" for f, n in used.most_common(3))
                evidence = f"{len(fviol)} عنصر بخط غير معتمد — {top}"
        elif rid == "DGA-RAD-001":
            status = _status_for(r, bool(rviol))
            if rviol:
                region = region_from_box(rect_of(rviol[0]), W, H)
                vals = Counter(v for e in rviol for v in e["bad"])
                top = " · ".join(f"{v:g}px ×{n}" for v, n in vals.most_common(3))
                evidence = f"{len(rviol)} عنصر بزوايا خارج المقياس — {top}"
        elif rid == "DGA-SPC-001":
            status = _status_for(r, bool(sviol))
            if sviol:
                region = region_from_box(rect_of(sviol[0]), W, H)
                vals = Counter(v for e in sviol for v in e["bad"].values())
                top = " · ".join(f"{v:g}px ×{n}" for v, n in vals.most_common(3))
                evidence = f"{len(sviol)} عنصر خارج شبكة {BASE_UNIT}px — {top}"
        elif rid == "DGA-CLR-001":
            status = _status_for(r, bool(cviol))
            if cviol:
                region = region_from_box(rect_of(cviol[0]), W, H)
                vals = Counter(e["hex"] for e in cviol)
                top = " · ".join(f"{h} ×{n}" for h, n in vals.most_common(3))
                evidence = f"{len(cviol)} عنصر بلون خارج الباليتة — {top}"
        elif rid == "DGA-ACC-001":
            status = _status_for(r, bool(aviol))
            if aviol:
                worst = min(aviol, key=lambda e: e["ratio"])
                region = region_from_box(rect_of(worst), W, H)
                evidence = f'أسوأ تباين {worst["ratio"]}:1 (المطلوب {worst["req"]}:1) — "{worst["text"][:30]}"'
        elif rid == "DGA-TYP-005":
            status = _status_for(r, bool(kviol))
            if kviol:
                region = region_from_box(rect_of(kviol[0]), W, H)
                evidence = f'{len(kviol)} عنوان بلا تتبّع سالب — "{kviol[0]["text"][:30]}"'
        elif rid == "DGA-SPC-004":
            status = _status_for(r, bool(pviol))
            if pviol:
                worst = max(pviol, key=lambda e: e["over"])
                region = region_from_box(rect_of(worst), W, H)
                evidence = f"{len(pviol)} فقرة أعرض من 720px (+{worst['over']}px كحد أقصى)"
        elif rid == "DGA-TYP-002":
            status = _status_for(r, bool(fzv))
            if fzv:
                region = region_from_box(rect_of(fzv[0]), W, H)
                vals = Counter(f"{e['fs']:g}px" for e in fzv)
                top = " · ".join(f"{v} ×{n}" for v, n in vals.most_common(3))
                evidence = f"{len(fzv)} عنصر بحجم خط خارج المقياس — {top}"
        elif rid == "DGA-CLR-004":
            status = _status_for(r, bool(grv))
            if grv:
                region = region_from_box(rect_of(grv[0]), W, H)
                evidence = f'{len(grv)} تدرج غير مطابق — محطات: {" → ".join(grv[0]["hexes"])}'
        elif rid == "DGA-ACC-002":
            status = _status_for(r, bool(uiv))
            if uiv:
                worst = min(uiv, key=lambda e: e["ratio"])
                region = region_from_box(rect_of(worst), W, H)
                evidence = f'أسوأ تباين حقل {worst["ratio"]}:1 (المطلوب {ACC_REQ["ui_components_min_ratio"]}:1)'
        elif rid == "DGA-RTL-002":
            status = _status_for(r, bool(rtv))
            if rtv:
                region = region_from_box(rect_of(rtv[0]), W, H)
                evidence = "؛ ".join(
                    ("اتجاه الوثيقة غير rtl" if e["kind"] == "dir" else f'سهم ← معكوس: "{e["text"][:30]}"')
                    for e in rtv[:3]
                )
        elif rid == "DGA-TPL-001":
            if tpl_ok:
                status = "pass"
            else:
                # عدم العثور على الشريط في الـ DOM (shadow roots/iframes المتاحة) لا يثبت غيابه —
                # قد يكون داخل iframe عابر للمصدر يتعذّر الوصول إليه تقنيًا. لا نعلن مخالفة مؤكدة
                # بناءً على عجزنا عن القياس، فتُستثنى هذه الحالة من العدّ والنسبة عمدًا.
                status = "manual_review"
                evidence = ("لم يُعثر على شريط الحالة في DOM الصفحة (فُحصت الـ shadow roots والـ iframes "
                            "المتاحة) — راجع أعلى لقطة الصفحة يدوياً: إن كان الشريط ظاهراً فالمعيار مستوفى")
                region = {"x": 0, "y": 0, "width": 100, "height": round(48 / H * 100, 2)}
        else:
            items = by_rule.get(rid, [])
            if not items:
                status = "pass"
            else:
                status = _status_for(r, True)
                # ليس كل عنصر معه box بالضرورة (مزوّد الوزارة قد لا يرجّع box_2d
                # إطلاقاً — راجع vision_provider.py) — نستخدم أول عنصر معه موضع
                # فعلي؛ إن لم يوجد، تبقى region فارغة والمخالفة تُعرض بلا تظليل.
                boxed_item = next((it for it in items if it["box"]), None)
                region = region_from_box(boxed_item["box"], W, H) if boxed_item else None
                evidence = items[0].get("evidence")
                if len(items) > 1:
                    evidence = f"{evidence} (+{len(items) - 1} مواضع أخرى)" if evidence else f"{len(items)} مواضع"
                if items[0].get("rec"):
                    recommendation = items[0]["rec"]

        # حالة "تحقق يدوي" غير محسومة عمدًا — تُستبعد من ترجيح المواضع بالكامل
        loc = locations.get(rid) if status != "manual_review" else None
        rules_out.append({
            "id": rid,
            "category": r["category"],
            "status": status,
            "title": r["title"],
            "description": r["description"],
            "recommendation": recommendation,
            "evidence": evidence,
            "region": region,
            "checkedLocations": loc[0] if loc else None,
            "passedLocations": loc[1] if loc else None,
        })

    rules_code = len(conf_ids & CODE_CHECKED)
    rules_visual_high = len(conf_ids - CODE_CHECKED)
    rules_visual_other = len(all_ids) - len(conf_ids)
    elapsed_part = f" elapsed={round(elapsed)}s" if elapsed is not None else ""
    logger.info(f"audit complete: url={url} conf={score_conf} est={score_all} "
                f"rules_code={rules_code} rules_visual_high={rules_visual_high} "
                f"rules_visual_other={rules_visual_other}{elapsed_part}")

    return {
        "id": f"aud_{abs(hash(url)) % 10_000_000}",
        "url": url,
        "scannedAt": datetime.now(timezone.utc).isoformat(),
        "durationSec": 0,
        "score": score_conf,
        "scoreEstimated": score_all,
        "grade": grade,
        "rules": rules_out,
        "screenshots": [
            {"label": "سطح المكتب", "viewport": "desktop", "url": f"/shots/{Path(page['shot']).name}",
             "width": W, "height": H},
        ],
    }


# ============ 5) نقطة الدخول ============
async def run_audit(url: str, provider: VisionProvider) -> dict:
    t0 = time.time()
    page = await capture_page(url)
    checks = run_checks(page)

    # نفس provider يُمرَّر لفحصي DGA وUX البصريين — كلاهما كانا أصلاً يُشغَّلان
    # في threads منفصلة (ThreadPoolExecutor) على نفس عميل Gemini، فمشاركة
    # provider واحد بينهما لا تضيف أي تزامن جديد لم يكن موجوداً.
    dga_visual_task = asyncio.to_thread(_run_visual_scan_sync, provider, page)
    if ENABLE_UX_LAYER:
        from ux.ux_visual_checks import run_ux_visual_checks
        ux_visual_task = asyncio.to_thread(run_ux_visual_checks, provider, page)
        (vv, _on_imgs), ux_visual_rules = await asyncio.gather(dga_visual_task, ux_visual_task)
    else:
        vv, _on_imgs = await dga_visual_task

    result = assemble_audit(url, page, checks, vv, elapsed=time.time() - t0)

    # UX layer hook — دمج إضافي بعد اكتمال نتيجة DGA، لا يعدّل assemble_audit()/checks
    # الخاصة بـDGA. تعطيل ENABLE_UX_LAYER يُلغي هذه الكتلة بالكامل فيرجع للنتيجة الأصلية.
    for r in result["rules"]:
        r["source"] = "DGA"
    if ENABLE_UX_LAYER:
        from ux.ux_checks import RULE_BY_ID as UX_RULE_BY_ID
        from ux.ux_checks import WEIGHT as UX_WEIGHT
        from ux.ux_checks import run_ux_checks
        ux_rules = run_ux_checks(page.get("ux_data"), page["shot_width"], page["shot_height"], page.get("ux_mobile_data"))
        ux_rules += ux_visual_rules
        if ux_rules:
            result["rules"].extend(ux_rules)
            # not_applicable/undetermined مستبعدة كلياً من معادلة النقاط (بسط ومقام) — لا تُحتسب
            # كأنها اجتازت الفحص ولا كأنها فشلته؛ لا تخمين لنتيجة قاعدة لم تُقيَّم فعلياً.
            scored = [r for r in ux_rules if r["status"] in ("pass", "fail", "warn")]
            ux_total_w = sum(UX_WEIGHT[UX_RULE_BY_ID[r["id"]]["severity"]] for r in scored)
            ux_lost = sum(UX_WEIGHT[UX_RULE_BY_ID[r["id"]]["severity"]]
                          for r in scored if r["status"] != "pass")
            # نِسَب DGA وUX منفصلتان لعرض الواجهة (كل قسم يُقيَّم بمعزل عن الآخر) — تُلتقَط قبل
            # حساب النسبة المدموجة أدناه، التي تبقى كما هي لأغراض التخزين/الدرجة الحرفية الحالية.
            result["dgaScore"] = result["score"]
            result["dgaScoreEstimated"] = result["scoreEstimated"]
            result["dgaGrade"] = result["grade"]
            result["uxScore"] = max(0, round(100 * (1 - ux_lost / ux_total_w))) if ux_total_w > 0 else None
            result["uxGrade"] = grade_of(result["uxScore"]) if result["uxScore"] is not None else None
            for key in ("score", "scoreEstimated"):
                dga_lost = TOTAL_W * (1 - result[key] / 100)
                result[key] = max(0, round(100 * (1 - (dga_lost + ux_lost) / (TOTAL_W + ux_total_w))))

    return result
