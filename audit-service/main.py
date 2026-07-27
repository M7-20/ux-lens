import os
import time

from dotenv import load_dotenv

load_dotenv()

import engine
import store
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

app = FastAPI(title="UX Lens Audit Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/shots", StaticFiles(directory=str(engine.SHOTS_DIR)), name="shots")


class AuditRequest(BaseModel):
    url: str


@app.get("/health")
def health():
    return {"ok": True, "gemini_key_set": bool(GEMINI_API_KEY)}


@app.post("/audit")
async def audit(req: AuditRequest):
    if not GEMINI_API_KEY:
        raise HTTPException(500, "GEMINI_API_KEY غير مضبوط — عدّل ملف audit-service/.env")
    t0 = time.time()
    try:
        result = await engine.run_audit(req.url, GEMINI_API_KEY)
    except Exception as e:
        raise HTTPException(500, f"فشل التدقيق: {e}")
    result["durationSec"] = round(time.time() - t0)
    store.save_audit({
        "url": result["url"],
        "scannedAt": result["scannedAt"],
        "score": result["score"],
        "durationSec": result["durationSec"],
    })
    return result


@app.get("/audits/recent")
def recent_audits(limit: int = 10):
    return store.recent(limit)


@app.get("/stats")
def stats():
    return store.stats()
