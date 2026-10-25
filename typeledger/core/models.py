"""Data shared between the typing engine and storage."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping

MODE_TIME = "time"
MODE_WORDS = "words"

TIME_OPTIONS = (15, 30, 60, 120)
WORD_OPTIONS = (10, 25, 50, 100)
LANGUAGES = ("en", "es")


@dataclass(frozen=True)
class CharStat:
    """How often one expected character was typed right or wrong."""

    hits: int = 0
    misses: int = 0


@dataclass(frozen=True)
class SessionResult:
    """Outcome of one completed practice session."""

    started_at: datetime  # timezone-aware, local time
    mode: str  # MODE_TIME or MODE_WORDS
    mode_value: int  # seconds for MODE_TIME, word count for MODE_WORDS
    language: str
    layout_id: str
    duration_s: float
    wpm: float  # correct chars / 5 per minute
    raw_wpm: float  # all typed chars / 5 per minute
    accuracy: float  # correct keystrokes / total keystrokes, 0.0-1.0
    correct_chars: int
    incorrect_chars: int
    keystrokes: int
    char_stats: Mapping[str, CharStat] = field(default_factory=dict)
