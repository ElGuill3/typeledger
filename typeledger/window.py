import gettext

from gi.repository import Adw, Gio, Gtk

_ = gettext.gettext


class TypeLedgerWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_title("TypeLedger")
        self.set_default_size(1000, 720)

        menu = Gio.Menu()
        menu.append(_("About TypeLedger"), "app.about")
        menu.append(_("Quit"), "app.quit")
        menu_button = Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu)

        header = Adw.HeaderBar()
        header.pack_end(menu_button)

        self.content = Adw.StatusPage(
            title=_("Practice"),
            description=_("Typing practice is coming soon."),
        )

        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(header)
        toolbar_view.set_content(self.content)
        self.set_content(toolbar_view)
