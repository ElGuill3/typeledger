import unittest

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk  # noqa: E402

from typeledger.core.models import MODE_TIME, MODE_WORDS  # noqa: E402
from typeledger.core.practice import PracticeSettings  # noqa: E402
from typeledger.core.storage import Storage  # noqa: E402
from typeledger.ui.practice_page import PracticePage  # noqa: E402

Adw.init()


class PracticePageTest(unittest.TestCase):
    def setUp(self):
        self.storage = Storage(":memory:")
        self.page = PracticePage(
            self.storage,
            settings=PracticeSettings("en", MODE_WORDS, 10, "corne-4x6"),
        )

    def test_committed_text_advances_session_and_flashes_keys(self):
        target = self.page.practice.session.target
        self.page._on_commit(None, target[:3])
        self.assertEqual(self.page.practice.session.position, 3)
        self.assertIn(target[3], self.page.text_label.get_text())
        self.assertTrue(self.page.keyboard._pressed)

    def test_backspace_key_moves_back_and_is_consumed(self):
        self.page._on_commit(None, "zz")
        handled = self.page._on_key_pressed(None, Gdk.KEY_BackSpace, 0, 0)
        self.assertTrue(handled)
        self.assertEqual(self.page.practice.session.position, 1)

    def test_shortcut_keys_are_not_consumed(self):
        self.assertFalse(self.page._on_key_pressed(None, Gdk.KEY_q, 0, 0))
        self.assertFalse(self.page._on_key_pressed(None, Gdk.KEY_Control_L, 0, 0))

    def test_completing_words_session_saves_it(self):
        self.page._on_commit(None, self.page.practice.session.target)
        self.assertEqual(len(self.storage.list_sessions()), 1)

    def test_changing_options_restarts_with_new_settings(self):
        self.page.mode_group.set_active_name(MODE_TIME)
        settings = self.page.practice.settings
        self.assertEqual(settings.mode, MODE_TIME)
        self.assertEqual(settings.mode_value, 30)
        self.page.layout_dropdown.set_selected(0)
        self.assertEqual(
            self.page.practice.settings.layout_id, self.page._layouts[0][0]
        )

    def test_hinted_layer_follows_next_char(self):
        self.page.practice.session._target = "{"
        self.page.practice.session._states = [self.page.practice.session.states[0]]
        self.page.refresh()
        self.assertEqual(self.page.keyboard._layer, 1)


class WindowTest(unittest.TestCase):
    def test_window_shows_practice_page(self):
        from typeledger.window import TypeLedgerWindow

        window = TypeLedgerWindow(storage=Storage(":memory:"))
        self.assertIsInstance(window.practice_page, PracticePage)


if __name__ == "__main__":
    unittest.main()
