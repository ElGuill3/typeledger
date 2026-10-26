import random
import unittest
from importlib.resources import files

from typeledger.core.codegen import generate_code, load_snippets
from typeledger.core.models import CODE_LANGUAGES, LANGUAGES, TEXT_SOURCES

# Practice page line width: snippet lines should fit without wrapping.
MAX_LINE = 56
GOOD_SNIPPET = "def f(x):\n    y = x + 1\n    return y"


def snippet_problems(snippet):
    """Every rule a bundled snippet breaks; empty means valid."""
    problems = []
    lines = snippet.split("\n")
    if not 3 <= len(lines) <= 12:
        problems.append(f"{len(lines)} lines, want 3-12")
    if not snippet.isascii():
        problems.append("non-ASCII text")
    if "\t" in snippet:
        problems.append("tab character")
    if "---" in lines:
        problems.append("separator line")
    # Blank lines only separate snippets in generated text.
    if any(not line.strip() for line in lines):
        problems.append("blank line")
    if lines[0].startswith(" "):
        problems.append("indented first line")
    for line in lines:
        if line != line.rstrip():
            problems.append(f"trailing space: {line!r}")
        if len(line) > MAX_LINE:
            problems.append(f"{len(line)} columns: {line!r}")
        if line.startswith("#!"):
            problems.append(f"header comment: {line!r}")
    return problems


class LanguageIdsTest(unittest.TestCase):
    def test_code_ids_and_combined_sources(self):
        self.assertEqual(LANGUAGES, ("en", "es"))
        self.assertEqual(CODE_LANGUAGES, ("python", "javascript", "rust", "go"))
        self.assertEqual(TEXT_SOURCES, LANGUAGES + CODE_LANGUAGES)


class SnippetDataTest(unittest.TestCase):
    def test_every_language_has_valid_snippets(self):
        for language in CODE_LANGUAGES:
            with self.subTest(language=language):
                snippets = load_snippets(language)
                self.assertGreaterEqual(len(snippets), 12)
                self.assertEqual(len(set(snippets)), len(snippets), "duplicate snippet")
                for snippet in snippets:
                    self.assertEqual(snippet_problems(snippet), [], snippet)

    def test_validator_accepts_a_good_snippet(self):
        self.assertEqual(snippet_problems(GOOD_SNIPPET), [])

    def test_validator_rejects_each_broken_rule(self):
        long_line = "x = " + "1" * MAX_LINE
        bad = {
            "too short": "a = 1\nb = 2",
            "too long": "\n".join(f"v{i} = {i}" for i in range(13)),
            "non-ASCII": GOOD_SNIPPET.replace("x + 1", "x \u00d7 1"),
            "tab": GOOD_SNIPPET.replace("    return", "\treturn"),
            "trailing space": GOOD_SNIPPET.replace("x + 1", "x + 1 "),
            "too wide": GOOD_SNIPPET + "\n" + long_line,
            "blank inside": GOOD_SNIPPET.replace("\n    return", "\n\n    return"),
            "whitespace-only inside": GOOD_SNIPPET.replace("\n    return", "\n    \n    return"),
            "separator": GOOD_SNIPPET + "\n---\nz = 1",
            "indented start": "    " + GOOD_SNIPPET,
            "header": "#! python\n" + GOOD_SNIPPET,
        }
        for name, snippet in bad.items():
            with self.subTest(name=name):
                self.assertNotEqual(snippet_problems(snippet), [], snippet)
        # A line exactly MAX_LINE wide is still fine.
        self.assertEqual(snippet_problems(GOOD_SNIPPET + "\nx = " + "1" * (MAX_LINE - 4)), [])

    def test_indentation_uses_multiples_of_four_spaces(self):
        for language in CODE_LANGUAGES:
            for snippet in load_snippets(language):
                for line in snippet.split("\n"):
                    indent = len(line) - len(line.lstrip(" "))
                    self.assertEqual(indent % 4, 0, f"{language}: {line!r}")

    def test_header_comment_lines_are_skipped(self):
        for language in CODE_LANGUAGES:
            raw = (files("typeledger") / "data" / "code" / f"{language}.txt").read_text(
                encoding="utf-8"
            )
            self.assertTrue(raw.startswith("#!"), language)
            self.assertFalse(any("#!" in s for s in load_snippets(language)))

    def test_unknown_language_rejected(self):
        for language in ("en", "klingon"):
            with self.assertRaises(ValueError):
                load_snippets(language)


class GenerateCodeTest(unittest.TestCase):
    def test_reaches_word_minimum_with_whole_snippets(self):
        snippets = set(load_snippets("python"))
        for min_words in (10, 25, 50, 100):
            with self.subTest(min_words=min_words):
                text = generate_code("python", min_words, random.Random(min_words))
                self.assertGreaterEqual(len(text.split()), min_words)
                parts = text.split("\n\n")
                for part in parts:
                    self.assertIn(part, snippets)
                # Dropping the last snippet falls below the minimum.
                self.assertLess(len("\n\n".join(parts[:-1]).split()), min_words)

    def test_no_snippet_twice_in_a_row(self):
        for seed in range(30):
            parts = generate_code("go", 300, random.Random(seed)).split("\n\n")
            for previous, current in zip(parts, parts[1:]):
                self.assertNotEqual(previous, current)

    def test_seeded_rng_is_deterministic(self):
        self.assertEqual(
            generate_code("rust", 50, random.Random(3)),
            generate_code("rust", 50, random.Random(3)),
        )

    def test_text_has_no_trailing_or_leading_newline(self):
        text = generate_code("javascript", 40, random.Random(1))
        self.assertEqual(text, text.strip())


if __name__ == "__main__":
    unittest.main()
