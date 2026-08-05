"""تحقق توكن واحة JWT + تزويد مستخدم فوري (waha/docs/ONBOARDING.md §5).

WAHA_SSO=off (الافتراضي): auth بلا تأثير فعلي، يرجّع مستخدم محلي مجهول — يخلي
UX Lens يشتغل مستقلاً بدون نشر واحة. لا تفعّل WAHA_SSO=on إلا خلف بوابة المنصة،
بعد ما يصير WAHA_PUBLIC_KEY_PATH يشير لمفتاح حقيقي.
"""
import functools
import os
import sqlite3
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request
from jose import JOSEError, jwt

import db

WAHA_KID = "waha-2026-07"
APP_ID = "uxlens"
SSO_ON = os.environ.get("WAHA_SSO", "off") == "on"


class User:
    def __init__(self, row) -> None:
        self.id = row["id"]
        self.waha_sub = row["waha_sub"]
        self.username = row["username"]
        self.name = row["name"]
        self.role = row["role"]
        self.is_active = bool(row["is_active"])


@functools.lru_cache(maxsize=1)
def _public_key() -> str:
    with open(os.environ["WAHA_PUBLIC_KEY_PATH"]) as fh:
        return fh.read()


def validate_waha_token(token: str) -> dict | None:
    """يرجّع claims أو None. أبداً ما يرمي استثناء — توكن سيء = 401 مو 500."""
    try:
        header = jwt.get_unverified_header(token)
    except JOSEError:
        return None
    if header.get("kid") != WAHA_KID:          # قرار #3: مطابقة kid فعلية
        return None
    try:
        claims = jwt.decode(token, _public_key(), algorithms=["RS256"])
    except JOSEError:
        return None
    return claims if claims.get("iss") == "waha" else None


def provision_or_update(conn: sqlite3.Connection, claims: dict, role: str) -> User:
    sub = claims["sub"]
    ad = claims.get("ad") or {}
    now = datetime.now(timezone.utc).isoformat()
    fields = (
        claims.get("username", ""), claims.get("name"), claims.get("name_ar"), role,
        ad.get("title"), ad.get("department"), ad.get("company"),
        ad.get("employee_id"), ad.get("email"),
    )
    try:
        conn.execute(
            "INSERT INTO users (waha_sub, username, name, name_ar, role, ad_title, "
            "ad_department, ad_company, ad_employee_id, ad_email, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (sub, *fields, now, now),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()   # سباق: طلب متزامن آخر أنشأ نفس الصف أول (خطأ §5.1 رقم 4)
    conn.execute(
        "UPDATE users SET username=?, name=?, name_ar=?, role=?, ad_title=?, "
        "ad_department=?, ad_company=?, ad_employee_id=?, ad_email=?, updated_at=? "
        "WHERE waha_sub=?",
        (*fields, now, sub),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM users WHERE waha_sub=?", (sub,)).fetchone()
    return User(row)


async def legacy_auth(request: Request, conn: sqlite3.Connection) -> User:
    return User({"id": 0, "waha_sub": "local", "username": "local", "name": None,
                 "role": "admin", "is_active": 1})


async def current_user(request: Request, conn: sqlite3.Connection = Depends(db.get_db)) -> User:
    if not SSO_ON:                              # قرار #5: يبوّب المسار كامل، مو الكوكي بس
        return await legacy_auth(request, conn)

    token = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
    token = token or request.cookies.get("waha_at")
    if not token:
        raise HTTPException(401, "not_authenticated")

    claims = validate_waha_token(token)
    if claims is None:
        raise HTTPException(401, "invalid_token")

    apps = claims.get("apps")
    if not isinstance(apps, dict) or APP_ID not in apps:
        raise HTTPException(403, "no_access")

    user = provision_or_update(conn, claims, role=apps[APP_ID])
    if not user.is_active:
        raise HTTPException(403, "inactive")
    return user
