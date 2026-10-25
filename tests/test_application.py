import unittest

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


if __name__ == "__main__":
    unittest.main()
