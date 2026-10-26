"""Line wrapping and Pango markup for the practice text."""

import html
import re
from collections.abc import Sequence

from typeledger.core.engine import CharState

ERROR_COLOR = "#e01b24"
DEFAULT_ACCENT = "#3584e4"
WRONG_SPACE = "·"

_TOKEN = re.compile(r"\S+\s*|\s+")


def wrap_lines(text: str, width: int) -> list[tuple[int, int]]:
    """Greedy word wrap returning [start, end) spans that cover `text` exactly.

    Spaces stay at the end of the line they follow, so cursor positions map
    to exactly one line. Words longer than `width` are hard-split.
    """
    if width <= 0:
        raise ValueError("width must be positive")
    lines: list[tuple[int, int]] = []
    line_start = 0
    for match in _TOKEN.finditer(text):
        start = match.start()
        word_len = len(match.group().rstrip(" "))
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
    lines.append((line_start, len(text)))
    return lines


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
        if state is CharState.CORRECT:
            parts.append(f'<span alpha="100%">{html.escape(char)}</span>')
        elif state is CharState.INCORRECT:
            shown = WRONG_SPACE if char == " " else html.escape(char)
            parts.append(
                f'<span foreground="{ERROR_COLOR}" underline="single">{shown}</span>'
            )
        elif index == position:
            parts.append(
                f'<span alpha="55%" underline="single" underline_color="{accent}">'
                f"{html.escape(char)}</span>"
            )
        else:
            parts.append(f'<span alpha="55%">{html.escape(char)}</span>')
    return "".join(parts)
