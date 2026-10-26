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

    def _key_region(self, view, key_id):
        """Pixel offsets that change when key_id is pressed (its keycap area)."""
        plain = bytes(self._render(view).get_data())
        view.set_pressed([key_id])
        pressed = bytes(self._render(view).get_data())
        view.set_pressed([])
        return [i for i in range(0, len(plain), 4) if plain[i : i + 4] != pressed[i : i + 4]]

    @staticmethod
    def _redness(data, region):
        """Mean red excess over green/blue in the region (ARGB32 is BGRA in memory)."""
        total = 0
        for i in region:
            b, g, r = data[i], data[i + 1], data[i + 2]
            total += r - (g + b) / 2
        return total / len(region)

    def _heat_view(self):
        from typeledger.ui.keyboard_view import KeyboardView

        view = KeyboardView()
        view.set_layout(load_layout("corne-4x6"))
        return view

    def test_heat_paints_hot_keys_red(self):
        view = self._heat_view()
        hot = self._key_region(view, "L2C1")
        cold = self._key_region(view, "L2C2")
        view.set_heat({"L2C1": 1.0, "L2C2": 0.0})
        data = bytes(self._render(view).get_data())
        strong = [i for i in hot if data[i + 2] > 150 and data[i + 1] < 80 and data[i] < 80]
        self.assertGreater(len(strong), len(hot) // 2)
        self.assertFalse([i for i in cold if data[i + 2] > 150 and data[i + 1] < 80])

    def test_heat_level_scales_redness(self):
        view = self._heat_view()
        region = self._key_region(view, "L2C1")
        view.set_heat({"L2C1": 0.3})
        mild = self._redness(bytes(self._render(view).get_data()), region)
        view.set_heat({"L2C1": 1.0})
        hot = self._redness(bytes(self._render(view).get_data()), region)
        self.assertGreater(mild, 0)
        self.assertGreater(hot, mild)

    def test_clearing_heat_restores_drawing(self):
        view = self._heat_view()
        before = bytes(self._render(view).get_data())
        view.set_heat({"L2C1": 0.8, "R1C3": 0.4})
        self.assertNotEqual(before, bytes(self._render(view).get_data()))
        view.set_heat({})
        self.assertEqual(before, bytes(self._render(view).get_data()))

    def test_heat_ignores_unknown_ids_and_clamps(self):
        view = self._heat_view()
        view.set_heat({"NOPE": 0.5, "L2C1": 2.0, "L2C2": -1})
        clamped = bytes(self._render(view).get_data())
        view.set_heat({"L2C1": 1.0, "L2C2": 0.0})
        self.assertEqual(clamped, bytes(self._render(view).get_data()))

    def test_pressed_wins_over_heat(self):
        view = self._heat_view()
        view.set_pressed(["L2C1"])
        pressed = bytes(self._render(view).get_data())
        view.set_heat({"L2C1": 1.0})
        self.assertEqual(pressed, bytes(self._render(view).get_data()))

    def test_hint_wins_over_heat(self):
        view = self._heat_view()
        view.set_hint(["L2C1"])
        hinted = bytes(self._render(view).get_data())
        view.set_heat({"L2C1": 1.0})
        self.assertEqual(hinted, bytes(self._render(view).get_data()))

    def test_renders_empty_without_layout(self):
        from typeledger.ui.keyboard_view import KeyboardView

        view = KeyboardView()
        view.set_pressed(["L0C0"])
        surface = self._render(view, 200, 100)
        self.assertFalse(any(surface.get_data()))


if __name__ == "__main__":
    unittest.main()
