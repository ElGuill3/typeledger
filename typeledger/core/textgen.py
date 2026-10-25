"""Practice text generation from per-language word lists."""

import random
from functools import cache
from importlib.resources import files

from typeledger.core.models import LANGUAGES


@cache
def load_words(language: str) -> tuple[str, ...]:
    """Return the word list for `language`, one lowercase word per entry."""
    if language not in LANGUAGES:
        raise ValueError(f"unknown language: {language!r}")
    resource = files("typeledger") / "data" / "words" / f"{language}.txt"
    text = resource.read_text(encoding="utf-8")
    words = (line.strip().lower() for line in text.splitlines())
    return tuple(dict.fromkeys(word for word in words if word))


def generate_text(
    language: str, word_count: int, rng: random.Random | None = None
) -> str:
    """Return `word_count` random words joined by single spaces.

    The same word never appears twice in a row.
    """
    words = load_words(language)
    rng = rng or random.Random()
    chosen: list[str] = []
    for _ in range(word_count):
        word = rng.choice(words)
        while chosen and word == chosen[-1]:
            word = rng.choice(words)
        chosen.append(word)
    return " ".join(chosen)
