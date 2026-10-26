import random
import unittest
from importlib.resources import files

from typeledger.core.codegen import generate_code, load_snippets
from typeledger.core.models import CODE_LANGUAGES, LANGUAGES, TEXT_SOURCES

# Practice page line width: snippet lines should fit without wrapping.
MAX_LINE = 56


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
                    lines = snippet.split("\n")
                    self.assertTrue(3 <= len(lines) <= 12, snippet)
                    self.assertTrue(snippet.isascii(), snippet)
                    self.assertNotIn("\t", snippet)
                    self.assertNotIn("---", lines)
                    # Blank lines only separate snippets in generated text.
                    self.assertNotIn("", lines, snippet)
                    for line in lines:
                        self.assertEqual(line, line.rstrip(), f"trailing space: {line!r}")
                        self.assertLessEqual(len(line), MAX_LINE, line)
                        self.assertFalse(line.startswith("#!"), line)
                    self.assertTrue(lines[0].strip() and lines[-1].strip())
                    self.assertFalse(lines[0].startswith(" "), snippet)

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
