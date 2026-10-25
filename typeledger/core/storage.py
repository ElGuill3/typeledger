"""SQLite persistence for completed practice sessions.

Streaks and charts are derived from these tables; nothing derived is stored.
"""

import math
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from typeledger.core.models import LANGUAGES, MODE_TIME, MODE_WORDS, CharStat, SessionResult

APP_DIR_NAME = "typeledger"
DB_FILE_NAME = "typeledger.db"


def default_db_path() -> Path:
    """Return `<user data dir>/typeledger/typeledger.db` without creating it.

    Mirrors GLib's user data dir (and Flatpak's per-app dir, which sets
    XDG_DATA_HOME) without importing GLib.
    """
    data_home = os.environ.get("XDG_DATA_HOME")
    base = Path(data_home) if data_home else Path.home() / ".local" / "share"
    return base / APP_DIR_NAME / DB_FILE_NAME


def _migrate_v1(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE sessions (
            id INTEGER PRIMARY KEY,
            started_at TEXT NOT NULL,
            started_at_utc TEXT NOT NULL,
            local_date TEXT NOT NULL,
            mode TEXT NOT NULL CHECK (mode IN ('time', 'words')),
            mode_value INTEGER NOT NULL CHECK (mode_value > 0),
            language TEXT NOT NULL,
            layout_id TEXT NOT NULL,
            duration_s REAL NOT NULL CHECK (duration_s >= 0),
            wpm REAL NOT NULL CHECK (wpm >= 0),
            raw_wpm REAL NOT NULL CHECK (raw_wpm >= 0),
            accuracy REAL NOT NULL CHECK (accuracy BETWEEN 0 AND 1),
            correct_chars INTEGER NOT NULL CHECK (correct_chars >= 0),
            incorrect_chars INTEGER NOT NULL CHECK (incorrect_chars >= 0),
            keystrokes INTEGER NOT NULL CHECK (keystrokes >= 0)
        )
        """
    )
    conn.execute("CREATE INDEX sessions_started_at_utc ON sessions (started_at_utc)")
    conn.execute("CREATE INDEX sessions_local_date ON sessions (local_date)")
    conn.execute(
        """
        CREATE TABLE key_stats (
            session_id INTEGER NOT NULL REFERENCES sessions (id) ON DELETE CASCADE,
            char TEXT NOT NULL CHECK (length(char) > 0),
            hits INTEGER NOT NULL CHECK (hits >= 0),
            misses INTEGER NOT NULL CHECK (misses >= 0),
            PRIMARY KEY (session_id, char)
        )
        """
    )


# Step N (1-based) upgrades the schema from user_version N-1 to N. Append only.
MIGRATIONS: list[Callable[[sqlite3.Connection], None]] = [_migrate_v1]


@dataclass(frozen=True)
class StoredSession:
    id: int
    result: SessionResult


def _check_count(name: str, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer, got {value!r}")


def _check_amount(name: str, value: object) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < 0
    ):
        raise ValueError(f"{name} must be a finite non-negative number, got {value!r}")


def _validate(result: SessionResult) -> None:
    if not isinstance(result.started_at, datetime) or result.started_at.utcoffset() is None:
        raise ValueError("started_at must be a timezone-aware datetime")
    if result.mode not in (MODE_TIME, MODE_WORDS):
        raise ValueError(f"unknown mode {result.mode!r}")
    _check_count("mode_value", result.mode_value)
    if result.mode_value == 0:
        raise ValueError("mode_value must be positive")
    if result.language not in LANGUAGES:
        raise ValueError(f"unknown language {result.language!r}")
    if not isinstance(result.layout_id, str) or not result.layout_id:
        raise ValueError("layout_id must be a non-empty string")
    for name in ("duration_s", "wpm", "raw_wpm", "accuracy"):
        _check_amount(name, getattr(result, name))
    if result.accuracy > 1:
        raise ValueError(f"accuracy must be within [0, 1], got {result.accuracy!r}")
    for name in ("correct_chars", "incorrect_chars", "keystrokes"):
        _check_count(name, getattr(result, name))
    for char, stat in result.char_stats.items():
        if not isinstance(char, str) or not char:
            raise ValueError(f"char_stats key must be a non-empty string, got {char!r}")
        if not isinstance(stat, CharStat):
            raise ValueError(f"char_stats[{char!r}] must be a CharStat, got {stat!r}")
        _check_count(f"char_stats[{char!r}].hits", stat.hits)
        _check_count(f"char_stats[{char!r}].misses", stat.misses)


class Storage:
    """Session store backed by one SQLite file (or ":memory:")."""

    def __init__(self, path: str | os.PathLike[str]):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        # Autocommit mode: transactions are opened explicitly with BEGIN.
        self._conn = sqlite3.connect(path, isolation_level=None)
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._migrate()

    def _migrate(self) -> None:
        version = self._conn.execute("PRAGMA user_version").fetchone()[0]
        for target, step in enumerate(MIGRATIONS[version:], start=version + 1):
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                step(self._conn)
                # PRAGMA does not accept bound parameters; target is an int from code.
                self._conn.execute(f"PRAGMA user_version = {int(target)}")
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise
            self._conn.execute("COMMIT")

    def save_session(self, result: SessionResult) -> int:
        """Validate and insert a session with its key stats atomically."""
        _validate(result)
        started_at = result.started_at
        self._conn.execute("BEGIN")
        try:
            cursor = self._conn.execute(
                """
                INSERT INTO sessions (
                    started_at, started_at_utc, local_date, mode, mode_value,
                    language, layout_id, duration_s, wpm, raw_wpm, accuracy,
                    correct_chars, incorrect_chars, keystrokes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    started_at.isoformat(),
                    started_at.astimezone(timezone.utc).isoformat(),
                    # started_at carries the local offset, so its own date is the local day.
                    started_at.date().isoformat(),
                    result.mode,
                    result.mode_value,
                    result.language,
                    result.layout_id,
                    float(result.duration_s),
                    float(result.wpm),
                    float(result.raw_wpm),
                    float(result.accuracy),
                    result.correct_chars,
                    result.incorrect_chars,
                    result.keystrokes,
                ),
            )
            session_id = cursor.lastrowid
            self._conn.executemany(
                "INSERT INTO key_stats (session_id, char, hits, misses) VALUES (?, ?, ?, ?)",
                [
                    (session_id, char, stat.hits, stat.misses)
                    for char, stat in result.char_stats.items()
                ],
            )
        except BaseException:
            self._conn.execute("ROLLBACK")
            raise
        self._conn.execute("COMMIT")
        return session_id

    def list_sessions(self, limit: int | None = None) -> list[StoredSession]:
        """Return stored sessions, newest first, optionally capped at `limit`."""
        if limit is not None and (isinstance(limit, bool) or not isinstance(limit, int) or limit < 0):
            raise ValueError(f"limit must be a non-negative integer or None, got {limit!r}")
        newest = "SELECT id FROM sessions ORDER BY started_at_utc DESC, id DESC LIMIT ?"
        params = (-1 if limit is None else limit,)
        rows = self._conn.execute(
            f"""
            SELECT id, started_at, mode, mode_value, language, layout_id,
                   duration_s, wpm, raw_wpm, accuracy,
                   correct_chars, incorrect_chars, keystrokes
            FROM sessions
            WHERE id IN ({newest})
            ORDER BY started_at_utc DESC, id DESC
            """,
            params,
        ).fetchall()
        stats: dict[int, dict[str, CharStat]] = {row[0]: {} for row in rows}
        for session_id, char, hits, misses in self._conn.execute(
            f"SELECT session_id, char, hits, misses FROM key_stats "
            f"WHERE session_id IN ({newest}) ORDER BY session_id, char",
            params,
        ):
            stats[session_id][char] = CharStat(hits=hits, misses=misses)
        return [
            StoredSession(
                id=row[0],
                result=SessionResult(
                    started_at=datetime.fromisoformat(row[1]),
                    mode=row[2],
                    mode_value=row[3],
                    language=row[4],
                    layout_id=row[5],
                    duration_s=row[6],
                    wpm=row[7],
                    raw_wpm=row[8],
                    accuracy=row[9],
                    correct_chars=row[10],
                    incorrect_chars=row[11],
                    keystrokes=row[12],
                    char_stats=stats[row[0]],
                ),
            )
            for row in rows
        ]

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "Storage":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()
