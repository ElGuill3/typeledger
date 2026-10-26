"""Typing session: compares typed input with the target text and computes metrics."""

import enum
import time
from collections.abc import Callable, Sequence
from datetime import datetime

from typeledger.core.models import MODE_TIME, MODE_WORDS, CharStat, SessionResult

CHARS_PER_WORD = 5


class CharState(enum.Enum):
    PENDING = "pending"
    CORRECT = "correct"
    INCORRECT = "incorrect"


def _words_per_minute(chars: int, duration_s: float) -> float:
    if duration_s <= 0:
        return 0.0
    return chars / CHARS_PER_WORD / (duration_s / 60.0)


class TypingSession:
    """One practice run over a target text.

    Every `type_char` call is a keystroke. Backspace only moves the cursor
    back, so corrected errors still count against accuracy.
    """

    def __init__(
        self,
        target: str,
        *,
        mode: str,
        mode_value: int,
        language: str,
        layout_id: str,
        clock: Callable[[], float] = time.monotonic,
        now: Callable[[], datetime] = lambda: datetime.now().astimezone(),
    ):
        if mode not in (MODE_TIME, MODE_WORDS):
            raise ValueError(f"unknown mode: {mode!r}")
        self._target = target
        self._mode = mode
        self._mode_value = mode_value
        self._language = language
        self._layout_id = layout_id
        self._clock = clock
        self._now = now

        self._states = [CharState.PENDING] * len(target)
        self._position = 0
        self._keystrokes = 0
        self._correct_keystrokes = 0
        self._hits: dict[str, int] = {}
        self._misses: dict[str, int] = {}

        self._started_at: datetime | None = None
        self._start_time: float | None = None
        self._end_time: float | None = None
        self._result: SessionResult | None = None

    @property
    def target(self) -> str:
        return self._target

    @property
    def position(self) -> int:
        return self._position

    @property
    def states(self) -> Sequence[CharState]:
        return tuple(self._states)

    @property
    def started(self) -> bool:
        return self._start_time is not None

    @property
    def finished(self) -> bool:
        return self._end_time is not None

    @property
    def keystrokes(self) -> int:
        return self._keystrokes

    @property
    def correct_keystrokes(self) -> int:
        return self._correct_keystrokes

    def type_char(self, ch: str) -> bool:
        if self.finished or self._position >= len(self._target):
            return False
        if not self.started:
            self._start_time = self._clock()
            self._started_at = self._now()

        expected = self._target[self._position]
        correct = ch == expected
        self._keystrokes += 1
        if correct:
            self._correct_keystrokes += 1
            self._hits[expected] = self._hits.get(expected, 0) + 1
        else:
            self._misses[expected] = self._misses.get(expected, 0) + 1
        self._states[self._position] = (
            CharState.CORRECT if correct else CharState.INCORRECT
        )
        self._position += 1

        if self._mode == MODE_WORDS and self._position == len(self._target):
            self._end_time = self._clock()
        return correct

    def backspace(self) -> None:
        if self.finished or self._position == 0:
            return
        self._position -= 1
        self._states[self._position] = CharState.PENDING

    def extend(self, text: str) -> None:
        self._target += text
        self._states.extend([CharState.PENDING] * len(text))

    def elapsed(self) -> float:
        if self._start_time is None:
            return 0.0
        end = self._end_time if self._end_time is not None else self._clock()
        return end - self._start_time

    def is_time_up(self) -> bool:
        return self._mode == MODE_TIME and self.elapsed() >= self._mode_value

    def _duration(self) -> float:
        elapsed = self.elapsed()
        if self._mode == MODE_TIME:
            return min(elapsed, float(self._mode_value))
        return elapsed

    def _count(self, state: CharState) -> int:
        return sum(1 for s in self._states if s is state)

    def _accuracy(self) -> float:
        if self._keystrokes == 0:
            return 0.0
        return self._correct_keystrokes / self._keystrokes

    def live_wpm(self) -> float:
        return _words_per_minute(self._count(CharState.CORRECT), self._duration())

    def live_accuracy(self) -> float:
        return self._accuracy()

    def finish(self) -> SessionResult:
        if self._result is not None:
            return self._result
        if self._end_time is None:
            self._end_time = self._clock()
        if self._started_at is None:
            # Nothing was typed: zero duration, anchored at the finish moment.
            self._started_at = self._now()

        duration = self._duration()
        correct_chars = self._count(CharState.CORRECT)
        char_stats = {
            ch: CharStat(hits=self._hits.get(ch, 0), misses=self._misses.get(ch, 0))
            for ch in sorted(self._hits.keys() | self._misses.keys())
        }
        self._result = SessionResult(
            started_at=self._started_at,
            mode=self._mode,
            mode_value=self._mode_value,
            language=self._language,
            layout_id=self._layout_id,
            duration_s=duration,
            wpm=_words_per_minute(correct_chars, duration),
            raw_wpm=_words_per_minute(self._keystrokes, duration),
            accuracy=self._accuracy(),
            correct_chars=correct_chars,
            incorrect_chars=self._count(CharState.INCORRECT),
            keystrokes=self._keystrokes,
            char_stats=char_stats,
        )
        return self._result
