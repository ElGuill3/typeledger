import re
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ICONS_DIR = ROOT / "data" / "icons"
APP_ID = "io.github.elguill3.TypeLedger"
FULL_COLOR = ICONS_DIR / "hicolor" / "scalable" / "apps" / f"{APP_ID}.svg"
SYMBOLIC = ICONS_DIR / "hicolor" / "symbolic" / "apps" / f"{APP_ID}-symbolic.svg"

SVG_NS = "{http://www.w3.org/2000/svg}"
XLINK_HREF = "{http://www.w3.org/1999/xlink}href"
COLOR = re.compile(r"#[0-9a-fA-F]{3,8}\b|rgba?\([^)]*\)")
SYMBOLIC_COLORS = {"#222", "#222222"}


def _local(tag):
    return tag.rsplit("}", 1)[-1]


def _colors(element):
    """Yield every color value used by fill/stroke attributes and styles."""
    for node in element.iter():
        for name in ("fill", "stroke", "stop-color", "color", "style"):
            value = node.get(name)
            if value:
                yield from COLOR.findall(value)
        if _local(node.tag) == "style" and node.text:
            yield from COLOR.findall(node.text)


class IconFileTests(unittest.TestCase):
    def _assert_clean_svg(self, path, view_box):
        self.assertTrue(path.is_file(), f"missing icon {path}")
        root = ET.parse(path).getroot()
        self.assertEqual(root.tag, f"{SVG_NS}svg")
        self.assertEqual(root.get("viewBox"), view_box)
        for node in root.iter():
            tag = _local(node.tag)
            self.assertNotIn(tag, {"image", "text", "foreignObject", "script"})
            for name in (XLINK_HREF, "href"):
                ref = node.get(name)
                if ref is not None:
                    self.assertTrue(
                        ref.startswith("#"), f"external reference {ref!r} in {path.name}"
                    )
        return root

    def test_full_color_icon(self):
        root = self._assert_clean_svg(FULL_COLOR, "0 0 128 128")
        # A full-color icon uses more than one color.
        self.assertGreater(len({c.lower() for c in _colors(root)}), 2)

    def test_symbolic_icon_uses_a_single_recolorable_color(self):
        root = self._assert_clean_svg(SYMBOLIC, "0 0 16 16")
        colors = {c.lower() for c in _colors(root)}
        self.assertTrue(colors, "symbolic icon declares no fill color")
        self.assertLessEqual(colors, SYMBOLIC_COLORS)
        for node in root.iter():
            stroke = node.get("stroke")
            self.assertIn(stroke, (None, "none"), "symbolic icon must not use strokes")

    def test_meson_installs_both_icons(self):
        meson = (ROOT / "data" / "meson.build").read_text(encoding="utf-8")
        self.assertIn("icons/hicolor/scalable/apps", meson)
        self.assertIn("icons/hicolor/symbolic/apps", meson)
        self.assertIn(f"{APP_ID}.svg", meson)
        self.assertIn(f"{APP_ID}-symbolic.svg", meson)


if __name__ == "__main__":
    unittest.main()
