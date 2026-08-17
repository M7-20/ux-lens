# طبقة القواعد البصرية لـ UX (تحتاج API الوزارة) — معزولة تماماً عن محرك DGA (engine.py).
# لا شيء هنا يستورد من engine.py (لا VISUAL_RULES، لا CODE_CHECKED، لا build_prompt، لا Violation،
# لا gen/to_box/dedup الخاصة بـ DGA) — كل الدوال المساعدة اللازمة مُعاد كتابتها محلياً هنا عمداً،
# حتى لو تشابهت المنطق، حفاظاً على استقلالية كاملة: حذف هذا الملف + تعطيل ENABLE_UX_LAYER
# لا يؤثران على DGA إطلاقاً. يستخدم نفس عميل الوزارة (OpenAI-compatible) الممرَّر من engine.py —
# إعادة استخدام الاتصال فقط، لا القواعد ولا البرومبت ولا منطق DGA.
import base64
import hashlib
import io
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from openai import APIConnectionError, APIStatusError, OpenAI
from PIL import Image

from ux.ux_checks import RULE_BY_ID, UX_RULES, region_from_box

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR.parent / "data"
DATA_DIR.mkdir(exist_ok=True)
CACHE_PATH = DATA_DIR / "ux_site_cache.json"

MINISTRY_VLM_API_KEY = os.environ.get("MINISTRY_VLM_API_KEY", "")
MINISTRY_VLM_BASE_URL = os.environ.get("MINISTRY_VLM_BASE_URL", "")
MINISTRY_VLM_MODEL = "vision"

TILE_HEIGHT = 1600
OVERLAP = 200
DEDUP_IOU = 0.5
MAX_TILES = 4

UX_VISUAL_RULES = [r for r in UX_RULES if r.get("detection") == "visual"]


def build_ux_visual_prompt() -> str:
    return f"""دقّق هذا الجزء من صفحة ويب مقابل مبادئ تجربة المستخدم (UX) العامة التالية باللغة العربية.
هذه مبادئ عامة لأي موقع (لا علاقة لها بهوية بصرية محددة) — احكم على وضوح التسلسل الهرمي، التباين الوظيفي، وسهولة الاستخدام البصري.
القواعد:
{chr(10).join(f"- {r['id']} ({r['category']}, {r['severity']}): {r['title']} — {r.get('detection_visual', r['description'])}" for r in UX_VISUAL_RULES)}
تنبيهات إلزامية — تمنع الأخطاء الشائعة على المواقع المختلفة:
1. الصور الفوتوغرافية وصور الأخبار والمحتوى الإعلامي: محتواها ليس جزءاً من واجهة الموقع — لا تُبلّغ عن مخالفات داخلها.
2. لا تُبلّغ عن عنصر بأنه "مفقود" إلا إذا فحصت الشريحة كاملة وتأكدت من غيابه.
3. إن لم تكن متأكداً من مخالفة، اجعل confidence "منخفضة" أو لا تذكرها إطلاقاً — الدقة أهم من العدد.
جميع الحقول النصية الحرة (evidence وrecommendation) يجب أن تكون بالكامل باللغة العربية الفصحى — ممنوع أي كلمة إنجليزية في evidence أو recommendation إلا أسماء تقنية لا مقابل عربي شائع لها (مثل CSS أو aria-current).
لكل مخالفة حدد الموقع عبر box_2d: تخيّل الصورة مقسّمة لشبكة 3×3 متساوية (يمين/وسط/يسار × أعلى/وسط/أسفل)، واختر اسم الخانة اللي يقع فيها مركز العنصر المخالف — قيمة واحدة فقط من: "أعلى-يسار", "أعلى-وسط", "أعلى-يمين", "وسط-يسار", "وسط-وسط", "وسط-يمين", "أسفل-يسار", "أسفل-وسط", "أسفل-يمين". لا تُرجِع إحداثيات رقمية أبداً.
مع كل مخالفة أضف أيضاً: rule_id + severity + confidence + evidence + recommendation.
لا تُرجِع مخالفة بدون دليل بصري واضح في evidence."""


PROMPT = build_ux_visual_prompt()
RULES_SIG = hashlib.md5((MINISTRY_VLM_MODEL + PROMPT).encode()).hexdigest()[:10]


def _load_cache() -> dict:
    return json.load(open(CACHE_PATH, encoding="utf-8")) if CACHE_PATH.exists() else {}


def _save_cache(cache: dict) -> None:
    tmp = CACHE_PATH.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)
    tmp.replace(CACHE_PATH)


def gen_ministry(client: OpenAI, **kw):
    for a in range(1, 5):
        try:
            return client.chat.completions.create(**kw)
        except (APIStatusError, APIConnectionError) as e:
            status = getattr(e, "status_code", None)
            if not (status is None or status >= 500 or status == 429) or a == 4:
                raise
            time.sleep(5 * a)


MINISTRY_VIOLATIONS_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "violations_response",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "violations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "box_2d": {
                                "type": "string",
                                "enum": [
                                    "أعلى-يسار", "أعلى-وسط", "أعلى-يمين",
                                    "وسط-يسار", "وسط-وسط", "وسط-يمين",
                                    "أسفل-يسار", "أسفل-وسط", "أسفل-يمين",
                                ],
                            },
                            "rule_id": {"type": "string"},
                            "severity": {"type": "string", "enum": ["Error", "Warning", "Info"]},
                            "confidence": {"type": "string", "enum": ["عالية", "متوسطة", "منخفضة"]},
                            "evidence": {"type": "string", "description": "بالعربي فقط"},
                            "recommendation": {"type": "string", "description": "بالعربي فقط"},
                        },
                        "required": ["box_2d", "rule_id", "severity", "confidence", "evidence", "recommendation"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["violations"],
            "additionalProperties": False,
        },
    },
}


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


GRID_CELLS = {
    "أعلى-يسار": [0, 0, 333, 333],
    "أعلى-وسط": [0, 333, 333, 667],
    "أعلى-يمين": [0, 667, 333, 1000],
    "وسط-يسار": [333, 0, 667, 333],
    "وسط-وسط": [333, 333, 667, 667],
    "وسط-يمين": [333, 667, 667, 1000],
    "أسفل-يسار": [667, 0, 1000, 333],
    "أسفل-وسط": [667, 333, 1000, 667],
    "أسفل-يمين": [667, 667, 1000, 1000],
}


def grid_to_box_2d(items: list[dict]) -> list[dict]:
    out = []
    for it in items:
        box = GRID_CELLS.get(it.get("box_2d"))
        if box is None:
            continue
        out.append({**it, "box_2d": box})
    return out


def overlap_frac(box, rects):
    x1, y1, x2, y2 = box
    area = max((x2 - x1) * (y2 - y1), 1)
    best = 0.0
    for b in rects:
        ox = max(0, min(x2, b["x"] + b["w"]) - max(x1, b["x"]))
        oy = max(0, min(y2, b["y"] + b["h"]) - max(y1, b["y"]))
        if ox <= 0 or oy <= 0:
            continue
        best = max(best, ox * oy / area)
    return best


def on_broken(box, broken):
    return overlap_frac(box, broken) >= 0.5


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
    kept = []
    for v in sorted(viols, key=lambda v: -(v["box"][2] - v["box"][0]) * (v["box"][3] - v["box"][1])):
        dup = next((k for k in kept if k["rule_id"] == v["rule_id"] and iou(k["box"], v["box"]) >= thr), None)
        if dup:
            if conf_rank.get(v["conf"], 0) > conf_rank.get(dup["conf"], 0):
                dup["conf"], dup["rec"] = v["conf"], v["rec"]
            continue
        kept.append(dict(v))
    return kept


def _scan_sync(client: OpenAI, page: dict) -> list[dict]:
    """يُنفَّذ في thread منفصل (نفس أسلوب DGA) — لا يُستدعى مباشرة من كود async."""
    if not UX_VISUAL_RULES:
        return []

    W, H = page["shot_width"], page["shot_height"]
    th = TILE_HEIGHT
    tiles = make_tiles(H, th, OVERLAP)
    if len(tiles) > MAX_TILES:
        th = -(-H // MAX_TILES) + OVERLAP
        tiles = make_tiles(H, th, OVERLAP)

    cache = _load_cache()
    full_image = Image.open(page["shot"]).convert("RGB")

    def analyze(i, y0, y1):
        crop = full_image.crop((0, y0, W, y1))
        key = f"{page['name']}|{W}x{H}|{i}|{RULES_SIG}|" + hashlib.md5(crop.tobytes()).hexdigest()[:10]
        if key in cache:
            return i, key, cache[key], True, True
        tile_note = f"\n(هذه الشريحة {i + 1} من {len(tiles)} من صفحة طويلة)"
        time.sleep(0.8 * i)
        try:
            buf = io.BytesIO()
            crop.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode()
            r = gen_ministry(client, model=MINISTRY_VLM_MODEL, temperature=0, max_tokens=8192, timeout=30,
                    reasoning_effort="none",
                    response_format=MINISTRY_VIOLATIONS_SCHEMA,
                    messages=[
                        {"role": "system", "content": "Return violations as JSON object {\"violations\": [...]}. ALL text fields (evidence, recommendation) MUST be written entirely in Arabic — no English words except untranslatable technical terms. No masks. Max 10."},
                        {"role": "user", "content": [
                            {"type": "text", "text": PROMPT + tile_note},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                        ]},
                    ])
            items = grid_to_box_2d(json.loads(r.choices[0].message.content)["violations"])
            ok = True
        except Exception:
            items, ok = [], False
        return i, key, items, False, ok

    with ThreadPoolExecutor(max_workers=min(2, len(tiles))) as ex:
        results = sorted(ex.map(lambda a: analyze(*a), [(i, y0, y1) for i, (y0, y1) in enumerate(tiles)]))

    fresh = [(k, it) for _, k, it, cached, ok in results if not cached and ok]
    if fresh:
        for k, it in fresh:
            cache[k] = it
        _save_cache(cache)

    # لا نخمّن "pass" لقاعدة لم نتمكن من تحليلها فعلياً — إذا فشلت كل الشرائح (لا كاش ولا استدعاء
    # ناجح)، الاستدعاء يرجع بلا نتائج، وrun_ux_visual_checks يُبلّغ "undetermined" بدل "pass".
    any_success = any(ok for _, _, _, _, ok in results)

    visual_ids = {r["id"] for r in UX_VISUAL_RULES}
    vv = []
    for i, _key, items, _cached, _ok in results:
        y0, y1 = tiles[i]
        for it in items:
            rid = it.get("rule_id", "")
            if rid not in visual_ids:
                continue
            box = to_box(it, W, y1 - y0, y0)
            if not box:
                continue
            if on_broken(box, page.get("broken", [])):
                continue
            vv.append({"box": box, "rule_id": rid, "sev": it["severity"],
                       "conf": it["confidence"], "rec": it.get("recommendation"),
                       "evidence": it.get("evidence")})

    return dedup(vv, DEDUP_IOU), any_success


def run_ux_visual_checks(client: OpenAI, page: dict) -> tuple[list[dict], bool]:
    """يرجع (قائمة نتائج بنفس شكل مخرجات run_ux_checks، هل نجح تحليل بصري واحد على الأقل).
    القائمة بنفس شكل id/category/status/title/description/recommendation/evidence/region/source='UX'
    — لكل الـ7 قواعد البصرية دائماً، بلا أي استدعاء لكود DGA.
    إذا فشل التحليل البصري بالكامل، القواعد السبع تُبلَّغ 'undetermined' لا 'pass' — لا تخمين،
    والعنصر الثاني بالمُرجَع يكون False ليعرف المستدعي إن هذي النتيجة غير موثوقة."""
    W, H = page["shot_width"], page["shot_height"]
    out: list[dict] = []

    if not UX_VISUAL_RULES:
        return out, True

    findings, any_success = _scan_sync(client, page)

    if not any_success:
        for r in UX_VISUAL_RULES:
            out.append({
                "id": r["id"], "category": r["category"], "status": "undetermined",
                "title": r["title"], "description": r["description"],
                "recommendation": r.get("recommendation"),
                "evidence": "تعذّر تحليل الصفحة بصرياً عبر API الوزارة لتقييم هذه القاعدة (فشل الاتصال أو التحليل في كل الشرائح).",
                "region": None, "source": "UX",
            })
        return out, False

    by_rule: dict[str, list[dict]] = {}
    for v in findings:
        by_rule.setdefault(v["rule_id"], []).append(v)

    for r in UX_VISUAL_RULES:
        items = by_rule.get(r["id"], [])
        violated = bool(items)
        status = "pass" if not violated else ("fail" if r["severity"] == "Error" else "warn")
        region = region_from_box_pixels(items[0]["box"], W, H) if violated else None
        evidence = items[0].get("evidence") if violated else None
        if violated and len(items) > 1:
            evidence = f"{evidence} (+{len(items) - 1} مواضع أخرى)" if evidence else f"{len(items)} مواضع"
        recommendation = r.get("recommendation")
        if violated and items[0].get("rec"):
            recommendation = items[0]["rec"]
        out.append({
            "id": r["id"], "category": r["category"], "status": status,
            "title": r["title"], "description": r["description"],
            "recommendation": recommendation,
            "evidence": evidence, "region": region,
            "source": "UX",
        })
    return out, True


def region_from_box_pixels(box, W, H):
    x1, y1, x2, y2 = box
    return region_from_box({"x": x1, "y": y1, "w": x2 - x1, "h": y2 - y1}, W, H)
