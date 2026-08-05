"""SQLite user store لتكامل waha JWT (auth.py). منفصل عن store.py — بيانات
ودورة حياة مختلفة تماماً (مستخدمون دائمون، مقابل سجل فحوصات append-only)."""
import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "users.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    waha_sub TEXT NOT NULL UNIQUE,
    username TEXT NOT NULL,
    name TEXT,
    name_ar TEXT,
    role TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    ad_title TEXT,
    ad_department TEXT,
    ad_company TEXT,
    ad_employee_id TEXT,
    ad_email TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

PERMISSIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS permissions (
    waha_sub TEXT PRIMARY KEY,
    role TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def _init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(SCHEMA)
    conn.execute(PERMISSIONS_SCHEMA)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(users)")}
    if "platform_admin" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN platform_admin INTEGER NOT NULL DEFAULT 0")
    conn.commit()
    conn.close()


_init_db()


def get_db():
    # check_same_thread=False: FastAPI can dispatch the async current_user() dependency
    # onto a different thread than this (sync) generator ran on within the same request —
    # the connection is still never shared *concurrently* across requests.
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
