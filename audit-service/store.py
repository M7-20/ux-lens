# Lightweight append-only history of completed audits — backs the homepage's
# "recent audits" list and aggregate stats. A JSON file is enough at this scale;
# swap for a real DB if usage grows.
import json
from pathlib import Path
from threading import Lock

HISTORY_PATH = Path(__file__).parent / "audits_history.json"
_lock = Lock()


def _load() -> list[dict]:
    if not HISTORY_PATH.exists():
        return []
    with open(HISTORY_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_audit(record: dict) -> None:
    with _lock:
        history = _load()
        history.append(record)
        tmp = HISTORY_PATH.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        tmp.replace(HISTORY_PATH)


def recent(limit: int = 10) -> list[dict]:
    history = _load()
    return list(reversed(history))[:limit]


def stats() -> dict:
    history = _load()
    if not history:
        return {"totalAudits": 0, "avgDurationSec": 0, "avgScore": 0}
    total = len(history)
    avg_duration = round(sum(h["durationSec"] for h in history) / total)
    avg_score = round(sum(h["score"] for h in history) / total)
    return {"totalAudits": total, "avgDurationSec": avg_duration, "avgScore": avg_score}
