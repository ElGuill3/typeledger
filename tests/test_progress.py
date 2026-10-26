import unittest
from datetime import date, datetime, timedelta, timezone

from typeledger.core.layout import Key, KeyboardLayout, load_layout
from typeledger.core.models import MODE_TIME, CharStat, SessionResult
from typeledger.core.progress import (
    CharErrorRate,
    Streak,
    char_error_rates,
    compute_streak,
    key_heat,
    overview,
    sessions_in_range,
)

LOCAL = timezone(timedelta(hours=-3))
TODAY = date(2026, 10, 25)


def _session(day, *, hour=12, minute=0, wpm=40.0, accuracy=0.9, duration=30.0, stats=None):
    return SessionResult(
        started_at=datetime(day.year, day.month, day.day, hour, minute, tzinfo=LOCAL),
        mode=MODE_TIME,
        mode_value=30,
        language="en",
        layout_id="corne-3x6",
        duration_s=duration,
        wpm=wpm,
        raw_wpm=wpm,
        accuracy=accuracy,
        correct_chars=0,
        incorrect_chars=0,
        keystrokes=0,
        char_stats=stats or {},
    )


def _ago(n):
    return TODAY - timedelta(days=n)


class StreakTest(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(compute_streak([], TODAY), Streak(0, 0, False))

    def test_today_practiced(self):
        self.assertEqual(compute_streak([_ago(2), _ago(1), TODAY], TODAY), Streak(3, 3, True))

    def test_alive_when_only_yesterday(self):
        self.assertEqual(compute_streak([_ago(2), _ago(1)], TODAY), Streak(2, 2, False))

    def test_broken_by_gap(self):
        self.assertEqual(compute_streak([_ago(3), _ago(2)], TODAY), Streak(0, 2, False))
        self.assertEqual(compute_streak([_ago(3), _ago(1), TODAY], TODAY), Streak(2, 2, True))

    def test_longest_older_than_current(self):
        days = [_ago(10), _ago(9), _ago(8), _ago(7), TODAY]
        self.assertEqual(compute_streak(days, TODAY), Streak(1, 4, True))

    def test_duplicates(self):
        days = [_ago(1), _ago(1), TODAY, TODAY, TODAY]
        self.assertEqual(compute_streak(days, TODAY), Streak(2, 2, True))

    def test_future_dates_ignored(self):
        days = [_ago(-1), _ago(-2), _ago(-3), _ago(1)]
        self.assertEqual(compute_streak(days, TODAY), Streak(1, 1, False))

    def test_late_night_session_counts_for_local_day(self):
        late = _session(_ago(1), hour=23, minute=30)
        # 23:30 at -03:00 is already the next day in UTC.
        self.assertEqual(late.started_at.astimezone(timezone.utc).date(), TODAY)
        self.assertEqual(overview([late], TODAY).streak, Streak(1, 1, False))


class SessionsInRangeTest(unittest.TestCase):
    def test_one_entry_per_session_oldest_first(self):
        # Newest first, like Storage.list_sessions(); same-day sessions stay apart.
        results = [
            _session(TODAY, hour=18, wpm=50.0),
            _session(TODAY, hour=9, wpm=30.0),
            _session(_ago(2), wpm=20.0),
        ]
        picked = sessions_in_range(results, days=7, today=TODAY)
        self.assertEqual([r.wpm for r in picked], [20.0, 30.0, 50.0])

    def test_same_start_keeps_input_order(self):
        results = [_session(TODAY, wpm=10.0), _session(TODAY, wpm=20.0)]
        picked = sessions_in_range(results, days=1, today=TODAY)
        self.assertEqual([r.wpm for r in picked], [10.0, 20.0])

    def test_out_of_window_ignored(self):
        results = [_session(_ago(7)), _session(_ago(-1)), _session(_ago(6), wpm=33.0)]
        picked = sessions_in_range(results, days=7, today=TODAY)
        self.assertEqual([r.wpm for r in picked], [33.0])

    def test_late_night_session_counts_for_local_day(self):
        results = [_session(_ago(1), hour=23, minute=59, wpm=44.0)]
        self.assertEqual(sessions_in_range(results, days=1, today=TODAY), [])
        self.assertEqual(len(sessions_in_range(results, days=2, today=TODAY)), 1)


class CharErrorRatesTest(unittest.TestCase):
    def test_aggregates_and_min_samples_boundary(self):
        results = [
            _session(TODAY, stats={"a": CharStat(2, 1), "b": CharStat(3, 0), " ": CharStat(5, 0)}),
            _session(_ago(1), stats={"a": CharStat(1, 1), "b": CharStat(1, 0)}),
        ]
        rates = char_error_rates(results)
        self.assertEqual(rates["a"], CharErrorRate("a", 3, 2, 0.4))
        self.assertNotIn("b", rates)  # 4 samples
        self.assertIn(" ", rates)
        rates = char_error_rates(results, min_samples=4)
        self.assertEqual(rates["b"].rate, 0.0)

    def test_empty(self):
        self.assertEqual(char_error_rates([]), {})


def _tiny_layout():
    keys = (
        Key("A", 0, 0, 1, 1, 0, "left", "index"),
        Key("B", 1, 0, 1, 1, 0, "right", "index"),
        Key("SH", 2, 0, 1, 1, 0, "right", "pinky"),
        Key("SP", 3, 0, 1, 1, 0, "left", "thumb"),
    )
    return KeyboardLayout("tiny", "Tiny", keys, (("a", "b", "Shift", "Space"),))


def _rate(ch, rate):
    return CharErrorRate(ch, 10, int(rate * 10), rate)


class KeyHeatTest(unittest.TestCase):
    def test_normalized_by_highest_level(self):
        heat = key_heat(_tiny_layout(), {"a": _rate("a", 0.4), "b": _rate("b", 0.1), " ": _rate(" ", 0.2)})
        self.assertAlmostEqual(heat["A"], 1.0)
        self.assertAlmostEqual(heat["B"], 0.25)
        self.assertAlmostEqual(heat["SP"], 0.5)
        self.assertNotIn("SH", heat)

    def test_upper_and_lower_case_take_max_on_char_key(self):
        heat = key_heat(_tiny_layout(), {"a": _rate("a", 0.1), "A": _rate("A", 0.3), "b": _rate("b", 0.6)})
        self.assertAlmostEqual(heat["A"], 0.5)
        self.assertAlmostEqual(heat["B"], 1.0)
        self.assertNotIn("SH", heat)  # Shift is not the char key

    def test_unreachable_char_skipped(self):
        heat = key_heat(_tiny_layout(), {"z": _rate("z", 0.9), "a": _rate("a", 0.3)})
        self.assertEqual(heat, {"A": 1.0})

    def test_all_zero_rates_is_empty(self):
        self.assertEqual(key_heat(_tiny_layout(), {"a": _rate("a", 0.0), "b": _rate("b", 0.0)}), {})
        self.assertEqual(key_heat(_tiny_layout(), {}), {})

    def test_bundled_layout_shifted_char(self):
        layout = load_layout("corne-3x6")
        heat = key_heat(layout, {"A": _rate("A", 0.5)})
        self.assertEqual(heat, {layout.keys_for_char("a")[-1]: 1.0})


class OverviewTest(unittest.TestCase):
    def test_empty_history(self):
        result = overview([], TODAY)
        self.assertEqual(result.streak, Streak(0, 0, False))
        self.assertEqual(result.total_sessions, 0)
        self.assertEqual(result.total_seconds, 0.0)
        self.assertEqual(result.best_wpm, 0.0)
        self.assertEqual(result.recent_avg_wpm, 0.0)
        self.assertEqual(result.recent_avg_accuracy, 0.0)
        self.assertEqual(result.recent_sessions, 0)

    def test_totals_and_recent_window_boundary(self):
        results = [
            _session(_ago(7), wpm=90.0, accuracy=0.5, duration=60.0),  # outside 7 days
            _session(_ago(6), wpm=30.0, accuracy=0.8, duration=30.0),  # first recent day
            _session(TODAY, wpm=50.0, accuracy=1.0, duration=15.0),
        ]
        result = overview(results, TODAY)
        self.assertEqual(result.total_sessions, 3)
        self.assertAlmostEqual(result.total_seconds, 105.0)
        self.assertAlmostEqual(result.best_wpm, 90.0)
        self.assertEqual(result.recent_sessions, 2)
        self.assertAlmostEqual(result.recent_avg_wpm, 40.0)
        self.assertAlmostEqual(result.recent_avg_accuracy, 0.9)
        self.assertEqual(result.streak, Streak(1, 2, True))  # _ago(7), _ago(6) are consecutive

    def test_custom_recent_days(self):
        results = [_session(_ago(1), wpm=20.0), _session(TODAY, wpm=40.0)]
        result = overview(results, TODAY, recent_days=1)
        self.assertEqual(result.recent_sessions, 1)
        self.assertAlmostEqual(result.recent_avg_wpm, 40.0)


if __name__ == "__main__":
    unittest.main()
