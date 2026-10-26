import random
import unittest
from datetime import datetime, timedelta, timezone

from typeledger.core.codegen import load_snippets
from typeledger.core.engine import CharState, TypingSession
from typeledger.core.layout import load_layout
from typeledger.core.models import CODE_LANGUAGES, MODE_TIME, MODE_WORDS
from typeledger.core.practice import Practice, PracticeSettings
from typeledger.core.progress import CharErrorRate, key_heat
from typeledger.core.storage import Storage
from typeledger.core.text_display import NEWLINE_MARK, build_markup, line_index, wrap_lines
from tests.test_storage import make_result, row_counts

P, C, I = CharState.PENDING, CharState.CORRECT, CharState.INCORRECT
START = datetime(2026, 10, 25, 18, 0, tzinfo=timezone(timedelta(hours=-3)))
CODE = "if x:\n    y = 1\n    z\nw"


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class StorageLanguageTest(unittest.TestCase):
    def setUp(self):
        self.storage = Storage(":memory:")
        self.addCleanup(self.storage.close)

    def test_accepts_code_and_prose_ids(self):
        for language in ("en", "es") + CODE_LANGUAGES:
            self.storage.save_session(make_result(language=language))
        languages = [s.result.language for s in self.storage.list_sessions()]
        self.assertCountEqual(languages, ["en", "es", *CODE_LANGUAGES])

    def test_unknown_id_rejected_and_writes_nothing(self):
        self.storage.save_session(make_result(language="python"))
        before = row_counts(self.storage)
        for language in ("klingon", "Python", ""):
            with self.subTest(language=language), self.assertRaises(ValueError):
                self.storage.save_session(make_result(language=language))
        self.assertEqual(row_counts(self.storage), before)

    def test_newline_char_stat_round_trips(self):
        from typeledger.core.models import CharStat

        self.storage.save_session(
            make_result(language="go", char_stats={"\n": CharStat(hits=3, misses=1)})
        )
        stats = self.storage.list_sessions()[0].result.char_stats
        self.assertEqual(stats["\n"], CharStat(hits=3, misses=1))


def code_session(target=CODE, mode=MODE_WORDS, auto_indent=True):
    return TypingSession(
        target,
        mode=mode,
        mode_value=10,
        language="python",
        layout_id="corne-4x6",
        clock=FakeClock(),
        auto_indent=auto_indent,
    )


class AutoIndentTest(unittest.TestCase):
    def test_indent_is_skipped_without_keystrokes_or_stats(self):
        session = code_session()
        for ch in "if x:\n":
            session.type_char(ch)
        self.assertEqual(session.position, len("if x:\n    "))
        self.assertEqual(session.keystrokes, 6)
        self.assertEqual(session.states[6:10], (C, C, C, C))
        self.assertEqual(session.states[10], P)
        result = session.finish()
        self.assertEqual(result.char_stats[" "].hits, 1)  # only "if x"
        self.assertEqual(result.char_stats["\n"].hits, 1)

    def test_wrong_enter_still_advances_and_skips_indent(self):
        session = code_session()
        for ch in "if x:":
            session.type_char(ch)
        self.assertFalse(session.type_char("q"))
        self.assertEqual(session.states[5], I)
        self.assertEqual(session.position, 10)
        self.assertEqual(session.keystrokes, 6)

    def test_line_without_indent_is_not_skipped(self):
        session = code_session("a\nb\n  c")
        session.type_char("a")
        session.type_char("\n")
        self.assertEqual(session.position, 2)
        session.type_char("b")
        session.type_char("\n")
        self.assertEqual(session.position, 6)

    def test_backspace_from_first_char_returns_to_newline(self):
        session = code_session()
        for ch in "if x:\n":
            session.type_char(ch)
        session.backspace()
        self.assertEqual(session.position, 5)
        self.assertEqual(session.states[5:11], (P,) * 6)
        session.type_char("\n")
        self.assertEqual(session.position, 10)

    def test_backspace_inside_line_is_one_char(self):
        session = code_session()
        for ch in "if x:\ny":
            session.type_char(ch)
        session.backspace()
        self.assertEqual(session.position, 10)
        session.backspace()
        self.assertEqual(session.position, 5)

    def test_words_mode_finishes_at_end(self):
        session = code_session()
        for ch in "if x:\ny = 1\nz\nw":
            session.type_char(ch)
        self.assertTrue(session.finished)
        self.assertEqual(session.finish().accuracy, 1.0)

    def test_prose_session_does_not_skip_spaces(self):
        session = code_session(auto_indent=False)
        for ch in "if x:\n":
            session.type_char(ch)
        self.assertEqual(session.position, 6)
        session.backspace()
        self.assertEqual(session.position, 5)


class WrapCodeTest(unittest.TestCase):
    def test_newline_is_a_hard_break_owned_by_its_line(self):
        text = "ab\n    cd\n\nef"
        lines = wrap_lines(text, 20)
        self.assertEqual(
            [text[s:e] for s, e in lines], ["ab\n", "    cd\n", "\n", "ef"]
        )
        self.assertEqual(line_index(lines, 2), 0)
        self.assertEqual(line_index(lines, 3), 1)

    def test_long_code_line_still_wraps_at_width(self):
        text = "x = alpha + beta\ny"
        lines = wrap_lines(text, 8)
        self.assertEqual("".join(text[s:e] for s, e in lines), text)
        self.assertEqual([text[s:e] for s, e in lines], ["x = ", "alpha + ", "beta\n", "y"])


class NewlineMarkupTest(unittest.TestCase):
    def test_newline_is_never_raw_and_shows_marker(self):
        for states, position in (([C, P], 1), ([C, P], 0), ([C, I], 2), ([C, C], 2)):
            with self.subTest(states=states, position=position):
                markup = build_markup("a\n", states, position=position, start=0, end=2)
                self.assertNotIn("\n", markup)
                self.assertIn(NEWLINE_MARK, markup)
        self.assertEqual(NEWLINE_MARK, "⏎")

    def test_pending_newline_is_dim_and_wrong_one_red(self):
        pending = build_markup("a\n", [C, P], position=0, start=1, end=2)
        self.assertEqual(pending, f'<span alpha="55%">{NEWLINE_MARK}</span>')
        wrong = build_markup("a\n", [C, I], position=2, start=1, end=2)
        self.assertIn('foreground="#e01b24"', wrong)

    def test_indent_spaces_render_as_spaces(self):
        markup = build_markup("\n  a", [C, C, C, P], position=3, start=1, end=4)
        self.assertEqual(markup.count('<span alpha="100%"> </span>'), 2)


def make_practice(settings, storage):
    clock = FakeClock()
    practice = Practice(settings, storage, rng=random.Random(5), clock=clock, now=lambda: START)
    return practice, clock


class CodePracticeTest(unittest.TestCase):
    def setUp(self):
        self.storage = Storage(":memory:")
        self.addCleanup(self.storage.close)

    def test_words_mode_ends_at_snippet_boundary(self):
        practice, _clock = make_practice(
            PracticeSettings("python", MODE_WORDS, 25, "corne-4x6"), self.storage
        )
        self.assertTrue(practice.is_code)
        target = practice.session.target
        self.assertGreaterEqual(len(target.split()), 25)
        snippets = set(load_snippets("python"))
        for part in target.split("\n\n"):
            self.assertIn(part, snippets)

    def test_typing_code_without_indent_completes_and_saves(self):
        practice, clock = make_practice(
            PracticeSettings("rust", MODE_WORDS, 10, "corne-4x6"), self.storage
        )
        target = practice.session.target
        typed = "\n".join(line.lstrip(" ") for line in target.split("\n"))
        clock.now = 20.0
        self.assertTrue(practice.type_text(typed))
        stored = self.storage.list_sessions()[0].result
        self.assertEqual(stored.language, "rust")
        self.assertEqual(stored.accuracy, 1.0)
        self.assertEqual(stored.keystrokes, len(typed))

    def test_time_mode_extends_with_snippets(self):
        practice, _clock = make_practice(
            PracticeSettings("go", MODE_TIME, 30, "corne-4x6"), self.storage
        )
        initial = practice.session.target
        typed = "\n".join(line.lstrip(" ") for line in initial.split("\n"))
        practice.type_text(typed)
        target = practice.session.target
        self.assertTrue(target.startswith(initial + "\n\n"))
        snippets = set(load_snippets("go"))
        for part in target.split("\n\n"):
            self.assertIn(part, snippets)
        self.assertIsNone(practice.last_result)

    def test_prose_settings_are_not_code(self):
        practice, _clock = make_practice(
            PracticeSettings("en", MODE_WORDS, 10, "corne-4x6"), self.storage
        )
        self.assertFalse(practice.is_code)
        self.assertNotIn("\n", practice.session.target)

    def test_enter_hint_for_newline(self):
        practice, _clock = make_practice(
            PracticeSettings("python", MODE_WORDS, 10, "corne-3x6"), self.storage
        )
        enter = practice.layout.keys_for_special("enter")
        self.assertTrue(enter)
        self.assertEqual(practice.hint_for("\n"), (0, enter))


class NewlineHeatTest(unittest.TestCase):
    def test_newline_heats_the_enter_key(self):
        layout = load_layout("corne-4x6")
        heat = key_heat(
            layout,
            {
                "\n": CharErrorRate("\n", 6, 4, 0.4),
                "a": CharErrorRate("a", 9, 1, 0.1),
            },
        )
        enter = layout.keys_for_special("enter")[0]
        self.assertEqual(heat[enter], 1.0)
        self.assertAlmostEqual(heat[layout.keys_for_char("a")[-1]], 0.25)


if __name__ == "__main__":
    unittest.main()
