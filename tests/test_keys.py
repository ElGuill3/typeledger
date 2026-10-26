import unittest

from typeledger.core.keys import special_key_name


class SpecialKeyNameTest(unittest.TestCase):
    def test_maps_gdk_keyval_names_to_layout_specials(self):
        cases = {
            "BackSpace": "backspace",
            "Return": "enter",
            "KP_Enter": "enter",
            "Tab": "tab",
            "ISO_Left_Tab": "tab",
            "space": "space",
            "Shift_L": "shift",
            "Shift_R": "shift",
            "Control_L": "ctrl",
            "Control_R": "ctrl",
            "Alt_L": "alt",
            "Alt_R": "alt",
            "Super_L": "super",
            "Super_R": "super",
            "Escape": "esc",
        }
        for keyval_name, expected in cases.items():
            with self.subTest(keyval_name=keyval_name):
                self.assertEqual(special_key_name(keyval_name), expected)

    def test_printable_and_unknown_names_are_not_specials(self):
        for keyval_name in ("a", "A", "1", "exclam", "dead_acute", "F5", None):
            with self.subTest(keyval_name=keyval_name):
                self.assertIsNone(special_key_name(keyval_name))


if __name__ == "__main__":
    unittest.main()
