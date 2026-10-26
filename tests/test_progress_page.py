import unittest
from datetime import date, datetime, timedelta, timezone

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw  # noqa: E402

from typeledger.core.layout import load_layout  # noqa: E402
from typeledger.core.models import MODE_TIME, CharStat, SessionResult  # noqa: E402
from typeledger.core.storage import Storage  # noqa: E402
from typeledger.ui.progress_page import ProgressPage  # noqa: E402

Adw.init()

LOCAL = timezone(timedelta(hours=-6))
TODAY = date(2026, 10, 25)
LAYOUT_ID = "corne-4x6"


def session(days_ago, *, wpm=40.0, accuracy=0.9, duration=60.0, stats=None):
    day = TODAY - timedelta(days=days_ago)
    return SessionResult(
        started_at=datetime(day.year, day.month, day.day, 12, 0, tzinfo=LOCAL),
        mode=MODE_TIME,
        mode_value=60,
        language="en",
        layout_id=LAYOUT_ID,
        duration_s=duration,
        wpm=wpm,
        raw_wpm=wpm,
        accuracy=accuracy,
        correct_chars=100,
        incorrect_chars=5,
        keystrokes=110,
        char_stats=stats or {},
    )


class ProgressPageEmptyTest(unittest.TestCase):
    def test_empty_history_shows_status_page(self):
        page = ProgressPage(Storage(":memory:"), today=lambda: TODAY)
        page.refresh(LAYOUT_ID)
        self.assertIs(page.stack.get_visible_child(), page.empty_page)
        self.assertIsInstance(page.empty_page, Adw.StatusPage)


class ProgressPageDataTest(unittest.TestCase):
    def setUp(self):
        self.storage = Storage(":memory:")
        # Practiced 1 and 2 days ago, a gap 3 days ago, then 4 days ago.
        self.storage.save_session(session(1, wpm=50.0, stats={"q": CharStat(1, 9)}))
        self.storage.save_session(session(2, wpm=30.0, stats={"a": CharStat(20, 0)}))
        self.storage.save_session(session(4, wpm=20.0))
        self.page = ProgressPage(self.storage, today=lambda: TODAY)
        self.page.refresh(LAYOUT_ID)

    def test_data_shows_content(self):
        self.assertIs(self.page.stack.get_visible_child(), self.page.content_page)

    def test_streak_label_shows_current_streak_and_today_pending(self):
        self.assertIn("2", self.page.streak_label.get_label())
        self.assertIn("🔥", self.page.streak_label.get_label())
        self.assertEqual(
            self.page.today_label.get_label(), "Practice today to keep your streak"
        )

    def test_today_done_after_practicing_today(self):
        self.storage.save_session(session(0))
        self.page.refresh(LAYOUT_ID)
        self.assertIn("3", self.page.streak_label.get_label())
        self.assertEqual(self.page.today_label.get_label(), "Practiced today")

    def test_overview_totals(self):
        self.assertEqual(self.page.total_sessions_label.get_label(), "3")
        self.assertEqual(self.page.best_wpm_label.get_label(), "50")
        self.assertEqual(self.page.total_time_label.get_label(), "3 min")

    def test_range_defaults_to_30_and_toggle_changes_point_count(self):
        self.assertEqual(self.page.range_group.get_active_name(), "30")
        self.assertEqual(len(self.page.wpm_points), 30)
        for days in (7, 90, 30):
            self.page.range_group.set_active_name(str(days))
            self.assertEqual(len(self.page.wpm_points), days)
            self.assertEqual(len(self.page.accuracy_points), days)

    def test_day_without_sessions_is_a_gap(self):
        points = dict(self.page.wpm_points)
        self.assertIsNone(points[TODAY - timedelta(days=3)])
        self.assertIsNone(points[TODAY])
        self.assertEqual(points[TODAY - timedelta(days=1)], 50.0)
        accuracy = dict(self.page.accuracy_points)
        self.assertAlmostEqual(accuracy[TODAY - timedelta(days=1)], 90.0)

    def test_heat_applied_for_error_prone_char(self):
        layout = load_layout(LAYOUT_ID)
        q_key = layout.keys_for_char("q")[-1]
        a_key = layout.keys_for_char("a")[-1]
        self.assertEqual(self.page.heat[q_key], 1.0)
        self.assertNotIn(a_key, self.page.heat)
        self.assertEqual(self.page.keyboard._heat, self.page.heat)


if __name__ == "__main__":
    unittest.main()
