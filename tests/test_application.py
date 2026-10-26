import contextlib
import io
import json
import os
import tempfile
import unittest
from unittest import mock

from typeledger.core.models import (
    LANGUAGES,
    TIME_OPTIONS,
    WORD_OPTIONS,
)


class OptionsContractTest(unittest.TestCase):
    def test_practice_options_match_spec(self):
        self.assertEqual(TIME_OPTIONS, (15, 30, 60, 120))
        self.assertEqual(WORD_OPTIONS, (10, 25, 50, 100))
        self.assertEqual(LANGUAGES, ("en", "es"))


class ApplicationImportTest(unittest.TestCase):
    def test_application_constructs_without_display(self):
        from typeledger import APP_ID
        from typeledger.application import TypeLedgerApplication

        app = TypeLedgerApplication()
        self.assertEqual(app.get_application_id(), APP_ID)


class OpenStorageTest(unittest.TestCase):
    def test_uses_xdg_data_home_database(self):
        from typeledger.application import open_storage

        data_home = tempfile.mkdtemp()
        with mock.patch.dict(os.environ, {"XDG_DATA_HOME": data_home}):
            storage, unavailable = open_storage()
        storage.close()
        self.assertFalse(unavailable)
        self.assertTrue(os.path.exists(os.path.join(data_home, "typeledger", "typeledger.db")))

    def test_falls_back_to_memory_when_database_cannot_be_opened(self):
        from typeledger.application import open_storage

        blocker = tempfile.NamedTemporaryFile(delete=False)
        blocker.close()
        # A regular file where the data directory should be makes mkdir fail.
        with mock.patch.dict(os.environ, {"XDG_DATA_HOME": blocker.name}):
            storage, unavailable = open_storage()
        self.addCleanup(storage.close)
        self.assertTrue(unavailable)
        self.assertEqual(storage.list_sessions(), [])
        os.unlink(blocker.name)


class CreateWindowTest(unittest.TestCase):
    def test_exports_summary_at_startup_with_real_storage(self):
        from typeledger.application import create_window

        data_home = tempfile.mkdtemp()
        with mock.patch.dict(os.environ, {"XDG_DATA_HOME": data_home}):
            window = create_window()
        self.addCleanup(window.storage.close)
        path = os.path.join(data_home, "typeledger", "summary.json")
        with open(path, encoding="utf-8") as summary:
            self.assertEqual(json.load(summary)["schema"], 1)

    def test_unwritable_data_dir_falls_back_without_crashing_or_exporting(self):
        from typeledger.application import create_window

        blocker = tempfile.NamedTemporaryFile(delete=False)
        blocker.close()
        self.addCleanup(os.unlink, blocker.name)
        stderr = io.StringIO()
        with mock.patch.dict(os.environ, {"XDG_DATA_HOME": blocker.name}):
            with contextlib.redirect_stderr(stderr):
                window = create_window()
        self.addCleanup(window.storage.close)
        self.assertIn("cannot open history database", stderr.getvalue())
        self.assertNotIn("cannot export summary", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
