import unittest

from typeledger.core.engine import CharState
from typeledger.core.text_display import (
    build_markup,
    line_index,
    wrap_lines,
)

P, C, I = CharState.PENDING, CharState.CORRECT, CharState.INCORRECT


class WrapLinesTest(unittest.TestCase):
    def test_lines_cover_text_exactly_and_respect_width(self):
        text = "the quick brown fox jumps over the lazy dog"
        lines = wrap_lines(text, 12)
        self.assertEqual("".join(text[s:e] for s, e in lines), text)
        for start, end in lines:
            self.assertLessEqual(len(text[start:end].rstrip(" ")), 12)
        self.assertEqual(
            [text[s:e] for s, e in lines],
            ["the quick ", "brown fox ", "jumps over ", "the lazy dog"],
        )

    def test_word_longer_than_width_is_split(self):
        self.assertEqual(wrap_lines("abcdefgh ij", 4), [(0, 4), (4, 9), (9, 11)])

    def test_empty_text_has_one_empty_line(self):
        self.assertEqual(wrap_lines("", 10), [(0, 0)])

    def test_rejects_non_positive_width(self):
        with self.assertRaises(ValueError):
            wrap_lines("abc", 0)


class LineIndexTest(unittest.TestCase):
    def test_finds_the_line_holding_the_cursor(self):
        lines = [(0, 10), (10, 20), (20, 25)]
        self.assertEqual(line_index(lines, 0), 0)
        self.assertEqual(line_index(lines, 9), 0)
        self.assertEqual(line_index(lines, 10), 1)
        self.assertEqual(line_index(lines, 25), 2)  # cursor after the last char


class BuildMarkupTest(unittest.TestCase):
    def test_marks_correct_incorrect_cursor_and_pending(self):
        markup = build_markup("abcd", [C, I, P, P], position=2, start=0, end=4)
        self.assertEqual(
            markup,
            '<span alpha="100%">a</span>'
            '<span foreground="#e01b24" underline="single">b</span>'
            '<span alpha="55%" underline="single" underline_color="#3584e4">c</span>'
            '<span alpha="55%">d</span>',
        )

    def test_escapes_markup_and_shows_wrong_space_visibly(self):
        markup = build_markup("<& ", [C, C, I], position=3, start=0, end=3)
        self.assertIn("&lt;", markup)
        self.assertIn("&amp;", markup)
        self.assertIn('underline="single">·</span>', markup)

    def test_renders_only_the_requested_slice(self):
        markup = build_markup("ABCDEF", [P] * 6, position=4, start=3, end=5)
        self.assertNotIn("C", markup)
        self.assertIn(">D<", markup)
        self.assertIn(">E<", markup)
        self.assertNotIn("F", markup)


if __name__ == "__main__":
    unittest.main()
