import contextlib
import io
import json
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from typeledger.core import progress
from typeledger.core.models import MODE_WORDS, SessionResult
from typeledger.core.storage import Storage, default_db_path
from typeledger.core.summary import (
    build_summary,
    default_summary_path,
    export_summary,
    write_summary,
)

MINUS_3 = timezone(timedelta(hours=-3))
TODAY = date(2026, 10, 25)
NOW = datetime(2026, 10, 25, 20, 0, tzinfo=MINUS_3)

SCHEMA_TYPES = {
    "schema": int,
    "generated_at": str,
    "practiced_days": list,
    "longest_streak": int,
    "total_sessions": int,
    "recent_days": int,
    "recent_avg_wpm": float,
    "recent_avg_accuracy": float,
    "recent_sessions": int,
}


def result(started_at, *, wpm=50.0, accuracy=0.9, keystrokes=10):
    return SessionResult(
        started_at=started_at,
        mode=MODE_WORDS,
        mode_value=10,
        language="en",
        layout_id="corne-4x6",
        duration_s=30.0,
        wpm=wpm,
        raw_wpm=wpm,
        accuracy=accuracy,
        correct_chars=keystrokes,
        incorrect_chars=0,
        keystrokes=keystrokes,
    )


def on(day, hour=12, minute=0, **kwargs):
    return result(datetime(day.year, day.month, day.day, hour, minute, tzinfo=MINUS_3), **kwargs)


class BuildSummaryTest(unittest.TestCase):
    def test_schema_keys_and_types(self):
        summary = build_summary([on(TODAY)], today=TODAY, now=NOW)
        self.assertEqual(set(summary), set(SCHEMA_TYPES))
        for key, kind in SCHEMA_TYPES.items():
            self.assertIs(type(summary[key]), kind, key)
        self.assertEqual(summary["schema"], 1)
        self.assertEqual(summary["recent_days"], 7)
        self.assertEqual(datetime.fromisoformat(summary["generated_at"]), NOW)
        self.assertTrue(all(type(day) is str for day in summary["practiced_days"]))

    def test_empty_history(self):
        summary = build_summary([], today=TODAY, now=NOW)
        self.assertEqual(summary["practiced_days"], [])
        self.assertEqual(summary["longest_streak"], 0)
        self.assertEqual(summary["total_sessions"], 0)
        self.assertEqual(summary["recent_sessions"], 0)
        self.assertEqual(summary["recent_avg_wpm"], 0.0)
        self.assertEqual(summary["recent_avg_accuracy"], 0.0)
        self.assertIs(type(summary["recent_avg_wpm"]), float)
        self.assertIs(type(summary["recent_avg_accuracy"]), float)

    def test_days_are_sorted_unique_local_dates(self):
        yesterday = TODAY - timedelta(days=1)
        results = [
            on(TODAY),
            # 23:30 at -03:00 is already the next day in UTC; it counts locally.
            on(yesterday, 23, 30),
            on(TODAY, 8),
            on(TODAY - timedelta(days=5)),
        ]
        summary = build_summary(results, today=TODAY, now=NOW)
        self.assertEqual(
            summary["practiced_days"],
            [
                (TODAY - timedelta(days=5)).isoformat(),
                yesterday.isoformat(),
                TODAY.isoformat(),
            ],
        )

    def test_days_are_capped_at_400_keeping_the_most_recent(self):
        results = [on(TODAY - timedelta(days=offset)) for offset in range(450)]
        summary = build_summary(results, today=TODAY, now=NOW)
        days = summary["practiced_days"]
        self.assertEqual(len(days), 400)
        self.assertEqual(days[-1], TODAY.isoformat())
        self.assertEqual(days[0], (TODAY - timedelta(days=399)).isoformat())
        self.assertEqual(summary["total_sessions"], 450)
        self.assertEqual(summary["longest_streak"], 450)

    def test_streak_and_recent_averages_match_progress(self):
        results = [
            on(TODAY, wpm=60.0, accuracy=1.0),
            on(TODAY - timedelta(days=1), wpm=40.0, accuracy=0.8),
            on(TODAY - timedelta(days=6), wpm=30.0, accuracy=0.7),
            on(TODAY - timedelta(days=7), wpm=99.0, accuracy=0.1),
            on(TODAY - timedelta(days=20)),
            on(TODAY - timedelta(days=21)),
            on(TODAY - timedelta(days=22)),
        ]
        summary = build_summary(results, today=TODAY, now=NOW)
        expected = progress.overview(results, TODAY, recent_days=7)
        self.assertEqual(summary["longest_streak"], expected.streak.longest)
        self.assertEqual(summary["longest_streak"], 3)
        self.assertEqual(summary["total_sessions"], expected.total_sessions)
        self.assertEqual(summary["recent_sessions"], expected.recent_sessions)
        self.assertEqual(summary["recent_sessions"], 3)
        self.assertAlmostEqual(summary["recent_avg_wpm"], expected.recent_avg_wpm)
        self.assertAlmostEqual(summary["recent_avg_wpm"], 130.0 / 3)
        self.assertAlmostEqual(summary["recent_avg_accuracy"], expected.recent_avg_accuracy)
        self.assertLessEqual(summary["recent_avg_accuracy"], 1.0)

    def test_summary_is_json_serializable(self):
        summary = build_summary([on(TODAY)], today=TODAY, now=NOW)
        self.assertEqual(json.loads(json.dumps(summary)), summary)


class WriteSummaryTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())

    def test_creates_parent_dirs_and_writes_utf8_json(self):
        path = self.root / "a" / "b" / "summary.json"
        summary = build_summary([on(TODAY)], today=TODAY, now=NOW)
        write_summary(summary, path)
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), summary)

    def test_replaces_existing_file_without_leaving_temp_files(self):
        path = self.root / "summary.json"
        path.write_text("old", encoding="utf-8")
        write_summary({"schema": 1}, path)
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"schema": 1})
        self.assertEqual(os.listdir(self.root), ["summary.json"])

    def test_unwritable_path_raises_oserror_and_leaves_no_temp_files(self):
        blocker = self.root / "blocker"
        blocker.write_text("", encoding="utf-8")
        with self.assertRaises(OSError):
            write_summary({"schema": 1}, blocker / "typeledger" / "summary.json")
        directory = self.root / "dir"
        directory.mkdir()
        # A directory where the file should be makes os.replace fail after the temp write.
        (directory / "summary.json").mkdir()
        with self.assertRaises(OSError):
            write_summary({"schema": 1}, directory / "summary.json")
        self.assertEqual(os.listdir(directory), ["summary.json"])


class DefaultPathAndExportTest(unittest.TestCase):
    def test_default_summary_path_is_next_to_database(self):
        data_home = tempfile.mkdtemp()
        with mock.patch.dict(os.environ, {"XDG_DATA_HOME": data_home}):
            path = default_summary_path()
            self.assertEqual(path, default_db_path().parent / "summary.json")
        self.assertEqual(path, Path(data_home) / "typeledger" / "summary.json")
        self.assertFalse(path.exists())

    def test_export_summary_writes_storage_history(self):
        data_home = tempfile.mkdtemp()
        with Storage(":memory:") as storage:
            storage.save_session(on(TODAY))
            with mock.patch.dict(os.environ, {"XDG_DATA_HOME": data_home}):
                path = export_summary(storage, today=TODAY, now=NOW)
        self.assertEqual(path, Path(data_home) / "typeledger" / "summary.json")
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data["practiced_days"], [TODAY.isoformat()])
        self.assertEqual(data["total_sessions"], 1)

    def test_export_summary_uses_explicit_path(self):
        path = Path(tempfile.mkdtemp()) / "out.json"
        with Storage(":memory:") as storage:
            self.assertEqual(export_summary(storage, path, today=TODAY, now=NOW), path)
        self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["total_sessions"], 0)


class WindowExportTest(unittest.TestCase):
    """The window hook: export at startup and after saved sessions, never crash."""

    def setUp(self):
        import gi

        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
        from gi.repository import Adw

        Adw.init()
        self.root = Path(tempfile.mkdtemp())
        self.storage = Storage(self.root / "history.db")
        self.addCleanup(self.storage.close)

    def make_window(self, summary_path):
        from typeledger.window import TypeLedgerWindow

        return TypeLedgerWindow(self.storage, summary_path=summary_path)

    def test_exports_at_startup(self):
        path = self.root / "out" / "summary.json"
        self.make_window(path)
        self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["total_sessions"], 0)

    def test_without_summary_path_nothing_is_exported(self):
        self.make_window(None)
        self.assertEqual(os.listdir(self.root), ["history.db"])

    def test_exports_after_saved_session(self):
        path = self.root / "summary.json"
        window = self.make_window(path)
        page = window.practice_page
        page._on_commit(None, page.practice.session.target)
        self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["total_sessions"], 1)

    def test_does_not_export_after_zero_keystroke_completion(self):
        path = self.root / "summary.json"
        window = self.make_window(path)
        path.unlink()
        page = window.practice_page
        page.practice.complete()
        self.assertEqual(page.practice.last_result.keystrokes, 0)
        page.emit("session-completed")
        self.assertFalse(path.exists())

    def test_does_not_export_after_failed_save(self):
        path = self.root / "summary.json"
        window = self.make_window(path)
        path.unlink()
        page = window.practice_page
        page.practice.save_error = ValueError("boom")
        page.emit("session-completed")
        self.assertFalse(path.exists())

    def test_export_failure_is_logged_not_raised(self):
        blocker = self.root / "blocker"
        blocker.write_text("", encoding="utf-8")
        stderr = io.StringIO()
        with mock.patch.dict(os.environ, {"XDG_DATA_HOME": str(blocker)}):
            with contextlib.redirect_stderr(stderr):
                window = self.make_window(default_summary_path())
                page = window.practice_page
                page._on_commit(None, page.practice.session.target)
        self.assertEqual(len(self.storage.list_sessions()), 1)
        self.assertEqual(stderr.getvalue().count("typeledger: cannot export summary"), 2)


if __name__ == "__main__":
    unittest.main()
