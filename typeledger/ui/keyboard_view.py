import gettext
import math

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("PangoCairo", "1.0")

from gi.repository import Adw, Gtk, Pango, PangoCairo  # noqa: E402

_ = gettext.gettext

PADDING = 12  # px around the drawing
KEY_GAP = 0.08  # key units between neighbouring keycaps
CORNER_RADIUS = 0.15  # key units


def _display_label(label):
    """Short keycap text for a layout label."""
    names = {
        "Esc": _("Esc"),
        "Tab": _("Tab"),
        "Bspc": _("Bspc"),
        "Enter": _("Enter"),
        "Space": _("Space"),
        "Shift": "⇧",
        "Ctrl": _("Ctrl"),
        "Alt": _("Alt"),
        "GUI": _("Super"),
        "Left": "←",
        "Down": "↓",
        "Up": "↑",
        "Right": "→",
    }
    if label in names:
        return names[label]
    if label.startswith("MO(") and label.endswith(")"):
        return "MO" + label[3:-1]
    if len(label) == 1:
        return label.upper()
    return label


class KeyboardView(Gtk.DrawingArea):
    """Draws a KeyboardLayout, highlighting pressed and hinted keys."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._layout = None
        self._layer = 0
        self._pressed = frozenset()
        self._hint = frozenset()
        self.set_content_height(260)
        self.set_hexpand(True)
        self.set_draw_func(lambda _area, cr, width, height: self.draw_to(cr, width, height))

    def set_layout(self, layout):
        self._layout = layout
        self._layer = 0
        self.queue_draw()

    def set_layer(self, index):
        self._layer = index
        self.queue_draw()

    def set_pressed(self, key_ids):
        self._pressed = frozenset(key_ids)
        self.queue_draw()

    def set_hint(self, key_ids):
        self._hint = frozenset(key_ids)
        self.queue_draw()

    def draw_to(self, cr, width, height):
        """Render the keyboard onto a cairo context of the given size."""
        layout = self._layout
        if layout is None or width <= 2 * PADDING or height <= 2 * PADDING:
            return

        min_x, min_y, max_x, max_y = self._bounds(layout)
        scale = min(
            (width - 2 * PADDING) / (max_x - min_x),
            (height - 2 * PADDING) / (max_y - min_y),
        )
        cr.translate(
            (width - (max_x - min_x) * scale) / 2 - min_x * scale,
            (height - (max_y - min_y) * scale) / 2 - min_y * scale,
        )

        fg = self.get_color()
        accent = Adw.StyleManager.get_default().get_accent_color_rgba()
        layer = max(0, min(self._layer, len(layout.layers) - 1))
        labels = layout.resolved_labels(layer)

        font = Pango.FontDescription.from_string("Sans")
        font.set_absolute_size(0.32 * scale * Pango.SCALE)
        small_font = font.copy()
        small_font.set_absolute_size(0.24 * scale * Pango.SCALE)

        cr.set_line_width(max(1.0, 0.03 * scale))
        for key, label in zip(layout.keys, labels):
            if label == "":
                continue
            cr.save()
            cr.translate((key.x + key.w / 2) * scale, (key.y + key.h / 2) * scale)
            cr.rotate(math.radians(key.rotation))
            w = (key.w - KEY_GAP) * scale
            h = (key.h - KEY_GAP) * scale
            _rounded_rect(cr, -w / 2, -h / 2, w, h, CORNER_RADIUS * scale)

            pressed = key.id in self._pressed
            if pressed:
                cr.set_source_rgba(accent.red, accent.green, accent.blue, 1.0)
                cr.fill_preserve()
            elif key.id in self._hint:
                cr.set_source_rgba(accent.red, accent.green, accent.blue, 0.35)
                cr.fill_preserve()
            cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.55 * fg.alpha)
            cr.stroke()

            text = _display_label(label)
            pango_layout = PangoCairo.create_layout(cr)
            pango_layout.set_font_description(font if len(text) <= 2 else small_font)
            pango_layout.set_text(text, -1)
            _ink, logical = pango_layout.get_pixel_extents()
            if pressed:
                cr.set_source_rgba(1.0, 1.0, 1.0, 1.0)
            else:
                cr.set_source_rgba(fg.red, fg.green, fg.blue, fg.alpha)
            cr.move_to(-logical.width / 2 - logical.x, -logical.height / 2 - logical.y)
            PangoCairo.show_layout(cr, pango_layout)
            cr.restore()

        cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.55 * fg.alpha)
        for encoder in layout.encoders:
            cr.new_sub_path()
            cr.arc(encoder.x * scale, encoder.y * scale, encoder.r * scale, 0, 2 * math.pi)
            cr.stroke()

    @staticmethod
    def _bounds(layout):
        xs, ys = [], []
        for key in layout.keys:
            cx, cy = key.x + key.w / 2, key.y + key.h / 2
            angle = math.radians(key.rotation)
            cos, sin = math.cos(angle), math.sin(angle)
            for dx, dy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                dx, dy = dx * key.w / 2, dy * key.h / 2
                xs.append(cx + dx * cos - dy * sin)
                ys.append(cy + dx * sin + dy * cos)
        for encoder in layout.encoders:
            xs += [encoder.x - encoder.r, encoder.x + encoder.r]
            ys += [encoder.y - encoder.r, encoder.y + encoder.r]
        return min(xs), min(ys), max(xs), max(ys)


def _rounded_rect(cr, x, y, w, h, r):
    r = min(r, w / 2, h / 2)
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()
