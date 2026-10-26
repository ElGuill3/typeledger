import random
import sqlite3
import unittest
from datetime import datetime, timedelta, timezone

from typeledger.core.models import MODE_TIME, MODE_WORDS
from typeledger.core.practice import Practice, PracticeSettings
from typeledger.core.storage import Storage

START = datetime(2026, 10, 25, 18, 0, tzinfo=timezone(timedelta(hours=-3)))


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def make_practice(settings, storage):
    clock = FakeClock()
    practice = Practice(
        settings,
        storage,
        rng=random.Random(7),
        clock=clock,
        now=lambda: START,
    )
    return practice, clock


class WordsModeTest(unittest.TestCase):
    def setUp(self):
        self.storage = Storage(":memory:")
        self.addCleanup(self.storage.close)
        self.practice, self.clock = make_practice(
            PracticeSettings("en", MODE_WORDS, 10, "corne-4x6"), self.storage
        )

    def test_text_has_requested_word_count(self):
        self.assertEqual(len(self.practice.session.target.split(" ")), 10)

    def test_typing_whole_text_completes_and_saves_once(self):
        target = self.practice.session.target
        self.clock.now = 30.0
        finished = self.practice.type_text(target)
        self.assertTrue(finished)
        result = self.practice.last_result
        self.assertEqual(result.accuracy, 1.0)
        self.assertEqual(result.layout_id, "corne-4x6")
        self.practice.type_text("x")  # ignored after finish
        stored = self.storage.list_sessions()
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0].result.keystrokes, len(target))

    def test_restart_with_new_settings_builds_new_session(self):
        self.practice.type_text("q")
        self.practice.restart(PracticeSettings("es", MODE_WORDS, 25, "corne-3x6"))
        self.assertEqual(self.practice.session.position, 0)
        self.assertEqual(len(self.practice.session.target.split(" ")), 25)
        self.assertEqual(self.practice.layout.id, "corne-3x6")
        self.assertEqual(self.storage.list_sessions(), [])

    def test_backspace_moves_cursor_back(self):
        self.practice.type_text("zz")
        self.practice.backspace()
        self.assertEqual(self.practice.session.position, 1)


class TimeModeTest(unittest.TestCase):
    def setUp(self):
        self.storage = Storage(":memory:")
        self.addCleanup(self.storage.close)
        self.practice, self.clock = make_practice(
            PracticeSettings("en", MODE_TIME, 15, "corne-4x6"), self.storage
        )

    def test_text_is_extended_before_the_cursor_reaches_the_end(self):
        session = self.practice.session
        initial_length = len(session.target)
        self.practice.type_text(session.target[: initial_length - 5])
        self.assertGreater(len(session.target), initial_length)
        self.assertFalse(session.finished)

    def test_tick_completes_when_time_is_up_and_saves(self):
        self.practice.type_text(self.practice.session.target[:20])
        self.clock.now = 14.9
        self.assertFalse(self.practice.tick())
        self.clock.now = 15.0
        self.assertTrue(self.practice.tick())
        self.assertEqual(self.practice.last_result.duration_s, 15.0)
        self.assertEqual(len(self.storage.list_sessions()), 1)
        self.assertFalse(self.practice.tick())  # already completed

    def test_cancel_discards_session_without_saving(self):
        settings = self.practice.settings
        self.practice.type_text(self.practice.session.target[:20])
        self.practice.cancel()
        self.assertEqual(self.practice.settings, settings)
        self.assertEqual(self.practice.session.position, 0)
        self.assertFalse(self.practice.session.started)
        self.assertIsNone(self.practice.last_result)
        self.clock.now = 100.0
        self.assertFalse(self.practice.tick())
        self.assertEqual(self.storage.list_sessions(), [])

    def test_tick_before_typing_does_nothing(self):
        self.clock.now = 100.0
        self.assertFalse(self.practice.tick())
        self.assertIsNone(self.practice.last_result)


class SaveTest(unittest.TestCase):
    def test_session_without_keystrokes_is_not_saved(self):
        storage = Storage(":memory:")
        self.addCleanup(storage.close)
        practice, _clock = make_practice(
            PracticeSettings("en", MODE_TIME, 15, "corne-4x6"), storage
        )
        practice.complete()
        self.assertEqual(storage.list_sessions(), [])
        self.assertIsNone(practice.save_error)

    def test_storage_failure_is_reported_not_raised(self):
        storage = Storage(":memory:")
        self.addCleanup(storage.close)
        storage.close()
        practice, _clock = make_practice(
            PracticeSettings("en", MODE_WORDS, 10, "corne-4x6"), storage
        )
        practice.type_text(practice.session.target)
        self.assertIsNotNone(practice.last_result)
        self.assertIsInstance(practice.save_error, sqlite3.Error)


class HintTest(unittest.TestCase):
    def setUp(self):
        self.storage = Storage(":memory:")
        self.addCleanup(self.storage.close)

    def test_hint_for_base_layer_char(self):
        practice, _clock = make_practice(
            PracticeSettings("en", MODE_WORDS, 10, "corne-4x6"), self.storage
        )
        layer, keys = practice.hint_for("a")
        self.assertEqual(layer, 0)
        self.assertEqual(keys, practice.layout.keys_for_char("a"))

    def test_hint_switches_to_layer_of_layer_key(self):
        practice, _clock = make_practice(
            PracticeSettings("en", MODE_WORDS, 10, "corne-4x6"), self.storage
        )
        layer, keys = practice.hint_for("{")
        self.assertEqual(layer, 1)
        self.assertEqual(keys, practice.layout.keys_for_char("{"))

    def test_next_hint_is_empty_after_finish(self):
        practice, _clock = make_practice(
            PracticeSettings("en", MODE_WORDS, 10, "corne-4x6"), self.storage
        )
        self.assertEqual(
            practice.next_hint(), practice.hint_for(practice.session.target[0])
        )
        practice.type_text(practice.session.target)
        self.assertEqual(practice.next_hint(), (0, ()))


if __name__ == "__main__":
    unittest.main()
