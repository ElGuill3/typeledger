import gettext
import locale
import os
import sqlite3
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio  # noqa: E402

from typeledger import APP_ID, VERSION  # noqa: E402
from typeledger.core.storage import Storage, default_db_path  # noqa: E402
from typeledger.window import TypeLedgerWindow  # noqa: E402

_ = gettext.gettext


def setup_translations():
    localedir = os.environ.get("TYPELEDGER_LOCALEDIR")
    try:
        locale.setlocale(locale.LC_ALL, "")
    except locale.Error:
        pass
    gettext.bindtextdomain("typeledger", localedir)
    gettext.textdomain("typeledger")


def open_storage():
    """Open the history database, falling back to memory if it cannot be opened."""
    try:
        return Storage(default_db_path()), False
    except (OSError, sqlite3.Error) as error:
        print(f"typeledger: cannot open history database: {error}", file=sys.stderr)
        return Storage(":memory:"), True


class TypeLedgerApplication(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self._add_action("quit", lambda *_args: self.quit(), ["<primary>q"])
        self._add_action("about", self._on_about)

    def do_activate(self):
        window = self.props.active_window
        if window is None:
            storage, unavailable = open_storage()
            window = TypeLedgerWindow(
                storage, history_unavailable=unavailable, application=self
            )
        window.present()

    def _add_action(self, name, callback, shortcuts=None):
        action = Gio.SimpleAction.new(name, None)
        action.connect("activate", callback)
        self.add_action(action)
        if shortcuts:
            self.set_accels_for_action(f"app.{name}", shortcuts)

    def _on_about(self, *_args):
        about = Adw.AboutDialog(
            application_name="TypeLedger",
            application_icon=APP_ID,
            version=VERSION,
            developer_name="ElGuill3",
            comments=_("Typing practice for split ergonomic keyboards"),
        )
        about.present(self.props.active_window)


def main():
    setup_translations()
    return TypeLedgerApplication().run(sys.argv)
