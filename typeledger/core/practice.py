"""One practice run: builds the text, feeds input to the engine, saves results."""

import re
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from typeledger.core.engine import TypingSession
from typeledger.core.layout import KeyboardLayout, load_layout
from typeledger.core.models import MODE_TIME, SessionResult
from typeledger.core.storage import Storage
from typeledger.core.textgen import generate_text

# Time mode starts with this many words and appends more as the cursor nears the end.
TIME_MODE_INITIAL_WORDS = 60
TIME_MODE_EXTRA_WORDS = 30
TIME_MODE_EXTEND_MARGIN = 40

_LAYER_KEY = re.compile(r"^MO\((\d+)\)$")


@dataclass(frozen=True)
class PracticeSettings:
    language: str
    mode: str
    mode_value: int
    layout_id: str


class Practice:
    def __init__(
        self,
        settings: PracticeSettings,
        storage: Storage,
        *,
        rng=None,
        clock: Callable[[], float] = time.monotonic,
        now: Callable[[], datetime] = lambda: datetime.now().astimezone(),
    ):
        self._storage = storage
        self._rng = rng
        self._clock = clock
        self._now = now
        self.restart(settings)

    def restart(self, settings: PracticeSettings | None = None) -> None:
        if settings is not None:
            self.settings = settings
            self.layout: KeyboardLayout = load_layout(settings.layout_id)
        word_count = (
            TIME_MODE_INITIAL_WORDS
            if self.settings.mode == MODE_TIME
            else self.settings.mode_value
        )
        self.session = TypingSession(
            generate_text(self.settings.language, word_count, rng=self._rng),
            mode=self.settings.mode,
            mode_value=self.settings.mode_value,
            language=self.settings.language,
            layout_id=self.settings.layout_id,
            clock=self._clock,
            now=self._now,
        )
        self.last_result: SessionResult | None = None
        self.save_error: Exception | None = None

    def type_text(self, text: str) -> bool:
        """Feed typed text; returns True when this input completed the session."""
        if self.last_result is not None:
            return False
        for char in text:
            self._ensure_text_ahead()
            self.session.type_char(char)
            if self.session.finished:
                self.complete()
                return True
        return False

    def backspace(self) -> None:
        if self.last_result is None:
            self.session.backspace()

    def tick(self) -> bool:
        """Call periodically; returns True when the time limit just completed the session."""
        if self.last_result is not None or not self.session.started:
            return False
        if self.session.is_time_up():
            self.complete()
            return True
        return False

    def complete(self) -> SessionResult:
        if self.last_result is None:
            result = self.session.finish()
            if result.keystrokes > 0:
                try:
                    self._storage.save_session(result)
                except (sqlite3.Error, ValueError) as error:
                    self.save_error = error
            self.last_result = result
        return self.last_result

    def hint_for(self, char: str) -> tuple[int, tuple[str, ...]]:
        """Layer to display and keys to press for `char`."""
        keys = self.layout.keys_for_char(char)
        base_labels = self.layout.layers[0]
        index_by_id = {key.id: index for index, key in enumerate(self.layout.keys)}
        for key_id in keys:
            match = _LAYER_KEY.match(base_labels[index_by_id[key_id]])
            if match:
                return int(match.group(1)), keys
        return 0, keys

    def next_hint(self) -> tuple[int, tuple[str, ...]]:
        session = self.session
        if self.last_result is not None or session.position >= len(session.target):
            return 0, ()
        return self.hint_for(session.target[session.position])

    def _ensure_text_ahead(self) -> None:
        if self.settings.mode != MODE_TIME:
            return
        remaining = len(self.session.target) - self.session.position
        if remaining < TIME_MODE_EXTEND_MARGIN:
            extra = generate_text(
                self.settings.language, TIME_MODE_EXTRA_WORDS, rng=self._rng
            )
            self.session.extend(" " + extra)
