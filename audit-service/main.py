import asyncio
import os
import time

from dotenv import load_dotenv

load_dotenv()

import engine
import store
import vision_provider
import waha_integration
from auth import current_user
from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="UX Lens Audit Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# كل شي تحت /api — البوابة (nginx) تشيل بادئة /uxlens وتترك /api/... كما هي
# (waha ONBOARDING.md §1: "proxy_pass http://127.0.0.1:<PORT>/api/;")
app.mount("/api/shots", StaticFiles(directory=str(engine.SHOTS_DIR)), name="shots")
api = APIRouter(prefix="/api")


class AuditRequest(BaseModel):
    url: str


@api.get("/health")
def health():
    try:
        vision_provider.get_vision_provider()
        vision_configured = True
    except RuntimeError:
        vision_configured = False
    return {
        "ok": True,
        "vision_provider": os.environ.get("VISION_PROVIDER", "gemini").strip().lower(),
        "vision_configured": vision_configured,
    }


@api.post("/audit")
async def audit(req: AuditRequest, user=Depends(current_user)):
    try:
        provider = vision_provider.get_vision_provider()
    except RuntimeError as e:
        raise HTTPException(500, f"مزوّد الرؤية غير مضبوط: {e}")
    t0 = time.time()
    try:
        result = await asyncio.wait_for(engine.run_audit(req.url, provider), timeout=300)
    except asyncio.TimeoutError:
        raise HTTPException(504, "تجاوز الفحص المهلة القصوى (5 دقائق) وأُلغي.")
    except Exception as e:
        raise HTTPException(500, f"فشل التدقيق: {e}")
    result["durationSec"] = round(time.time() - t0)
    tally = {"pass": 0, "warn": 0, "fail": 0, "manual_review": 0}
    for r in result["rules"]:
        tally[r["status"]] = tally.get(r["status"], 0) + 1
    dga_rules = [r for r in result["rules"] if r.get("source") != "UX"]
    ux_rules = [r for r in result["rules"] if r.get("source") == "UX"]
    dga_pass_count = sum(1 for r in dga_rules if r["status"] == "pass")
    ux_pass_count = sum(1 for r in ux_rules if r["status"] == "pass")
    store.save_audit({
        "url": result["url"],
        "scannedAt": result["scannedAt"],
        "score": result["score"],
        "scoreEstimated": result["scoreEstimated"],
        "dgaScore": result.get("dgaScore"),
        "uxScore": result.get("uxScore"),
        "dgaPassCount": dga_pass_count,
        "dgaTotalCount": len(dga_rules),
        "uxPassCount": ux_pass_count,
        "uxTotalCount": len(ux_rules),
        "durationSec": result["durationSec"],
        "tally": tally,
        "reportPath": result["screenshots"][0]["url"] if result["screenshots"] else None,
    })
    return result


@api.get("/audits/recent")
def recent_audits(limit: int = 10, user=Depends(current_user)):
    return store.recent(limit)


@api.get("/stats")
def stats(user=Depends(current_user)):
    return store.stats()


app.include_router(api)
app.include_router(waha_integration.router)
