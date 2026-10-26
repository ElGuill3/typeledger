"""Line wrapping and Pango markup for the practice text."""

import html
import re
from collections.abc import Sequence

from typeledger.core.engine import CharState

ERROR_COLOR = "#e01b24"
DEFAULT_ACCENT = "#3584e4"
WRONG_SPACE = "·"
NEWLINE_MARK = "⏎"

_TOKEN = re.compile(r"\S+\s*|\s+")


def wrap_lines(text: str, width: int) -> list[tuple[int, int]]:
    """Greedy word wrap returning [start, end) spans that cover `text` exactly.

    Spaces stay at the end of the line they follow, so cursor positions map
    to exactly one line. Words longer than `width` are hard-split. A newline
    always ends its line and belongs to it.
    """
    if width <= 0:
        raise ValueError("width must be positive")
    lines: list[tuple[int, int]] = []
    segment_start = 0
    while (newline := text.find("\n", segment_start)) != -1:
        _wrap_segment(text, segment_start, newline + 1, width, lines)
        segment_start = newline + 1
    if segment_start < len(text) or not lines:
        _wrap_segment(text, segment_start, len(text), width, lines)
    return lines


def _wrap_segment(
    text: str, segment_start: int, segment_end: int, width: int, lines: list
) -> None:
    line_start = segment_start
    for match in _TOKEN.finditer(text, segment_start, segment_end):
        start = match.start()
        word_len = len(match.group().rstrip())
        while word_len > width:
            if start > line_start:
                lines.append((line_start, start))
            lines.append((start, start + width))
            start += width
            word_len -= width
            line_start = start
        if start > line_start and (start - line_start) + word_len > width:
            lines.append((line_start, start))
            line_start = start
    lines.append((line_start, segment_end))


def line_index(lines: Sequence[tuple[int, int]], position: int) -> int:
    for index, (_start, end) in enumerate(lines):
        if position < end:
            return index
    return len(lines) - 1


def build_markup(
    target: str,
    states: Sequence[CharState],
    *,
    position: int,
    start: int,
    end: int,
    accent: str = DEFAULT_ACCENT,
) -> str:
    parts = []
    for index in range(start, end):
        char = target[index]
        state = states[index]
        # The page joins lines itself: a newline is drawn as a marker.
        shown = NEWLINE_MARK if char == "\n" else html.escape(char)
        if state is CharState.CORRECT:
            parts.append(f'<span alpha="100%">{shown}</span>')
        elif state is CharState.INCORRECT:
            shown = WRONG_SPACE if char == " " else shown
            parts.append(
                f'<span foreground="{ERROR_COLOR}" underline="single">{shown}</span>'
            )
        elif index == position:
            parts.append(
                f'<span alpha="55%" underline="single" underline_color="{accent}">'
                f"{shown}</span>"
            )
        else:
            parts.append(f'<span alpha="55%">{shown}</span>')
    return "".join(parts)
