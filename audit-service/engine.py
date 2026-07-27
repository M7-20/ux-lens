# ============================================================
#  UX Lens — محرك تدقيق DGA (نسخة خدمة، بدون Colab)
#  من CSS (يقين 100%): الخط · الزوايا · المسافات
#  من الصورة (Gemini): بقية القواعد، بمستوى ثقة ودليل
# ============================================================
import asyncio
import hashlib
import json
import re
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from google import genai
from google.genai import errors, types
from PIL import Image
from playwright.async_api import async_playwright
from pydantic import BaseModel

BASE_DIR = Path(__file__).parent
SHOTS_DIR = BASE_DIR / "shots"
CACHE_PATH = BASE_DIR / "site_cache.json"
SHOTS_DIR.mkdir(exist_ok=True)

APPROVED_FONT = "IBM Plex Sans Arabic"
TILE_HEIGHT = 1600
OVERLAP = 200
SLEEP_TILES = 6
MODEL = "gemini-3.5-flash"

with open(BASE_DIR / "dga" / "dga-rules.json", encoding="utf-8") as f:
    DGA = json.load(f)
with open(BASE_DIR / "dga" / "dga-tokens.json", encoding="utf-8") as f:
    TOKENS = json.load(f)

RULE = {r["id"]: r for r in DGA["rules"]}
CODE_CHECKED = {"DGA-TYP-001", "DGA-RAD-001", "DGA-SPC-001"}
VISUAL_RULES = [r for r in DGA["rules"] if r["id"] not in CODE_CHECKED]

RADIUS_TOKEN = {float(v): k for k, v in TOKENS["radius"].items()}
ALLOWED_RADIUS = sorted(RADIUS_TOKEN)
BASE_UNIT = int(TOKENS["spacing"].get("base_unit", 4))
SPC_EXTRA = {2.0, 6.0}
prop_ar = lambda p: re.sub(r"([A-Z])", r"-\1", p).lower()


def safe_name(url: str) -> str:
    p = urlparse(url)
    name = re.sub(r"[^A-Za-z0-9_-]+", "_", p.path.strip("/") or "home")[:50]
    if p.query:
        keys = "_".join(sorted({q.split("=")[0] for q in p.query.split("&") if q}))
        name += f"__{re.sub(r'[^A-Za-z0-9_-]+', '', keys)[:20]}_{hashlib.md5(p.query.encode()).hexdigest()[:6]}"
    return name


# ============ 1) التقاط الصفحة ============
async def capture_page(url: str) -> dict:
    name = safe_name(url)
    shot = str(SHOTS_DIR / f"{name}.png")
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--no-sandbox"])
        pg = await b.new_page(viewport={"width": 1440, "height": 900})
        try:
            await pg.goto(url, wait_until="load", timeout=75000)

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

            broken = await pg.evaluate("""() => [...document.images]
                .filter(i => !i.complete || !i.naturalWidth)
                .map(i => { const r = i.getBoundingClientRect();
                            return {src:i.currentSrc||i.src||'', alt:(i.alt||'').slice(0,60),
                                    x:r.x+scrollX, y:r.y+scrollY, w:r.width, h:r.height}; })
                .filter(o => o.w > 20 && o.h > 20)""")

            png_bytes = await pg.screenshot(full_page=True)
            with open(shot, "wb") as f:
                f.write(png_bytes)

            m = await pg.evaluate("""() => {
                const FONT = new Set(['h1','h2','h3','h4','p','a','button','span','li','label','input']);
                const BOX  = new Set(['button','a','input','select','textarea','div','section','article','li','img']);
                const SPC  = new Set(['button','a','input','select','textarea','section','article','li',
                                      'header','footer','nav','div','p','h1','h2','h3','ul','form']);
                const PROPS=['paddingTop','paddingRight','paddingBottom','paddingLeft',
                             'marginTop','marginRight','marginBottom','marginLeft','rowGap','columnGap'];
                const fonts=[], radii=[], spacing=[];
                for (const e of document.body.getElementsByTagName('*')) {
                    const tag = e.tagName.toLowerCase();
                    const inF = FONT.has(tag), inB = BOX.has(tag), inS = SPC.has(tag);
                    if (!inF && !inB && !inS) continue;
                    const r = e.getBoundingClientRect();
                    if (r.width <= 0 || r.height <= 0) continue;
                    const cs = getComputedStyle(e);
                    const base = {x:r.x+scrollX, y:r.y+scrollY, w:r.width, h:r.height};

                    if (inF) {
                        const t = (e.textContent || '').trim();
                        if (t.length > 1) fonts.push({...base, text:t.slice(0,40), font:cs.fontFamily});
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
                return {fonts, radii, spacing};
            }""")
        finally:
            await b.close()

    with Image.open(shot) as im:
        width, height = im.size
    return {"url": url, "name": name, "shot": shot, "shot_width": width, "shot_height": height,
            "broken": broken, **m}


# ============ 2) الفحوص الكودية (CSS) ============
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


def rect_of(el):
    return (int(el["x"]), int(el["y"]), int(el["x"] + el["w"]), int(el["y"] + el["h"]))


# ============ 3) الفحص البصري (Gemini) ============
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
لكل مخالفة: box_2d [ymin,xmin,ymax,xmax] 0-1000 + rule_id + severity + confidence + evidence + recommendation.
لا تُرجِع مخالفة بدون دليل بصري واضح في evidence."""


def gen(client: genai.Client, **kw):
    for a in range(1, 5):
        try:
            return client.models.generate_content(**kw)
        except (errors.ServerError, errors.ClientError) as e:
            if not (isinstance(e, errors.ServerError) or getattr(e, "code", None) == 429) or a == 4:
                raise
            time.sleep(5 * a)


def make_tiles(h, th, ov):
    ys = range(0, max(h - ov, 1), th - ov)
    return [(y, min(y + th, h)) for y in ys]


def to_box(it, W, th, y0):
    ymin, xmin, ymax, xmax = it["box_2d"]
    if xmin > xmax:
        xmin, xmax = xmax, xmin
    if ymin > ymax:
        ymin, ymax = ymax, ymin
    bx = (int(xmin / 1000 * W), int(ymin / 1000 * th) + y0, int(xmax / 1000 * W), int(ymax / 1000 * th) + y0)
    bw, bh = bx[2] - bx[0], bx[3] - bx[1]
    if bw < 2 or bh < 2:
        return None
    if bh > 0.35 * th and bw < 0.20 * W and bh / max(bw, 1) > 4:
        return None
    if bw > 0.9 * W and bh < 12:
        return None
    return bx


def on_broken(box, broken):
    x1, y1, x2, y2 = box
    area = max((x2 - x1) * (y2 - y1), 1)
    for b in broken:
        ox = max(0, min(x2, b["x"] + b["w"]) - max(x1, b["x"]))
        oy = max(0, min(y2, b["y"] + b["h"]) - max(y1, b["y"]))
        if ox <= 0 or oy <= 0:
            continue
        if ox * oy / area >= 0.5:
            return True
        if ox * oy / max(b["w"] * b["h"], 1) >= 0.8:
            return True
    return False


async def run_visual_scan(client: genai.Client, page: dict) -> list[dict]:
    W, H = page["shot_width"], page["shot_height"]
    tiles = make_tiles(H, TILE_HEIGHT, OVERLAP)
    prompt = build_prompt()

    cache = json.load(open(CACHE_PATH, encoding="utf-8")) if CACHE_PATH.exists() else {}
    vv = []
    full_image = Image.open(page["shot"]).convert("RGB")
    for i, (y0, y1) in enumerate(tiles):
        key = f"{page['name']}|{W}x{H}|{i}"
        if key in cache:
            items = cache[key]
        else:
            try:
                tile_img = full_image.crop((0, y0, W, y1))
                r = await asyncio.to_thread(
                    gen, client, model=MODEL, contents=[tile_img, prompt],
                    config=types.GenerateContentConfig(
                        system_instruction="Return violations as JSON array in Arabic. No masks. Max 15.",
                        temperature=0, max_output_tokens=8192,
                        response_mime_type="application/json", response_schema=list[Violation],
                        thinking_config=types.ThinkingConfig(thinking_budget=0)))
                items = json.loads(r.text)
            except Exception:
                items = []
            cache[key] = items
            json.dump(cache, open(CACHE_PATH, "w", encoding="utf-8"), ensure_ascii=False)
            if i < len(tiles) - 1:
                await asyncio.sleep(SLEEP_TILES)

        for it in items:
            if it.get("rule_id") in CODE_CHECKED:
                continue
            box = to_box(it, W, y1 - y0, y0)
            if not box:
                continue
            if on_broken(box, page["broken"]):
                continue
            vv.append({"box": box, "rule_id": it["rule_id"], "sev": it["severity"],
                       "conf": it["confidence"], "rec": it.get("recommendation"),
                       "evidence": it.get("evidence")})
    return vv


# ============ 4) تجميع النتيجة بشكل الواجهة (Audit) ============
def region_from_box(box, W, H):
    x1, y1, x2, y2 = box
    return {
        "x": round(x1 / W * 100, 2),
        "y": round(y1 / H * 100, 2),
        "width": round((x2 - x1) / W * 100, 2),
        "height": round((y2 - y1) / H * 100, 2),
    }


def assemble_audit(url: str, page: dict, fviol, rviol, sviol, vv: list[dict]) -> dict:
    W, H = page["shot_width"], page["shot_height"]

    violated_ids = set()
    if fviol:
        violated_ids.add("DGA-TYP-001")
    if rviol:
        violated_ids.add("DGA-RAD-001")
    if sviol:
        violated_ids.add("DGA-SPC-001")

    by_rule = defaultdict(list)
    for v in vv:
        by_rule[v["rule_id"]].append(v)
        violated_ids.add(v["rule_id"])

    WEIGHT = {"Error": 3, "Warning": 2, "Info": 1}
    total_w = sum(WEIGHT.get(r["severity"], 1) for r in DGA["rules"])
    lost_w = sum(WEIGHT.get(RULE.get(rid, {}).get("severity", "Warning"), 1) for rid in violated_ids)
    score = max(0, round(100 * (1 - lost_w / max(total_w, 1))))
    grade = "A" if score >= 90 else "B" if score >= 75 else "C" if score >= 60 else "D"

    rules_out = []
    for r in DGA["rules"]:
        rid = r["id"]
        region = None
        evidence = None
        recommendation = r.get("recommendation")

        if rid == "DGA-TYP-001":
            status = "fail" if fviol else "pass"
            if fviol:
                region = region_from_box(rect_of(fviol[0]), W, H)
                used = Counter(e["font"].split(",")[0].strip(" \"'") for e in fviol)
                top = " · ".join(f"{f} ×{n}" for f, n in used.most_common(3))
                evidence = f"{len(fviol)} عنصر بخط غير معتمد — {top}"
        elif rid == "DGA-RAD-001":
            status = "fail" if rviol else "pass"
            if rviol:
                region = region_from_box(rect_of(rviol[0]), W, H)
                vals = Counter(v for e in rviol for v in e["bad"])
                top = " · ".join(f"{v:g}px ×{n}" for v, n in vals.most_common(3))
                evidence = f"{len(rviol)} عنصر بزوايا خارج المقياس — {top}"
        elif rid == "DGA-SPC-001":
            status = "fail" if sviol else "pass"
            if sviol:
                region = region_from_box(rect_of(sviol[0]), W, H)
                vals = Counter(v for e in sviol for v in e["bad"].values())
                top = " · ".join(f"{v:g}px ×{n}" for v, n in vals.most_common(3))
                evidence = f"{len(sviol)} عنصر خارج شبكة {BASE_UNIT}px — {top}"
        else:
            items = by_rule.get(rid, [])
            if not items:
                status = "pass"
            else:
                status = "fail" if any(v["sev"] == "Error" for v in items) else "warn"
                region = region_from_box(items[0]["box"], W, H)
                evidence = items[0].get("evidence")
                if len(items) > 1:
                    evidence = f"{evidence} (+{len(items) - 1} مواضع أخرى)" if evidence else f"{len(items)} مواضع"
                if items[0].get("rec"):
                    recommendation = items[0]["rec"]

        rules_out.append({
            "id": rid,
            "category": r["category"],
            "status": status,
            "title": r["title"],
            "description": r["description"],
            "recommendation": recommendation,
            "evidence": evidence,
            "region": region,
        })

    return {
        "id": f"aud_{abs(hash(url)) % 10_000_000}",
        "url": url,
        "scannedAt": datetime.now(timezone.utc).isoformat(),
        "durationSec": 0,
        "score": score,
        "grade": grade,
        "rules": rules_out,
        "screenshots": [
            {"label": "سطح المكتب", "viewport": "desktop", "url": f"/shots/{Path(page['shot']).name}",
             "width": W, "height": H},
        ],
    }


# ============ 5) نقطة الدخول ============
async def run_audit(url: str, gemini_api_key: str) -> dict:
    page = await capture_page(url)

    fviol = [e for e in page["fonts"] if APPROVED_FONT.lower() not in e["font"].lower()]
    rviol = check_radius(page["radii"])
    sviol = check_spacing(page["spacing"])

    client = genai.Client(api_key=gemini_api_key)
    vv = await run_visual_scan(client, page)

    return assemble_audit(url, page, fviol, rviol, sviol, vv)
