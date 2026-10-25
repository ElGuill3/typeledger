import dataclasses
import os
import shutil
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from typeledger.core import storage
from typeledger.core.models import MODE_TIME, MODE_WORDS, CharStat, SessionResult
from typeledger.core.storage import Storage, StoredSession, default_db_path

MINUS_3 = timezone(timedelta(hours=-3))


def make_result(**overrides):
    values = dict(
        started_at=datetime(2026, 10, 25, 18, 30, 15, 123456, tzinfo=MINUS_3),
        mode=MODE_TIME,
        mode_value=30,
        language="es",
        layout_id="corne-4x6",
        duration_s=30.0,
        wpm=42.5,
        raw_wpm=45.25,
        accuracy=0.9375,
        correct_chars=106,
        incorrect_chars=7,
        keystrokes=120,
        char_stats={"a": CharStat(hits=12, misses=1), "ñ": CharStat(hits=2, misses=3), " ": CharStat(hits=20)},
    )
    values.update(overrides)
    return SessionResult(**values)


def row_counts(store):
    sessions = store._conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    key_stats = store._conn.execute("SELECT COUNT(*) FROM key_stats").fetchone()[0]
    return sessions, key_stats


class TempDirMixin:
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="typeledger-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)


class RoundTripTest(unittest.TestCase):
    def test_full_result_round_trips(self):
        result = make_result()
        with Storage(":memory:") as store:
            session_id = store.save_session(result)
            sessions = store.list_sessions()

        self.assertEqual(sessions, [StoredSession(id=session_id, result=result)])
        loaded = sessions[0].result
        self.assertEqual(loaded.started_at.utcoffset(), timedelta(hours=-3))
        self.assertEqual(loaded.started_at.isoformat(), result.started_at.isoformat())
        self.assertEqual(dict(loaded.char_stats), dict(result.char_stats))

    def test_empty_char_stats_round_trip(self):
        result = make_result(char_stats={})
        with Storage(":memory:") as store:
            store.save_session(result)
            self.assertEqual(store.list_sessions()[0].result, result)
            self.assertEqual(row_counts(store), (1, 0))

    def test_stored_session_is_frozen(self):
        stored = StoredSession(id=1, result=make_result())
        with self.assertRaises(dataclasses.FrozenInstanceError):
            stored.id = 2

    def test_started_at_stored_as_iso_with_offset(self):
        with Storage(":memory:") as store:
            store.save_session(make_result())
            stored = store._conn.execute("SELECT started_at FROM sessions").fetchone()[0]
        self.assertEqual(stored, "2026-10-25T18:30:15.123456-03:00")


class LocalDateTest(unittest.TestCase):
    def test_local_date_uses_local_wall_clock_not_utc(self):
        # 23:30 at -03:00 is already the next day in UTC.
        late = datetime(2026, 10, 25, 23, 30, tzinfo=MINUS_3)
        with Storage(":memory:") as store:
            store.save_session(make_result(started_at=late))
            local_date = store._conn.execute("SELECT local_date FROM sessions").fetchone()[0]
        self.assertEqual(local_date, "2026-10-25")


class OrderingTest(unittest.TestCase):
    def setUp(self):
        self.store = Storage(":memory:")
        self.addCleanup(self.store.close)
        base = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)
        self.oldest = make_result(started_at=base)
        # Later instant but an earlier-looking wall clock in its own offset.
        self.newest = make_result(started_at=(base + timedelta(hours=2)).astimezone(MINUS_3))
        self.middle = make_result(started_at=base + timedelta(hours=1))
        self.ids = {
            "middle": self.store.save_session(self.middle),
            "oldest": self.store.save_session(self.oldest),
            "newest": self.store.save_session(self.newest),
        }

    def test_newest_first(self):
        listed = self.store.list_sessions()
        self.assertEqual(
            [s.id for s in listed],
            [self.ids["newest"], self.ids["middle"], self.ids["oldest"]],
        )

    def test_limit(self):
        listed = self.store.list_sessions(limit=2)
        self.assertEqual([s.id for s in listed], [self.ids["newest"], self.ids["middle"]])
        self.assertEqual(self.store.list_sessions(limit=0), [])

    def test_invalid_limit(self):
        for limit in (-1, 1.5, True, "2"):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                self.store.list_sessions(limit=limit)


class SchemaTest(TempDirMixin, unittest.TestCase):
    def test_creates_parent_dirs_and_version_is_1(self):
        path = self.tmp / "nested" / "dir" / "typeledger.db"
        with Storage(path) as store:
            version = store._conn.execute("PRAGMA user_version").fetchone()[0]
            foreign_keys = store._conn.execute("PRAGMA foreign_keys").fetchone()[0]
        self.assertTrue(path.exists())
        self.assertEqual(version, 1)
        self.assertEqual(foreign_keys, 1)

    def test_memory_version_is_1(self):
        with Storage(":memory:") as store:
            self.assertEqual(store._conn.execute("PRAGMA user_version").fetchone()[0], 1)

    def test_reopen_keeps_data_and_does_not_rerun_v1(self):
        path = self.tmp / "typeledger.db"
        result = make_result()
        with Storage(path) as store:
            session_id = store.save_session(result)

        calls = []
        v1 = storage.MIGRATIONS[0]

        def spy(conn):
            calls.append("v1")
            v1(conn)

        with mock.patch.object(storage, "MIGRATIONS", [spy]):
            with Storage(path) as store:
                self.assertEqual(calls, [])
                self.assertEqual(store._conn.execute("PRAGMA user_version").fetchone()[0], 1)
                self.assertEqual(store.list_sessions(), [StoredSession(id=session_id, result=result)])

    def test_only_pending_migrations_run(self):
        path = self.tmp / "typeledger.db"
        Storage(path).close()

        calls = []
        with mock.patch.object(storage, "MIGRATIONS", [storage.MIGRATIONS[0], lambda conn: calls.append("v2")]):
            with Storage(path) as store:
                self.assertEqual(store._conn.execute("PRAGMA user_version").fetchone()[0], 2)
            with Storage(path):
                pass
        self.assertEqual(calls, ["v2"])

    def test_close_is_idempotent(self):
        store = Storage(":memory:")
        store.close()
        store.close()


class ValidationTest(unittest.TestCase):
    INVALID = {
        "unknown mode": dict(mode="zen"),
        "unknown language": dict(language="fr"),
        "accuracy above 1": dict(accuracy=1.01),
        "accuracy below 0": dict(accuracy=-0.01),
        "accuracy nan": dict(accuracy=float("nan")),
        "negative duration": dict(duration_s=-1.0),
        "infinite duration": dict(duration_s=float("inf")),
        "negative wpm": dict(wpm=-0.5),
        "negative raw wpm": dict(raw_wpm=-0.5),
        "negative correct chars": dict(correct_chars=-1),
        "negative incorrect chars": dict(incorrect_chars=-1),
        "negative keystrokes": dict(keystrokes=-1),
        "non-int keystrokes": dict(keystrokes=1.5),
        "bool keystrokes": dict(keystrokes=True),
        "non-positive mode value": dict(mode_value=0),
        "empty layout id": dict(layout_id=""),
        "naive started_at": dict(started_at=datetime(2026, 10, 25, 18, 30)),
        "non-datetime started_at": dict(started_at="2026-10-25T18:30:00+00:00"),
        "negative char hits": dict(char_stats={"a": CharStat(hits=-1)}),
        "negative char misses": dict(char_stats={"a": CharStat(misses=-1)}),
        "empty char key": dict(char_stats={"": CharStat(hits=1)}),
        "non-CharStat value": dict(char_stats={"a": (1, 0)}),
    }

    def test_invalid_input_raises_and_writes_nothing(self):
        with Storage(":memory:") as store:
            store.save_session(make_result())
            before = row_counts(store)
            for name, overrides in self.INVALID.items():
                with self.subTest(name), self.assertRaises(ValueError):
                    store.save_session(make_result(**overrides))
                self.assertEqual(row_counts(store), before, name)

    def test_words_mode_and_boundaries_are_valid(self):
        with Storage(":memory:") as store:
            store.save_session(make_result(mode=MODE_WORDS, mode_value=25, accuracy=0.0, wpm=0.0, keystrokes=0))
            store.save_session(make_result(accuracy=1.0, language="en"))
            self.assertEqual(row_counts(store)[0], 2)


class TransactionTest(unittest.TestCase):
    def test_key_stats_failure_rolls_back_session(self):
        with Storage(":memory:") as store:
            store.save_session(make_result())
            before = row_counts(store)
            bad = make_result(char_stats={"a": CharStat(hits=1), "b": CharStat(hits=-5)})
            # Bypass validation so the failure happens inside the key_stats insert.
            with mock.patch.object(storage, "_validate", lambda result: None):
                with self.assertRaises(sqlite3.Error):
                    store.save_session(bad)
            self.assertEqual(row_counts(store), before)
            # The connection stays usable after the rollback.
            store.save_session(make_result())
            self.assertEqual(row_counts(store)[0], before[0] + 1)


class DefaultDbPathTest(TempDirMixin, unittest.TestCase):
    def test_honors_xdg_data_home(self):
        with mock.patch.dict(os.environ, {"XDG_DATA_HOME": str(self.tmp)}):
            self.assertEqual(default_db_path(), self.tmp / "typeledger" / "typeledger.db")

    def test_falls_back_to_local_share(self):
        env = {k: v for k, v in os.environ.items() if k != "XDG_DATA_HOME"}
        env["HOME"] = str(self.tmp)
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(default_db_path(), self.tmp / ".local" / "share" / "typeledger" / "typeledger.db")

    def test_empty_xdg_data_home_falls_back(self):
        with mock.patch.dict(os.environ, {"XDG_DATA_HOME": "", "HOME": str(self.tmp)}):
            self.assertEqual(default_db_path(), self.tmp / ".local" / "share" / "typeledger" / "typeledger.db")

    def test_does_not_create_anything(self):
        with mock.patch.dict(os.environ, {"XDG_DATA_HOME": str(self.tmp)}):
            default_db_path()
        self.assertEqual(list(self.tmp.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
