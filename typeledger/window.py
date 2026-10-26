import gettext

from gi.repository import Adw, Gio, Gtk

from typeledger.ui.practice_page import PracticePage
from typeledger.ui.progress_page import ProgressPage

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

        self.practice_page = PracticePage(storage)
        self.progress_page = ProgressPage(storage)
        self.practice_page.connect("session-completed", lambda *_args: self._refresh_progress())

        self.view_stack = Adw.ViewStack()
        self.view_stack.add_titled_with_icon(
            self.practice_page, "practice", _("Practice"), "input-keyboard-symbolic"
        )
        self.view_stack.add_titled_with_icon(
            self.progress_page, "progress", _("Progress"), "x-office-presentation-symbolic"
        )
        self.view_stack.connect("notify::visible-child-name", self._on_view_changed)

        header = Adw.HeaderBar(
            title_widget=Adw.ViewSwitcher(
                stack=self.view_stack, policy=Adw.ViewSwitcherPolicy.WIDE
            )
        )
        header.pack_end(menu_button)

        self.toast_overlay = Adw.ToastOverlay(child=self.view_stack)
        if history_unavailable:
            self.toast_overlay.add_toast(
                Adw.Toast(title=_("History is unavailable; sessions will not be kept."))
            )

        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(header)
        toolbar_view.set_content(self.toast_overlay)
        self.set_content(toolbar_view)
        self._refresh_progress()
        self.practice_page.grab_focus()

    def _refresh_progress(self):
        self.progress_page.refresh(self.practice_page.practice.settings.layout_id)

    def _on_view_changed(self, *_args):
        if self.view_stack.get_visible_child_name() == "progress":
            # A timed session cannot be paused; leaving it would let the clock
            # finish it unseen, so drop it and offer a fresh one on return.
            self.practice_page.cancel_running_time_session()
            self._refresh_progress()
            # The stack keeps focus on the hidden practice page, which would
            # keep capturing keystrokes; move it out explicitly.
            if not self.progress_page.child_focus(Gtk.DirectionType.TAB_FORWARD):
                self.set_focus(None)
        else:
            self.practice_page.grab_focus()
