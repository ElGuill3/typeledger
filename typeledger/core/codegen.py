"""Practice text generation from bundled code snippets.

A snippet file holds snippets separated by lines containing only ``---``.
Lines starting with ``#!`` are file comments and are skipped.
"""

import random
from functools import cache
from importlib.resources import files

from typeledger.core.models import CODE_LANGUAGES

SNIPPET_SEPARATOR = "---"
COMMENT_PREFIX = "#!"


@cache
def load_snippets(language: str) -> tuple[str, ...]:
    """Return the snippets for `language`, without surrounding blank lines."""
    if language not in CODE_LANGUAGES:
        raise ValueError(f"unknown code language: {language!r}")
    resource = files("typeledger") / "data" / "code" / f"{language}.txt"
    snippets: list[str] = []
    current: list[str] = []
    for line in resource.read_text(encoding="utf-8").splitlines():
        if line.startswith(COMMENT_PREFIX):
            continue
        if line == SNIPPET_SEPARATOR:
            snippets.append("\n".join(current).strip("\n"))
            current = []
        else:
            current.append(line.rstrip())
    snippets.append("\n".join(current).strip("\n"))
    return tuple(dict.fromkeys(snippet for snippet in snippets if snippet))


def generate_code(
    language: str, min_words: int, rng: random.Random | None = None
) -> str:
    """Return whole snippets joined by a blank line, with at least `min_words`
    whitespace-separated tokens.

    The same snippet never appears twice in a row.
    """
    snippets = load_snippets(language)
    rng = rng or random.Random()
    chosen: list[str] = []
    words = 0
    while not chosen or words < min_words:
        snippet = rng.choice(snippets)
        while chosen and snippet == chosen[-1]:
            snippet = rng.choice(snippets)
        chosen.append(snippet)
        words += len(snippet.split())
    return "\n\n".join(chosen)
