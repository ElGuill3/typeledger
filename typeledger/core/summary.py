"""JSON summary of the practice history for the GNOME Shell panel extension.

The extension never reads SQLite; it reads this file (schema v1). Field
names and types are a contract with the extension: change them only with
a new schema version.
"""

import json
import os
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

from .models import SessionResult
from .progress import overview, session_day
from .storage import default_db_path

SCHEMA_VERSION = 1
SUMMARY_FILE_NAME = "summary.json"
RECENT_DAYS = 7
MAX_PRACTICED_DAYS = 400


def default_summary_path() -> Path:
    """Return `<user data dir>/typeledger/summary.json` without creating it."""
    return default_db_path().parent / SUMMARY_FILE_NAME


def build_summary(results: Iterable[SessionResult], *, today: date, now: datetime) -> dict:
    """Schema v1 summary; days are local dates, the most recent 400 at most."""
    results = list(results)
    stats = overview(results, today, recent_days=RECENT_DAYS)
    days = sorted({session_day(r) for r in results if session_day(r) <= today})
    return {
        "schema": SCHEMA_VERSION,
        "generated_at": now.isoformat(),
        "practiced_days": [day.isoformat() for day in days[-MAX_PRACTICED_DAYS:]],
        "longest_streak": stats.streak.longest,
        "total_sessions": stats.total_sessions,
        "recent_days": RECENT_DAYS,
        "recent_avg_wpm": float(stats.recent_avg_wpm),
        "recent_avg_accuracy": float(stats.recent_avg_accuracy),
        "recent_sessions": stats.recent_sessions,
    }


def write_summary(summary: dict, path: Path) -> None:
    """Write `summary` as UTF-8 JSON, atomically replacing `path`.

    Raises OSError when the file cannot be written.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as temp:
            json.dump(summary, temp, ensure_ascii=False, indent=2)
            temp.write("\n")
            temp.flush()
            os.fsync(temp.fileno())
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def export_summary(storage, path=None, *, today=None, now=None) -> Path:
    """Build the summary from `storage` and write it; returns the written path."""
    if now is None:
        now = datetime.now().astimezone()
    if today is None:
        today = now.date()
    path = default_summary_path() if path is None else Path(path)
    results = [stored.result for stored in storage.list_sessions()]
    write_summary(build_summary(results, today=today, now=now), path)
    return path
