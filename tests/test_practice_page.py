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

    def test_completing_session_emits_session_completed(self):
        emitted = []
        self.page.connect("session-completed", lambda _page: emitted.append(True))
        self.page._on_commit(None, self.page.practice.session.target[:-1])
        self.assertEqual(emitted, [])
        self.page._on_commit(None, self.page.practice.session.target[-1])
        self.assertEqual(emitted, [True])

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

    def test_window_has_practice_and_progress_views(self):
        from typeledger.ui.progress_page import ProgressPage
        from typeledger.window import TypeLedgerWindow

        window = TypeLedgerWindow(storage=Storage(":memory:"))
        self.assertIsInstance(window.progress_page, ProgressPage)
        self.assertIs(window.view_stack.get_child_by_name("practice"), window.practice_page)
        self.assertIs(window.view_stack.get_child_by_name("progress"), window.progress_page)
        self.assertEqual(window.view_stack.get_visible_child_name(), "practice")

    def test_progress_refreshes_after_session_completed(self):
        from typeledger.window import TypeLedgerWindow

        storage = Storage(":memory:")
        window = TypeLedgerWindow(storage=storage)
        page = window.progress_page
        self.assertIs(page.stack.get_visible_child(), page.empty_page)
        window.practice_page._on_commit(None, window.practice_page.practice.session.target)
        self.assertIs(page.stack.get_visible_child(), page.content_page)
        self.assertEqual(page.total_sessions_label.get_label(), "1")

    def test_progress_refreshes_when_shown(self):
        from typeledger.window import TypeLedgerWindow

        storage = Storage(":memory:")
        window = TypeLedgerWindow(storage=storage)
        window.practice_page.practice.type_text(window.practice_page.practice.session.target)
        page = window.progress_page
        self.assertIs(page.stack.get_visible_child(), page.empty_page)
        window.view_stack.set_visible_child_name("progress")
        self.assertIs(page.stack.get_visible_child(), page.content_page)

    def test_practice_page_loses_focus_on_progress_view(self):
        from gi.repository import GLib

        from typeledger.window import TypeLedgerWindow

        window = TypeLedgerWindow(storage=Storage(":memory:"))
        window.present()
        context = GLib.MainContext.default()
        while context.pending():
            context.iteration(False)
        window.view_stack.set_visible_child_name("progress")
        focus = window.get_focus()
        self.assertFalse(
            focus is not None and focus.is_ancestor(window.practice_page)
            or focus is window.practice_page
        )
        window.view_stack.set_visible_child_name("practice")
        self.assertIs(window.get_focus(), window.practice_page)
        window.destroy()


if __name__ == "__main__":
    unittest.main()
