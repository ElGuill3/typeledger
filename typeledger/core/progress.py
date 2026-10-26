"""Progress statistics derived from saved sessions.

Pure functions over ``SessionResult`` values (e.g. ``Storage.list_sessions()``).
A session's day is the local date of ``started_at``.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable, Mapping

from .layout import KeyboardLayout
from .models import SessionResult


@dataclass(frozen=True)
class Streak:
    current: int  # consecutive days ending today, or yesterday if today is not done yet
    longest: int
    practiced_today: bool


@dataclass(frozen=True)
class CharErrorRate:
    char: str
    hits: int
    misses: int
    rate: float  # misses / (hits + misses)


@dataclass(frozen=True)
class Overview:
    streak: Streak
    total_sessions: int
    total_seconds: float
    best_wpm: float
    recent_avg_wpm: float
    recent_avg_accuracy: float
    recent_sessions: int


def session_day(result: SessionResult) -> date:
    return result.started_at.date()


def compute_streak(days: Iterable[date], today: date) -> Streak:
    """Streaks over practiced days; duplicates are fine and future days are ignored."""
    practiced = {day for day in days if day <= today}
    if not practiced:
        return Streak(0, 0, False)

    longest = 0
    run = 0
    previous = None
    for day in sorted(practiced):
        run = run + 1 if previous is not None and day - previous == timedelta(days=1) else 1
        longest = max(longest, run)
        previous = day

    practiced_today = today in practiced
    current = 0
    day = today if practiced_today else today - timedelta(days=1)
    while day in practiced:
        current += 1
        day -= timedelta(days=1)
    return Streak(current, longest, practiced_today)


def sessions_in_range(
    results: Iterable[SessionResult], *, days: int, today: date
) -> list[SessionResult]:
    """Sessions of the ``days`` days ending at ``today``, oldest first.

    Sessions with the same ``started_at`` keep their input order.
    """
    first = today - timedelta(days=days - 1)
    picked = [r for r in results if first <= session_day(r) <= today]
    return sorted(picked, key=lambda r: r.started_at)


def char_error_rates(
    results: Iterable[SessionResult], *, min_samples: int = 5
) -> dict[str, CharErrorRate]:
    """Per-character error rate over all ``results``.

    Characters with fewer than ``min_samples`` hits + misses are omitted.
    The space character is kept; ``key_heat`` paints it on the Space key.
    """
    hits = defaultdict(int)
    misses = defaultdict(int)
    for result in results:
        for ch, stat in result.char_stats.items():
            hits[ch] += stat.hits
            misses[ch] += stat.misses

    rates = {}
    for ch in hits.keys() | misses.keys():
        total = hits[ch] + misses[ch]
        if total < min_samples or total == 0:
            continue
        rates[ch] = CharErrorRate(ch, hits[ch], misses[ch], misses[ch] / total)
    return rates


def key_heat(layout: KeyboardLayout, rates: Mapping[str, CharErrorRate]) -> dict[str, float]:
    """Heat 0..1 per key id: the max rate of the chars it types, over the hottest key.

    Only the char key is heated (not Shift or layer keys). Unreachable chars
    are skipped. All-zero levels give an empty dict.
    """
    levels = {}
    for ch, rate in rates.items():
        key_ids = layout.keys_for_char(ch)
        if not key_ids:
            continue
        key_id = key_ids[-1]
        levels[key_id] = max(levels.get(key_id, 0.0), rate.rate)

    highest = max(levels.values(), default=0.0)
    if highest <= 0.0:
        return {}
    return {key_id: level / highest for key_id, level in levels.items() if level > 0.0}


def overview(results: Iterable[SessionResult], today: date, *, recent_days: int = 7) -> Overview:
    """Totals over all history plus averages over the last ``recent_days`` days."""
    results = list(results)
    first_recent = today - timedelta(days=recent_days - 1)
    recent = [r for r in results if first_recent <= session_day(r) <= today]
    return Overview(
        streak=compute_streak((session_day(r) for r in results), today),
        total_sessions=len(results),
        total_seconds=sum(r.duration_s for r in results),
        best_wpm=max((r.wpm for r in results), default=0.0),
        recent_avg_wpm=_mean(r.wpm for r in recent),
        recent_avg_accuracy=_mean(r.accuracy for r in recent),
        recent_sessions=len(recent),
    )


def _mean(values: Iterable[float]) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0
