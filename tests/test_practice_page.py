import unittest

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk  # noqa: E402

from typeledger.core.engine import CharState  # noqa: E402
from typeledger.core.models import MODE_TIME, MODE_WORDS  # noqa: E402
from typeledger.core.practice import Practice, PracticeSettings  # noqa: E402
from typeledger.core.storage import Storage  # noqa: E402
from typeledger.ui.practice_page import PracticePage  # noqa: E402

Adw.init()


class PracticePageTest(unittest.TestCase):
    def setUp(self):
        self.storage = Storage(":memory:")
        self.addCleanup(self.storage.close)
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

    def test_enter_in_prose_mode_is_swallowed_without_typing(self):
        handled = self.page._on_key_pressed(None, Gdk.KEY_Return, 0, 0)
        self.assertTrue(handled)
        self.assertEqual(self.page.practice.session.position, 0)
        self.assertEqual(self.page.practice.session.keystrokes, 0)

    def test_language_dropdown_lists_prose_and_code(self):
        model = self.page.language_dropdown.get_model()
        names = [model.get_string(i) for i in range(model.get_n_items())]
        self.assertEqual(names, ["English", "Spanish", "Python", "JavaScript", "Rust", "Go"])

    def test_selecting_python_restarts_code_session(self):
        self.page.language_dropdown.set_selected(2)
        practice = self.page.practice
        self.assertEqual(practice.settings.language, "python")
        self.assertTrue(practice.is_code)
        self.assertIn("\n", practice.session.target)


class CodePracticePageTest(unittest.TestCase):
    def setUp(self):
        self.storage = Storage(":memory:")
        self.addCleanup(self.storage.close)
        self.page = PracticePage(
            self.storage,
            settings=PracticeSettings("python", MODE_WORDS, 10, "corne-4x6"),
        )
        self.page.practice.session._target = "if x:\n    y"
        self.page.practice.session._states = [CharState.PENDING] * 11
        self.page.refresh()

    def test_dropdown_shows_code_language(self):
        self.assertEqual(self.page.language_dropdown.get_selected(), 2)

    def test_enter_types_newline_and_flashes_enter(self):
        self.page._on_commit(None, "if x:")
        enter = self.page.practice.layout.keys_for_special("enter")
        self.assertEqual(self.page.keyboard._hint, frozenset(enter))
        self.assertIn("⏎", self.page.text_label.get_text())
        handled = self.page._on_key_pressed(None, Gdk.KEY_Return, 0, 0)
        self.assertTrue(handled)
        session = self.page.practice.session
        self.assertEqual(session.position, 10)  # newline typed, indent skipped
        self.assertEqual(session.keystrokes, 6)
        self.assertEqual(self.page.keyboard._pressed, frozenset(enter))

    def test_tab_is_swallowed_without_typing(self):
        self.assertTrue(self.page._on_key_pressed(None, Gdk.KEY_Tab, 0, 0))
        self.assertEqual(self.page.practice.session.keystrokes, 0)

    def test_word_counter_counts_whitespace_tokens(self):
        self.page._on_commit(None, "if x:")
        self.page._on_key_pressed(None, Gdk.KEY_Return, 0, 0)
        self.assertTrue(self.page.stats_label.get_label().endswith("2/10"))

    def test_enter_completing_session_saves_it(self):
        self.page.practice.session._target = "a\nb\n"
        self.page.practice.session._states = [CharState.PENDING] * 4
        self.page._on_commit(None, "a")
        self.page._on_key_pressed(None, Gdk.KEY_Return, 0, 0)
        self.page._on_commit(None, "b")
        self.page._on_key_pressed(None, Gdk.KEY_Return, 0, 0)
        self.assertEqual(self.storage.list_sessions()[0].result.language, "python")


class WindowTest(unittest.TestCase):
    def make_storage(self):
        storage = Storage(":memory:")
        self.addCleanup(storage.close)
        return storage

    def test_window_shows_practice_page(self):
        from typeledger.window import TypeLedgerWindow

        window = TypeLedgerWindow(storage=self.make_storage())
        self.assertIsInstance(window.practice_page, PracticePage)

    def test_window_has_practice_and_progress_views(self):
        from typeledger.ui.progress_page import ProgressPage
        from typeledger.window import TypeLedgerWindow

        window = TypeLedgerWindow(storage=self.make_storage())
        self.assertIsInstance(window.progress_page, ProgressPage)
        self.assertIs(window.view_stack.get_child_by_name("practice"), window.practice_page)
        self.assertIs(window.view_stack.get_child_by_name("progress"), window.progress_page)
        self.assertEqual(window.view_stack.get_visible_child_name(), "practice")

    def test_progress_refreshes_after_session_completed(self):
        from typeledger.window import TypeLedgerWindow

        storage = self.make_storage()
        window = TypeLedgerWindow(storage=storage)
        page = window.progress_page
        self.assertIs(page.stack.get_visible_child(), page.empty_page)
        window.practice_page._on_commit(None, window.practice_page.practice.session.target)
        self.assertIs(page.stack.get_visible_child(), page.content_page)
        self.assertEqual(page.total_sessions_label.get_label(), "1")

    def test_progress_refreshes_when_shown(self):
        from typeledger.window import TypeLedgerWindow

        storage = self.make_storage()
        window = TypeLedgerWindow(storage=storage)
        window.practice_page.practice.type_text(window.practice_page.practice.session.target)
        page = window.progress_page
        self.assertIs(page.stack.get_visible_child(), page.empty_page)
        window.view_stack.set_visible_child_name("progress")
        self.assertIs(page.stack.get_visible_child(), page.content_page)

    def test_practice_page_loses_focus_on_progress_view(self):
        from gi.repository import GLib

        from typeledger.window import TypeLedgerWindow

        window = TypeLedgerWindow(storage=self.make_storage())
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


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class ViewSwitchSessionTest(unittest.TestCase):
    def make_window(self, settings):
        from typeledger.window import TypeLedgerWindow

        self.storage = Storage(":memory:")
        self.addCleanup(self.storage.close)
        self.clock = FakeClock()
        self.window = TypeLedgerWindow(storage=self.storage)
        self.page = self.window.practice_page
        self.page.practice = Practice(settings, self.storage, clock=self.clock)
        self.page._show_settings(settings)
        self.page.refresh()
        self.completed = []
        self.page.connect("session-completed", lambda _page: self.completed.append(True))

    def test_started_time_session_is_cancelled_on_progress_view(self):
        settings = PracticeSettings("en", MODE_TIME, 15, "corne-4x6")
        self.make_window(settings)
        self.page._on_commit(None, self.page.practice.session.target[:10])
        self.window.view_stack.set_visible_child_name("progress")
        self.assertEqual(self.storage.list_sessions(), [])
        self.window.view_stack.set_visible_child_name("practice")
        session = self.page.practice.session
        self.assertEqual(session.position, 0)
        self.assertFalse(session.started)
        self.assertEqual(self.page.practice.settings, settings)
        self.assertEqual(self.page.mode_group.get_active_name(), MODE_TIME)
        self.assertEqual(self.page.value_group.get_active_name(), "15")

    def test_time_running_out_on_progress_view_saves_nothing(self):
        self.make_window(PracticeSettings("en", MODE_TIME, 15, "corne-4x6"))
        self.page._on_commit(None, self.page.practice.session.target[:10])
        self.window.view_stack.set_visible_child_name("progress")
        self.clock.now = 100.0
        self.page._on_tick()
        self.assertEqual(self.storage.list_sessions(), [])
        self.assertEqual(self.completed, [])
        self.assertIsNone(self.page.practice.last_result)

    def test_started_words_session_survives_view_switch(self):
        settings = PracticeSettings("en", MODE_WORDS, 10, "corne-4x6")
        self.make_window(settings)
        target = self.page.practice.session.target
        self.page._on_commit(None, target[:5])
        self.window.view_stack.set_visible_child_name("progress")
        self.window.view_stack.set_visible_child_name("practice")
        session = self.page.practice.session
        self.assertEqual(session.target, target)
        self.assertEqual(session.position, 5)
        self.assertTrue(session.started)

    def test_unstarted_time_session_survives_view_switch(self):
        self.make_window(PracticeSettings("en", MODE_TIME, 15, "corne-4x6"))
        session = self.page.practice.session
        self.window.view_stack.set_visible_child_name("progress")
        self.window.view_stack.set_visible_child_name("practice")
        self.assertIs(self.page.practice.session, session)


if __name__ == "__main__":
    unittest.main()
