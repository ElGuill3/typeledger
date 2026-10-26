import gettext
import locale

from gi.repository import Adw, Gdk, GLib, Gtk

from typeledger.core.keys import special_key_name
from typeledger.core.layout import available_layouts
from typeledger.core.models import (
    LANGUAGES,
    MODE_TIME,
    MODE_WORDS,
    TIME_OPTIONS,
    WORD_OPTIONS,
)
from typeledger.core.practice import Practice, PracticeSettings
from typeledger.core.text_display import build_markup, line_index, wrap_lines
from typeledger.ui.keyboard_view import KeyboardView

_ = gettext.gettext

LINE_WIDTH = 56
VISIBLE_LINES = 3
TICK_MS = 100
PRESS_FLASH_MS = 160
DEFAULT_LAYOUT = "corne-4x6"


def default_language():
    lang = (locale.getlocale()[0] or "").lower()
    return "es" if lang.startswith("es") else "en"


def language_names():
    return {"en": _("English"), "es": _("Spanish")}


class PracticePage(Gtk.Box):
    """Practice text on top, live stats, and the keyboard layout underneath."""

    __gtype_name__ = "TypeLedgerPracticePage"

    def __init__(self, storage, *, settings=None, **kwargs):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=18, **kwargs)
        self.set_margin_top(18)
        self.set_margin_bottom(18)
        self.set_margin_start(24)
        self.set_margin_end(24)
        self.set_focusable(True)

        settings = settings or PracticeSettings(
            default_language(), MODE_WORDS, 25, DEFAULT_LAYOUT
        )
        self.practice = Practice(settings, storage)
        self._layouts = available_layouts()
        self._flash_source = None
        self._updating_options = False

        self.append(self._build_options())
        self.stats_label = Gtk.Label(css_classes=["title-4", "numeric"])
        self.append(self.stats_label)

        self.text_label = Gtk.Label(
            use_markup=True,
            justify=Gtk.Justification.LEFT,
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
            vexpand=True,
            css_classes=["monospace"],
        )
        self.append(self.text_label)

        self.keyboard = KeyboardView()
        self.keyboard.set_layout(self.practice.layout)
        self.append(self.keyboard)

        self._setup_input()
        self._tick_source = GLib.timeout_add(TICK_MS, self._on_tick)
        self.connect("unrealize", self._on_unrealize)
        self.refresh()

    # Options

    def _build_options(self):
        bar = Gtk.Box(spacing=12, halign=Gtk.Align.CENTER)

        self.mode_group = Adw.ToggleGroup(css_classes=["round"])
        self.mode_group.add(Adw.Toggle(name=MODE_TIME, label=_("Time")))
        self.mode_group.add(Adw.Toggle(name=MODE_WORDS, label=_("Words")))
        self.mode_group.connect("notify::active-name", self._on_mode_changed)
        bar.append(self.mode_group)

        self.value_group = Adw.ToggleGroup(css_classes=["round"])
        self.value_group.connect("notify::active-name", self._on_option_changed)
        bar.append(self.value_group)

        names = language_names()
        self.language_dropdown = Gtk.DropDown.new_from_strings(
            [names[code] for code in LANGUAGES]
        )
        self.language_dropdown.set_tooltip_text(_("Text language"))
        self.language_dropdown.connect("notify::selected", self._on_option_changed)
        bar.append(self.language_dropdown)

        self.layout_dropdown = Gtk.DropDown.new_from_strings(
            [name for _id, name in self._layouts]
        )
        self.layout_dropdown.set_tooltip_text(_("Keyboard layout"))
        self.layout_dropdown.connect("notify::selected", self._on_option_changed)
        bar.append(self.layout_dropdown)

        restart = Gtk.Button(
            icon_name="view-refresh-symbolic", tooltip_text=_("Restart")
        )
        restart.connect("clicked", lambda _button: self.restart())
        bar.append(restart)

        self._show_settings(self.practice.settings)
        return bar

    def _fill_values(self, mode, selected):
        self.value_group.remove_all()
        options = TIME_OPTIONS if mode == MODE_TIME else WORD_OPTIONS
        for value in options:
            label = _("{seconds} s").format(seconds=value) if mode == MODE_TIME else str(value)
            self.value_group.add(Adw.Toggle(name=str(value), label=label))
        if selected not in options:
            selected = options[1]
        self.value_group.set_active_name(str(selected))

    def _show_settings(self, settings):
        self._updating_options = True
        self.mode_group.set_active_name(settings.mode)
        self._fill_values(settings.mode, settings.mode_value)
        self.language_dropdown.set_selected(LANGUAGES.index(settings.language))
        layout_ids = [layout_id for layout_id, _name in self._layouts]
        self.layout_dropdown.set_selected(layout_ids.index(settings.layout_id))
        self._updating_options = False

    def _on_mode_changed(self, *_args):
        if self._updating_options:
            return
        self._updating_options = True
        self._fill_values(self.mode_group.get_active_name(), None)
        self._updating_options = False
        self._on_option_changed()

    def _on_option_changed(self, *_args):
        if self._updating_options or self.value_group.get_active_name() is None:
            return
        settings = PracticeSettings(
            language=LANGUAGES[self.language_dropdown.get_selected()],
            mode=self.mode_group.get_active_name(),
            mode_value=int(self.value_group.get_active_name()),
            layout_id=self._layouts[self.layout_dropdown.get_selected()][0],
        )
        self.restart(settings)

    # Session

    def restart(self, settings=None):
        self.practice.restart(settings)
        self.keyboard.set_layout(self.practice.layout)
        self.keyboard.set_pressed(())
        self.refresh()
        self.grab_focus()

    def refresh(self):
        session = self.practice.session
        lines = wrap_lines(session.target, LINE_WIDTH)
        first = line_index(lines, session.position)
        accent = Adw.StyleManager.get_default().get_accent_color_rgba().to_string()
        markup_lines = [
            build_markup(
                session.target,
                session.states,
                position=session.position,
                start=line_start,
                end=line_end,
                accent=_hex_color(accent),
            )
            for line_start, line_end in lines[first : first + VISIBLE_LINES]
        ]
        self.text_label.set_markup(
            '<span size="x-large">' + "\n".join(markup_lines) + "</span>"
        )

        layer, keys = self.practice.next_hint()
        self.keyboard.set_layer(layer)
        self.keyboard.set_hint(keys)
        self._refresh_stats()

    def _refresh_stats(self):
        practice = self.practice
        session = practice.session
        if practice.settings.mode == MODE_TIME:
            remaining = max(0, practice.settings.mode_value - int(session.elapsed()))
            progress = _("{seconds} s").format(seconds=remaining)
        else:
            typed_words = session.target[: session.position].count(" ")
            progress = f"{typed_words}/{practice.settings.mode_value}"
        accuracy = session.live_accuracy() if session.keystrokes else 1.0
        self.stats_label.set_label(
            _("{wpm} WPM · {accuracy}% · {progress}").format(
                wpm=round(session.live_wpm()),
                accuracy=round(accuracy * 100),
                progress=progress,
            )
        )

    def _on_tick(self):
        if self.practice.tick():
            self.refresh()
            self._show_results()
        elif self.practice.session.started and self.practice.last_result is None:
            self._refresh_stats()
        return GLib.SOURCE_CONTINUE

    def _on_unrealize(self, *_args):
        if self._tick_source:
            GLib.source_remove(self._tick_source)
            self._tick_source = None

    def _show_results(self):
        result = self.practice.last_result
        body = _(
            "{wpm} WPM · {accuracy}% accuracy\n"
            "Raw: {raw} WPM · Time: {seconds} s"
        ).format(
            wpm=round(result.wpm),
            accuracy=round(result.accuracy * 100),
            raw=round(result.raw_wpm),
            seconds=round(result.duration_s),
        )
        if self.practice.save_error is not None:
            body += "\n\n" + _("This session could not be saved.")
        dialog = Adw.AlertDialog(heading=_("Session complete"), body=body)
        dialog.add_response("again", _("Practice again"))
        dialog.set_default_response("again")
        dialog.set_close_response("again")
        dialog.connect("response", lambda *_args: self.restart())
        dialog.present(self)

    # Input

    def _setup_input(self):
        self.im_context = Gtk.IMMulticontext()
        self.im_context.connect("commit", self._on_commit)

        controller = Gtk.EventControllerKey()
        controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        controller.set_im_context(self.im_context)
        controller.connect("key-pressed", self._on_key_pressed)
        self.add_controller(controller)
        self.im_context.set_client_widget(self)

        focus = Gtk.EventControllerFocus()
        focus.connect("enter", lambda *_args: self.im_context.focus_in())
        focus.connect("leave", lambda *_args: self.im_context.focus_out())
        self.add_controller(focus)

    def _on_commit(self, _im_context, text):
        pressed = []
        for char in text:
            pressed.extend(self.practice.layout.keys_for_char(char))
        completed = self.practice.type_text(text)
        self._flash(pressed)
        self.refresh()
        if completed:
            self._show_results()

    def _on_key_pressed(self, _controller, keyval, _keycode, state):
        name = special_key_name(Gdk.keyval_name(keyval))
        if name is None:
            return False
        self._flash(self.practice.layout.keys_for_special(name))
        if name == "backspace":
            self.practice.backspace()
            self.refresh()
            return True
        # Let shortcuts (Ctrl+Q, ...) through; swallow the rest so focused
        # option widgets never react to practice keystrokes.
        return name in ("tab", "enter", "esc")

    def _flash(self, key_ids):
        self.keyboard.set_pressed(key_ids)
        if self._flash_source:
            GLib.source_remove(self._flash_source)
        self._flash_source = GLib.timeout_add(PRESS_FLASH_MS, self._clear_flash)

    def _clear_flash(self):
        self._flash_source = None
        self.keyboard.set_pressed(())
        return GLib.SOURCE_REMOVE


def _hex_color(rgba_string):
    rgba = Gdk.RGBA()
    rgba.parse(rgba_string)
    return "#{:02x}{:02x}{:02x}".format(
        round(rgba.red * 255), round(rgba.green * 255), round(rgba.blue * 255)
    )
