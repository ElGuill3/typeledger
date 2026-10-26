import gettext

from gi.repository import Adw, Gio, Gtk

from typeledger.ui.practice_page import PracticePage

_ = gettext.gettext


class TypeLedgerWindow(Adw.ApplicationWindow):
    def __init__(self, storage, history_unavailable=False, **kwargs):
        super().__init__(**kwargs)
        self.set_title("TypeLedger")
        self.set_default_size(1000, 720)

        menu = Gio.Menu()
        menu.append(_("About TypeLedger"), "app.about")
        menu.append(_("Quit"), "app.quit")
        menu_button = Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu)

        header = Adw.HeaderBar()
        header.pack_end(menu_button)

        self.practice_page = PracticePage(storage)
        self.toast_overlay = Adw.ToastOverlay(child=self.practice_page)
        if history_unavailable:
            self.toast_overlay.add_toast(
                Adw.Toast(title=_("History is unavailable; sessions will not be kept."))
            )

        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(header)
        toolbar_view.set_content(self.toast_overlay)
        self.set_content(toolbar_view)
        self.practice_page.grab_focus()
