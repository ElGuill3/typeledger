import unittest
from datetime import datetime, timezone

from typeledger.core.engine import CharState, TypingSession
from typeledger.core.models import MODE_TIME, MODE_WORDS, CharStat, SessionResult

STARTED_AT = datetime(2026, 10, 25, 18, 0, tzinfo=timezone.utc)


class FakeClock:
    def __init__(self, start=100.0):
        self.value = start

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


def make_session(target, *, mode=MODE_WORDS, mode_value=2, clock=None):
    return TypingSession(
        target,
        mode=mode,
        mode_value=mode_value,
        language="en",
        layout_id="corne-4x6",
        clock=clock or FakeClock(),
        now=lambda: STARTED_AT,
    )


def type_text(session, text, clock=None, step=0.0):
    for ch in text:
        session.type_char(ch)
        if clock is not None:
            clock.advance(step)


class TypingSessionTest(unittest.TestCase):
    def test_all_correct_words_session(self):
        clock = FakeClock()
        session = make_session("hello world", clock=clock)
        self.assertFalse(session.started)
        self.assertEqual(session.elapsed(), 0.0)

        session.type_char("h")
        self.assertTrue(session.started)
        clock.advance(6.0)
        type_text(session, "ello worl")
        self.assertFalse(session.finished)
        self.assertTrue(session.type_char("d"))
        self.assertTrue(session.finished)

        clock.advance(30.0)  # elapsed is frozen at finish
        self.assertEqual(session.elapsed(), 6.0)

        result = session.finish()
        self.assertIsInstance(result, SessionResult)
        self.assertEqual(result.started_at, STARTED_AT)
        self.assertEqual(result.mode, MODE_WORDS)
        self.assertEqual(result.mode_value, 2)
        self.assertEqual(result.language, "en")
        self.assertEqual(result.layout_id, "corne-4x6")
        self.assertEqual(result.duration_s, 6.0)
        # 11 chars / 5 = 2.2 words in 0.1 minutes
        self.assertAlmostEqual(result.wpm, 22.0)
        self.assertAlmostEqual(result.raw_wpm, 22.0)
        self.assertEqual(result.accuracy, 1.0)
        self.assertEqual(result.correct_chars, 11)
        self.assertEqual(result.incorrect_chars, 0)
        self.assertEqual(result.keystrokes, 11)
        self.assertEqual(session.finish(), result)

    def test_error_backspace_and_correction(self):
        clock = FakeClock()
        session = make_session("abc", clock=clock)
        self.assertTrue(session.type_char("a"))
        self.assertFalse(session.type_char("x"))
        self.assertEqual(session.states[1], CharState.INCORRECT)
        self.assertEqual(session.position, 2)

        session.backspace()
        self.assertEqual(session.position, 1)
        self.assertEqual(session.states[1], CharState.PENDING)
        self.assertEqual(session.keystrokes, 2)

        clock.advance(12.0)
        type_text(session, "bc")
        self.assertTrue(session.finished)
        self.assertEqual(
            list(session.states), [CharState.CORRECT] * 3
        )

        result = session.finish()
        self.assertEqual(result.keystrokes, 4)
        self.assertEqual(result.correct_chars, 3)
        self.assertEqual(result.incorrect_chars, 0)
        self.assertAlmostEqual(result.accuracy, 0.75)
        # 3 correct chars / 5 in 0.2 minutes; 4 typed chars / 5 in 0.2 minutes
        self.assertAlmostEqual(result.wpm, 3.0)
        self.assertAlmostEqual(result.raw_wpm, 4.0)
        self.assertEqual(result.char_stats["b"], CharStat(hits=1, misses=1))

    def test_backspace_at_zero_is_noop(self):
        session = make_session("ab")
        session.backspace()
        self.assertEqual(session.position, 0)
        self.assertEqual(session.keystrokes, 0)
        self.assertFalse(session.started)

    def test_typing_after_finish_is_ignored(self):
        session = make_session("ab")
        type_text(session, "ab")
        self.assertTrue(session.finished)
        self.assertFalse(session.type_char("c"))
        self.assertEqual(session.keystrokes, 2)
        self.assertEqual(session.position, 2)
        session.backspace()
        self.assertEqual(session.position, 2)

    def test_explicit_finish_stops_typing(self):
        session = make_session("abc")
        session.type_char("a")
        session.finish()
        self.assertTrue(session.finished)
        self.assertFalse(session.type_char("b"))
        self.assertEqual(session.keystrokes, 1)

    def test_time_mode_time_up_and_duration_capped(self):
        clock = FakeClock()
        session = make_session("abc", mode=MODE_TIME, mode_value=15, clock=clock)
        self.assertFalse(session.is_time_up())
        type_text(session, "abc")
        self.assertFalse(session.finished)  # time mode does not end on text end
        clock.advance(14.0)
        self.assertFalse(session.is_time_up())
        clock.advance(2.0)
        self.assertTrue(session.is_time_up())

        result = session.finish()
        self.assertEqual(result.mode, MODE_TIME)
        self.assertEqual(result.mode_value, 15)
        self.assertEqual(result.duration_s, 15.0)
        # 3 chars / 5 in 0.25 minutes
        self.assertAlmostEqual(result.wpm, 2.4)

    def test_extend_appends_target(self):
        session = make_session("ab", mode=MODE_TIME, mode_value=30)
        type_text(session, "ab")
        session.extend(" cd")
        self.assertEqual(session.target, "ab cd")
        self.assertEqual(len(session.states), 5)
        self.assertEqual(session.states[2], CharState.PENDING)
        self.assertTrue(session.type_char(" "))
        self.assertEqual(session.position, 3)

    def test_zero_keystroke_finish(self):
        session = make_session("abc")
        result = session.finish()
        self.assertEqual(result.started_at, STARTED_AT)
        self.assertEqual(result.duration_s, 0.0)
        self.assertEqual(result.wpm, 0.0)
        self.assertEqual(result.raw_wpm, 0.0)
        self.assertEqual(result.accuracy, 0.0)
        self.assertEqual(result.keystrokes, 0)
        self.assertEqual(result.correct_chars, 0)
        self.assertEqual(dict(result.char_stats), {})

    def test_char_stats_hits_and_misses_including_space(self):
        session = make_session("a a b")
        # Both spaces are typed wrong; every letter is right.
        type_text(session, "a-acb")
        self.assertTrue(session.finished)
        result = session.finish()
        self.assertEqual(result.char_stats["a"], CharStat(hits=2, misses=0))
        self.assertEqual(result.char_stats[" "], CharStat(hits=0, misses=2))
        self.assertEqual(result.char_stats["b"], CharStat(hits=1, misses=0))
        self.assertNotIn("c", result.char_stats)
        self.assertEqual(result.incorrect_chars, 2)
        self.assertEqual(result.correct_chars, 3)

    def test_live_metrics(self):
        clock = FakeClock()
        session = make_session("abcd", clock=clock)
        self.assertEqual(session.live_wpm(), 0.0)
        self.assertEqual(session.live_accuracy(), 0.0)
        session.type_char("a")
        clock.advance(6.0)
        session.type_char("x")
        self.assertAlmostEqual(session.live_wpm(), 2.0)  # 1 correct / 5 in 0.1 min
        self.assertAlmostEqual(session.live_accuracy(), 0.5)
        self.assertEqual(session.correct_keystrokes, 1)


if __name__ == "__main__":
    unittest.main()
