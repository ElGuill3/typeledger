import ast
import re
import unittest
from pathlib import Path

PO_DIR = Path(__file__).resolve().parent.parent / "po"
PLACEHOLDER = re.compile(r"\{(\w*)[^{}]*\}")


def _parse_po(path):
    """Return a list of entries: dicts with msgid, msgstr and flags."""
    entries = []
    entry = None
    field = None

    def finish():
        if entry is not None and "msgid" in entry:
            entries.append(entry)

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            finish()
            entry, field = None, None
            continue
        if entry is None:
            entry = {"flags": set(), "msgid": "", "msgstr": ""}
        if line.startswith("#,"):
            entry["flags"].update(flag.strip() for flag in line[2:].split(","))
        elif line.startswith("#"):
            continue
        elif line.startswith('"'):
            entry[field] += ast.literal_eval(line)
        else:
            keyword, _, value = line.partition(" ")
            field = "msgstr" if keyword.startswith("msgstr") else keyword
            entry.setdefault(field, "")
            entry[field] += ast.literal_eval(value)
    finish()
    return entries


class SpanishTranslationTests(unittest.TestCase):
    def setUp(self):
        self.po_path = PO_DIR / "es.po"
        self.assertTrue(self.po_path.is_file(), "po/es.po is missing")
        entries = _parse_po(self.po_path)
        self.header = next(e for e in entries if e["msgid"] == "")
        self.entries = [e for e in entries if e["msgid"] != ""]

    def test_linguas_lists_spanish(self):
        languages = (PO_DIR / "LINGUAS").read_text(encoding="utf-8").split()
        self.assertIn("es", languages)

    def test_header_declares_utf8_and_plurals(self):
        self.assertIn("charset=UTF-8", self.header["msgstr"])
        self.assertIn("Plural-Forms: nplurals=2; plural=(n != 1);", self.header["msgstr"])

    def test_has_entries(self):
        self.assertTrue(self.entries)

    def test_every_entry_is_translated_and_not_fuzzy(self):
        for entry in self.entries:
            with self.subTest(msgid=entry["msgid"]):
                self.assertNotIn("fuzzy", entry["flags"])
                self.assertTrue(entry["msgstr"].strip(), "untranslated")

    def test_placeholders_are_preserved(self):
        for entry in self.entries:
            with self.subTest(msgid=entry["msgid"]):
                self.assertEqual(
                    sorted(PLACEHOLDER.findall(entry["msgid"])),
                    sorted(PLACEHOLDER.findall(entry["msgstr"])),
                )

    def test_catalog_covers_template(self):
        pot_path = PO_DIR / "typeledger.pot"
        if not pot_path.is_file():
            self.skipTest("po/typeledger.pot is missing")
        template = {e["msgid"] for e in _parse_po(pot_path) if e["msgid"]}
        translated = {e["msgid"] for e in self.entries}
        self.assertEqual(template - translated, set())


if __name__ == "__main__":
    unittest.main()
