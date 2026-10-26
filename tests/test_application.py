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


if __name__ == "__main__":
    unittest.main()
