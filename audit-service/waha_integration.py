"""System Integration API لواحة (waha ONBOARDING.md §6) — إلزامي للانضمام.
عقد ذاتي الوصف: نصرّح نحن بالـobjects/roles، وواحة تعرضها بواجهتها بدون
ما تعرف شيء عن تفاصيل UX Lens الداخلية.
"""
import sqlite3
from datetime import datetime, timezone

import db
from auth import User, current_user
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/waha")

APP_ID = "uxlens"

ROLE_LABELS = {
    "viewer": {"en": "Viewer", "ar": "مشاهد"},
    "editor": {"en": "Editor", "ar": "محرر"},
}


def _bilingual_name(name: str | None, name_ar: str | None, email: str | None) -> dict:
    """سلسلة احتياط autoglean's _display_name: لغة الاسم نفسها، ثم اللغة الأخرى،
    ثم الجزء المحلي من البريد — أبداً ما ترجع فاضية."""
    local = (email.split("@")[0] if email else "") or "user"
    return {"en": name or name_ar or local, "ar": name_ar or name or local}


def _resolve_target(caller: User, sub: str | None) -> str:
    """قاعدة §6 الموحّدة: كل واحد يقرأ/يكتب بياناته، واستهداف sub غيره يحتاج
    platform_admin=true وإلا 403. /profile بدون sub و/profile/{sub}=نفس caller
    يُعاملان بنفس الطريقة تماماً (autoglean's _resolve_target)."""
    target = sub or caller.waha_sub
    if target != caller.waha_sub and not caller.platform_admin:
        raise HTTPException(403, "platform_admin required to access another user's data")
    return target


class GrantsBody(BaseModel):
    grants: list[dict]


@router.get("/profile")
@router.get("/profile/{sub}")
async def profile(sub: str | None = None, user: User = Depends(current_user),
                   conn: sqlite3.Connection = Depends(db.get_db)):
    # لازم يرد <2s وأبداً ما يرمي 500 — أسوأ حالة بروفايل شبه فاضٍ (app_id بس).
    # 403/404 مقصودان ومُوثَّقان بـ§6، يُعاد رميهما كما هم؛ فقط الأخطاء غير المتوقعة تُلتقط.
    try:
        target = _resolve_target(user, sub)
        row = conn.execute("SELECT * FROM users WHERE waha_sub=?", (target,)).fetchone()
        if row is None:
            raise HTTPException(404, "not_found")   # لم نرَ هذا المستخدم قط — قاعدة §6
        return {
            "app_id": APP_ID,
            "identity": {
                "display_name": _bilingual_name(row["name"], row["name_ar"], row["ad_email"]),
                "email": row["ad_email"],
                "role": row["role"],
                "role_label": ROLE_LABELS.get(row["role"]),
                "department": ({"en": row["ad_department"], "ar": row["ad_department"]}
                                if row["ad_department"] else None),
            },
        }
    except HTTPException:
        raise
    except Exception:
        return {"app_id": APP_ID}


@router.get("/permissions/schema")
async def permissions_schema():
    """بدون auth عمداً — وصف عام لما يقدر النظام يمنحه، مو بيانات مستخدم."""
    return {
        "app_id": APP_ID,
        "objects": [{
            "key": "app",
            "label": {"en": "UX Lens", "ar": "UX Lens"},
            "roles": [{"key": k, "label": v} for k, v in ROLE_LABELS.items()],
        }],
    }


@router.get("/permissions/{sub}")
async def get_permissions(sub: str, user: User = Depends(current_user),
                           conn: sqlite3.Connection = Depends(db.get_db)):
    target = _resolve_target(user, sub)
    row = conn.execute("SELECT role FROM permissions WHERE waha_sub=?", (target,)).fetchone()
    return {"grants": [{"object": "app", "role": row["role"]}] if row else []}


@router.put("/permissions/{sub}")
async def put_permissions(sub: str, body: GrantsBody, user: User = Depends(current_user),
                           conn: sqlite3.Connection = Depends(db.get_db)):
    target = _resolve_target(user, sub)
    if len(body.grants) > 1:
        raise HTTPException(422, "at most one grant supported (single 'app' object)")
    for g in body.grants:
        if g.get("object") != "app" or g.get("role") not in ROLE_LABELS:
            raise HTTPException(422, f"invalid grant: {g}")
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("DELETE FROM permissions WHERE waha_sub=?", (target,))
    if body.grants:
        conn.execute("INSERT INTO permissions (waha_sub, role, updated_at) VALUES (?,?,?)",
                     (target, body.grants[0]["role"], now))
    conn.commit()
    return {"grants": body.grants}
