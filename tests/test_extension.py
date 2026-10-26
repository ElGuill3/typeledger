import datetime
import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
import time
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
GNOME_SHELL = shutil.which("gnome-shell")
DBUS_RUN_SESSION = shutil.which("dbus-run-session")
PROBE_DIR = EXTENSION_ROOT / "tests" / "panel-probe@typeledger.test"
PROBE_UUID = PROBE_DIR.name


def _run(args, **kwargs):
    return subprocess.run(args, capture_output=True, text=True, timeout=60, **kwargs)


STACK_FRAME = re.compile(r"^\s*\S*@\S+:\d+(:\d+)?\s*$")


def extension_js_errors(log, uuids=(UUID, PROBE_UUID)):
    """JS ERROR blocks (message plus stack frames) that mention one of uuids.

    Errors from other parts of the shell are ignored: a throwaway headless
    session logs unrelated ones that say nothing about these extensions."""
    blocks = []
    current = None
    for line in log.splitlines():
        if "JS ERROR" in line:
            current = [line]
            blocks.append(current)
        elif current is not None and STACK_FRAME.match(line):
            current.append(line)
        else:
            current = None
    texts = ("\n".join(block) for block in blocks)
    return [text for text in texts if any(uuid in text for uuid in uuids)]


def shell_major_version():
    output = _run([GNOME_SHELL, "--version"]).stdout
    match = re.search(r"GNOME Shell (\d+)", output)
    return match.group(1) if match else None


@unittest.skipUnless(GJS, "gjs is not installed")
class StreakLogicTests(unittest.TestCase):
    def test_gjs_streak_suite_passes(self):
        result = _run([GJS, "-m", str(EXTENSION_ROOT / "tests" / "test_streak.js")])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("FAIL", result.stdout)

    def test_gjs_reminder_suite_passes(self):
        result = _run([GJS, "-m", str(EXTENSION_ROOT / "tests" / "test_reminder.js")])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_streak_module_is_pure(self):
        source = (EXTENSION_DIR / "streak.js").read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"^\s*import\b|\bimport\s*\(", source, re.MULTILINE))

    def test_reminder_module_is_pure(self):
        source = (EXTENSION_DIR / "reminder.js").read_text(encoding="utf-8")
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


class PanelLabelTests(unittest.TestCase):
    def test_label_never_ellipsizes(self):
        # St.Label ellipsizes by default, which drops its minimum width to ~1px.
        # In a crowded top bar the right box then shrinks this button to its
        # padding while fixed-width indicators keep theirs, leaving an empty mark.
        source = (EXTENSION_DIR / "extension.js").read_text(encoding="utf-8")
        pattern = r"this\._label\.clutter_text\.ellipsize\s*=\s*Pango\.EllipsizeMode\.NONE"
        self.assertIsNotNone(re.search(pattern, source), "the panel label must not ellipsize")


@unittest.skipUnless(
    GNOME_SHELL and DBUS_RUN_SESSION,
    "gnome-shell and dbus-run-session are needed to run a throwaway headless shell",
)
class HeadlessShellTests(unittest.TestCase):
    """Loads the extension in an isolated headless GNOME Shell with its own HOME,
    XDG dirs, D-Bus session and keyfile GSettings backend, so the user's
    session and settings are never touched."""

    def _run_shell(self, root):
        home = root / "home"
        extensions = home / ".local" / "share" / "gnome-shell" / "extensions"
        extensions.mkdir(parents=True)
        shutil.copytree(EXTENSION_DIR, extensions / UUID)
        shutil.copytree(PROBE_DIR, extensions / PROBE_UUID)
        data = home / ".local" / "share" / "typeledger"
        data.mkdir()
        today = datetime.date.today().isoformat()
        (data / "summary.json").write_text(
            json.dumps(
                {
                    "schema": 1,
                    "generated_at": f"{today}T10:00:00",
                    "practiced_days": [today],
                    "longest_streak": 1,
                    "total_sessions": 1,
                    "recent_days": 7,
                    "recent_avg_wpm": 16.0,
                    "recent_avg_accuracy": 0.87,
                    "recent_sessions": 1,
                }
            ),
            encoding="utf-8",
        )
        runtime = root / "run"
        runtime.mkdir(mode=0o700)
        out = root / "out"
        out.mkdir()
        env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith(("DBUS_", "WAYLAND_", "GSETTINGS_"))
            and key not in ("DISPLAY", "XDG_RUNTIME_DIR", "XDG_SESSION_TYPE")
            and not (key.startswith("XDG_") and key.endswith("_HOME"))
        }
        env.update(
            HOME=str(home),
            XDG_DATA_HOME=str(home / ".local" / "share"),
            XDG_CONFIG_HOME=str(home / ".config"),
            XDG_CACHE_HOME=str(home / ".cache"),
            XDG_RUNTIME_DIR=str(runtime),
            GSETTINGS_BACKEND="keyfile",
            # Without these, D-Bus activates gvfs, whose FUSE mount under
            # XDG_RUNTIME_DIR can still be busy when the temp dir is removed.
            GIO_USE_VFS="local",
            GVFS_DISABLE_FUSE="1",
            TYPELEDGER_PROBE_OUT=str(out),
        )
        script = (
            f"gsettings set org.gnome.shell enabled-extensions \"['{UUID}', '{PROBE_UUID}']\" && "
            "exec gnome-shell --headless --wayland --no-x11 --virtual-monitor 1024x768"
        )
        result_path = out / "result.json"
        with open(root / "shell.log", "w", encoding="utf-8") as log:
            shell = subprocess.Popen(
                [DBUS_RUN_SESSION, "--", "sh", "-c", script],
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            try:
                deadline = time.monotonic() + 45
                while not result_path.exists() and shell.poll() is None and time.monotonic() < deadline:
                    time.sleep(0.2)
            finally:
                if shell.poll() is None:
                    os.killpg(shell.pid, signal.SIGTERM)
                try:
                    shell.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    os.killpg(shell.pid, signal.SIGKILL)
                    shell.wait()
        log_text = (root / "shell.log").read_text(encoding="utf-8", errors="replace")
        # gnome-shell is installed, so a missing result is a real failure.
        self.assertTrue(
            result_path.exists(), f"headless gnome-shell gave no probe result:\n{log_text[-2000:]}"
        )
        return json.loads(result_path.read_text(encoding="utf-8")), log_text

    def test_shell_version_is_supported_by_extension_and_probe(self):
        version = shell_major_version()
        self.assertIsNotNone(version, "could not read the gnome-shell version")
        for directory in (EXTENSION_DIR, PROBE_DIR):
            with self.subTest(uuid=directory.name):
                metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
                self.assertIn(version, metadata["shell-version"])

    def test_label_keeps_its_text_width_in_a_crowded_panel(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, log = self._run_shell(Path(tmp))
        self.assertNotIn("error", result, log[-2000:])
        self.assertEqual(extension_js_errors(log), [])
        # The probe really crowded the panel: the right box was given less than
        # it asked for, and the room left for the streak button was below its
        # relaxed natural width.
        right = result["squeezedRightBox"]
        self.assertGreater(result["fillerWidth"], 0, result)
        self.assertLess(right["allocWidth"], right["natWidth"], result)
        room = result["sideWidth"] - result["fillerWidth"] - (
            right["natWidth"] - result["fillerWidth"] - result["squeezedButton"]["natWidth"]
        )
        self.assertLess(room, result["relaxedButton"]["natWidth"], result)
        self.assertLess(
            result["squeezedButton"]["allocWidth"], result["relaxedButton"]["allocWidth"], result
        )
        for state in ("relaxed", "squeezed"):
            with self.subTest(state=state):
                label = result[state]
                self.assertEqual(label["text"], "🔥 1")
                self.assertTrue(label["visible"] and label["mapped"])
                self.assertEqual(label["opacity"], 255)
                self.assertGreater(label["natWidth"], 0)
                self.assertGreaterEqual(label["allocWidth"], label["natWidth"], label)
                self.assertEqual(label["minWidth"], label["natWidth"], label)


class ExtensionJsErrorFilterTests(unittest.TestCase):
    def test_keeps_errors_from_our_extensions_only(self):
        log = "\n".join(
            [
                "gnome-shell: starting",
                "JS ERROR: TypeError: x is undefined",
                "_init@resource:///org/gnome/shell/ui/status/network.js:12:5",
                f"JS ERROR: Extension {UUID}: Error: boom",
                f"enable@file:///tmp/home/extensions/{UUID}/extension.js:40:9",
                "JS ERROR: Error: bad",
                f"_step@file:///tmp/home/extensions/{PROBE_UUID}/extension.js:50:13",
                "@resource:///org/gnome/shell/ui/init.js:21:20",
                f"unrelated line mentioning {UUID}",
            ]
        )
        errors = extension_js_errors(log)
        self.assertEqual(len(errors), 2, errors)
        self.assertIn("Error: boom", errors[0])
        self.assertIn("Error: bad", errors[1])
        self.assertNotIn("unrelated", errors[1])

    def test_ignores_a_log_with_only_foreign_errors(self):
        log = "JS ERROR: TypeError: x is undefined\n_init@resource:///org/gnome/shell/ui/panel.js:1:1"
        self.assertEqual(extension_js_errors(log), [])


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
                    "--extra-source=reminder.js",
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
            "reminder.js",
            "metadata.json",
            "stylesheet.css",
            f"locale/es/LC_MESSAGES/{domain}.mo",
        ):
            with self.subTest(name=name):
                self.assertIn(name, names)


if __name__ == "__main__":
    unittest.main()
