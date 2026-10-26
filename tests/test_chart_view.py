import unittest
from datetime import date, timedelta

import cairo
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw  # noqa: E402

WIDTH, HEIGHT = 600, 200
START = date(2026, 10, 1)


def _days(values):
    return [(START + timedelta(days=i), value) for i, value in enumerate(values)]


class ChartViewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Adw.init()

    def setUp(self):
        accent = Adw.StyleManager.get_default().get_accent_color_rgba()
        self.accent = tuple(round(c * 255) for c in (accent.red, accent.green, accent.blue))

    def _view(self, values):
        from typeledger.ui.chart_view import ChartView

        view = ChartView()
        view.set_title("WPM")
        view.set_points(_days(values))
        return view

    def _render(self, view, width=WIDTH, height=HEIGHT):
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
        view.draw_to(cairo.Context(surface), width, height)
        surface.flush()
        return surface

    def _accent_columns(self, surface):
        """Map x -> number of opaque accent-colored pixels in that column."""
        data = surface.get_data()
        stride = surface.get_stride()
        columns = {}
        for y in range(surface.get_height()):
            for x in range(surface.get_width()):
                i = y * stride + x * 4
                b, g, r, a = data[i], data[i + 1], data[i + 2], data[i + 3]
                if a < 250:
                    continue
                if all(abs(p - q) <= 12 for p, q in zip((r, g, b), self.accent)):
                    columns[x] = columns.get(x, 0) + 1
        return columns

    def test_empty_series_draws_empty_state_without_accent(self):
        for values in ([], [None, None, None]):
            with self.subTest(values=values):
                surface = self._render(self._view(values))
                self.assertTrue(any(surface.get_data()))
                self.assertEqual(self._accent_columns(surface), {})

    def test_series_with_data_draws_accent(self):
        surface = self._render(self._view([30, 42, 38, 50]))
        self.assertTrue(self._accent_columns(surface))

    def test_gap_breaks_the_line(self):
        full = self._accent_columns(self._render(self._view([40, 40, 40])))
        middle = (min(full) + max(full)) // 2
        self.assertIn(middle, full)

        gapped = self._accent_columns(self._render(self._view([40, None, 40])))
        self.assertTrue(gapped)
        for x in range(middle - 3, middle + 4):
            self.assertNotIn(x, gapped)

    def test_auto_range_handles_constant_and_single_point(self):
        for values in ([50, 50, 50], [0, 0], [None, 72, None], [12.5]):
            with self.subTest(values=values):
                view = self._view(values)
                view.set_y_range(None, None)
                self.assertTrue(self._accent_columns(self._render(view)))
                view.set_y_range(0.0, None)
                self.assertTrue(self._accent_columns(self._render(view)))

    def test_explicit_range_and_value_format_are_used(self):
        calls = []

        def spy(value):
            calls.append(value)
            return f"{value:.0f}%"

        view = self._view([90, 95, None, 97])
        view.set_y_range(0.0, 100.0)
        view.set_value_format(spy)
        self._render(view)
        self.assertGreaterEqual(len(calls), 3)
        self.assertLessEqual(len(calls), 6)
        self.assertEqual(min(calls), 0.0)
        self.assertEqual(max(calls), 100.0)

    def test_tiny_sizes_do_not_raise(self):
        view = self._view([10, None, 20])
        for width, height in ((0, 0), (10, 10), (60, 40)):
            self._render(view, max(width, 1), max(height, 1))

    def test_widget_defaults(self):
        view = self._view([])
        self.assertGreaterEqual(view.get_content_height(), 180)
        self.assertTrue(view.get_hexpand())


if __name__ == "__main__":
    unittest.main()
