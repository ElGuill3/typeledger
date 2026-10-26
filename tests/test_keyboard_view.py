import unittest

import cairo
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw  # noqa: E402

from typeledger.core.layout import load_layout  # noqa: E402


class KeyboardViewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Adw.init()

    def _render(self, view, width=900, height=320):
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
        context = cairo.Context(surface)
        view.draw_to(context, width, height)
        surface.flush()
        return surface

    def test_renders_layout_with_pressed_and_hint(self):
        from typeledger.ui.keyboard_view import KeyboardView

        view = KeyboardView()
        self.assertGreaterEqual(view.get_content_height(), 260)
        for layout_id in ("corne-4x6", "corne-3x6"):
            layout = load_layout(layout_id)
            view.set_layout(layout)
            view.set_pressed(layout.keys_for_char("A"))
            view.set_hint(layout.keys_for_char("{"))
            for layer in range(len(layout.layers)):
                view.set_layer(layer)
                surface = self._render(view)
                self.assertTrue(any(surface.get_data()), layout_id)

    def test_pressed_and_hint_change_the_drawing(self):
        from typeledger.ui.keyboard_view import KeyboardView

        view = KeyboardView()
        view.set_layout(load_layout("corne-4x6"))
        plain = bytes(self._render(view).get_data())
        view.set_hint(["L2C1"])
        hinted = bytes(self._render(view).get_data())
        view.set_pressed(["L2C1"])
        pressed = bytes(self._render(view).get_data())
        self.assertNotEqual(plain, hinted)
        self.assertNotEqual(hinted, pressed)

    def test_renders_empty_without_layout(self):
        from typeledger.ui.keyboard_view import KeyboardView

        view = KeyboardView()
        view.set_pressed(["L0C0"])
        surface = self._render(view, 200, 100)
        self.assertFalse(any(surface.get_data()))


if __name__ == "__main__":
    unittest.main()
