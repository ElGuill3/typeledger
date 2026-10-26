import json
import re
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

from tests.test_translations import PLACEHOLDER, _parse_po

ROOT = Path(__file__).resolve().parent.parent
EXTENSION_ROOT = ROOT / "extension"
UUID = "typeledger@elguill3.github.io"
EXTENSION_DIR = EXTENSION_ROOT / UUID
GJS = shutil.which("gjs")
GNOME_EXTENSIONS = shutil.which("gnome-extensions")


def _run(args, **kwargs):
    return subprocess.run(args, capture_output=True, text=True, timeout=60, **kwargs)


@unittest.skipUnless(GJS, "gjs is not installed")
class StreakLogicTests(unittest.TestCase):
    def test_gjs_streak_suite_passes(self):
        result = _run([GJS, "-m", str(EXTENSION_ROOT / "tests" / "test_streak.js")])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("FAIL", result.stdout)

    def test_streak_module_is_pure(self):
        source = (EXTENSION_DIR / "streak.js").read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"^\s*import\b|\bimport\s*\(", source, re.MULTILINE))


class MetadataTests(unittest.TestCase):
    def setUp(self):
        self.metadata = json.loads((EXTENSION_DIR / "metadata.json").read_text(encoding="utf-8"))

    def test_uuid_matches_directory(self):
        self.assertEqual(self.metadata["uuid"], EXTENSION_DIR.name)

    def test_targets_gnome_shell_50(self):
        self.assertEqual(self.metadata["shell-version"], ["50"])

    def test_required_keys(self):
        for key in ("uuid", "name", "description", "shell-version", "url", "gettext-domain"):
            with self.subTest(key=key):
                self.assertIn(key, self.metadata)
        self.assertEqual(self.metadata["name"], "TypeLedger Streak")
        self.assertEqual(self.metadata["url"], "https://github.com/ElGuill3/typeledger")


class ExtensionTranslationTests(unittest.TestCase):
    def setUp(self):
        po_dir = EXTENSION_ROOT / "po"
        self.template = {e["msgid"] for e in _parse_po(po_dir / "typeledger-extension.pot") if e["msgid"]}
        entries = _parse_po(po_dir / "es.po")
        self.header = next(e for e in entries if e["msgid"] == "")
        self.entries = [e for e in entries if e["msgid"]]

    def test_header_declares_plurals(self):
        self.assertIn("Plural-Forms: nplurals=2; plural=(n != 1);", self.header["msgstr"])

    def test_catalog_covers_template(self):
        self.assertTrue(self.template)
        self.assertEqual(self.template - {e["msgid"] for e in self.entries}, set())

    def test_entries_are_translated_and_keep_placeholders(self):
        for entry in self.entries:
            with self.subTest(msgid=entry["msgid"]):
                self.assertNotIn("fuzzy", entry["flags"])
                self.assertTrue(entry["msgstr"].strip())
                self.assertEqual(
                    sorted(PLACEHOLDER.findall(entry["msgid"])),
                    sorted(PLACEHOLDER.findall(entry["msgstr"])),
                )
                self.assertEqual(entry["msgid"].count("%d") > 0, "%d" in entry["msgstr"])


@unittest.skipUnless(GJS, "gjs is not installed")
class ExtensionSyntaxTests(unittest.TestCase):
    def test_extension_module_parses(self):
        # Outside GNOME Shell the resource:/// imports cannot be resolved, but GJS
        # parses the whole module before linking its imports and never evaluates
        # it, so a SyntaxError here means the file is broken while an import
        # resolution error means it parsed.
        path = EXTENSION_DIR / "extension.js"
        self.assertTrue(path.is_file(), "extension.js is missing")
        result = _run([GJS, "-m", str(path)])
        output = result.stdout + result.stderr
        self.assertNotIn("SyntaxError", output)
        if result.returncode != 0:
            self.assertRegex(output, r"ImportError|Unable to load|Failed to resolve imports")

    def test_parse_check_detects_syntax_errors(self):
        broken = (EXTENSION_DIR / "extension.js").read_text(encoding="utf-8") + "\nconst = ;\n"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "extension.js"
            path.write_text(broken, encoding="utf-8")
            result = _run([GJS, "-m", str(path)])
        self.assertIn("SyntaxError", result.stdout + result.stderr)


@unittest.skipUnless(GNOME_EXTENSIONS, "gnome-extensions is not installed")
class PackTests(unittest.TestCase):
    def test_pack_includes_sources_and_spanish_catalog(self):
        domain = json.loads((EXTENSION_DIR / "metadata.json").read_text(encoding="utf-8"))[
            "gettext-domain"
        ]
        with tempfile.TemporaryDirectory() as out:
            result = _run(
                [
                    GNOME_EXTENSIONS,
                    "pack",
                    str(EXTENSION_DIR),
                    "--podir=../po",
                    "--extra-source=streak.js",
                    "--force",
                    "-o",
                    out,
                ]
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            archive = Path(out) / f"{UUID}.shell-extension.zip"
            self.assertTrue(archive.is_file(), result.stdout + result.stderr)
            with zipfile.ZipFile(archive) as bundle:
                names = set(bundle.namelist())
        for name in (
            "extension.js",
            "streak.js",
            "metadata.json",
            "stylesheet.css",
            f"locale/es/LC_MESSAGES/{domain}.mo",
        ):
            with self.subTest(name=name):
                self.assertIn(name, names)


if __name__ == "__main__":
    unittest.main()
