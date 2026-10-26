import json
import os
import tempfile
import unittest

from typeledger.core.layout import (
    available_layouts,
    load_layout,
    load_layout_file,
)


def _minimal_layout():
    return {
        "id": "tiny",
        "name": "Tiny",
        "keys": [
            {"id": "A", "x": 0, "y": 0, "hand": "left", "finger": "index"},
            {"id": "B", "x": 1, "y": 0, "hand": "right", "finger": "index"},
        ],
        "layers": [["a", "Shift"]],
    }


class BundledLayoutsTest(unittest.TestCase):
    def test_available_layouts_lists_both_corne_models(self):
        layouts = dict(available_layouts())
        self.assertEqual(layouts["corne-4x6"], "Corne 4x6 + 3 thumbs")
        self.assertEqual(layouts["corne-3x6"], "Corne 3x6 + 3 thumbs")

    def test_key_counts(self):
        self.assertEqual(len(load_layout("corne-4x6").keys), 54)
        self.assertEqual(len(load_layout("corne-3x6").keys), 42)

    def test_layers_match_key_count_and_ids_are_unique(self):
        for layout_id, _name in available_layouts():
            layout = load_layout(layout_id)
            self.assertEqual(layout.id, layout_id)
            ids = [key.id for key in layout.keys]
            self.assertEqual(len(ids), len(set(ids)), layout_id)
            self.assertEqual(len(layout.layers), 3, layout_id)
            for layer in layout.layers:
                self.assertEqual(len(layer), len(layout.keys), layout_id)

    def test_4x6_has_one_encoder_per_half(self):
        self.assertEqual(len(load_layout("corne-4x6").encoders), 2)

    def test_unknown_layout_id_raises(self):
        with self.assertRaises(ValueError):
            load_layout("does-not-exist")


class KeysForCharTest(unittest.TestCase):
    def setUp(self):
        self.l46 = load_layout("corne-4x6")
        self.l36 = load_layout("corne-3x6")

    def test_lowercase_letter_is_a_single_key(self):
        self.assertEqual(self.l46.keys_for_char("a"), ("L2C1",))
        self.assertEqual(self.l36.keys_for_char("a"), ("L1C1",))

    def test_uppercase_letter_uses_opposite_hand_shift(self):
        self.assertEqual(self.l46.keys_for_char("A"), ("R3C5", "L2C1"))
        self.assertEqual(self.l46.keys_for_char("P"), ("L3C0", "R1C4"))
        self.assertEqual(self.l36.keys_for_char("A"), ("L2C0", "L1C1"))

    def test_digit(self):
        self.assertEqual(self.l46.keys_for_char("1"), ("L0C1",))
        self.assertEqual(self.l36.keys_for_char("1"), ("LT1", "L0C1"))

    def test_shifted_symbol_prefers_layer0_shift_over_layer1(self):
        self.assertEqual(self.l46.keys_for_char("!"), ("R3C5", "L0C1"))
        # 3x6: layer 1 + Shift (lower + Shift + 1) comes before layer 2.
        self.assertEqual(self.l36.keys_for_char("!"), ("LT1", "L2C0", "L0C1"))

    def test_brace(self):
        self.assertEqual(self.l46.keys_for_char("{"), ("LT1", "R2C2"))
        self.assertEqual(self.l36.keys_for_char("{"), ("RT1", "R2C2"))

    def test_shifted_punctuation(self):
        self.assertEqual(self.l46.keys_for_char("<"), ("L3C0", "R3C2"))

    def test_space(self):
        self.assertEqual(self.l46.keys_for_char(" "), ("LT2",))
        self.assertEqual(self.l36.keys_for_char(" "), ("LT2",))

    def test_unreachable_char(self):
        self.assertEqual(self.l46.keys_for_char("é"), ())
        self.assertEqual(self.l36.keys_for_char("É"), ())

    def test_keys_for_special(self):
        self.assertEqual(self.l46.keys_for_special("backspace"), ("R0C5",))
        self.assertEqual(self.l36.keys_for_special("backspace"), ("R0C5",))
        self.assertEqual(self.l46.keys_for_special("shift"), ("L3C0", "R3C5"))
        self.assertEqual(self.l46.keys_for_special("enter"), ("RT0",))
        self.assertEqual(self.l46.keys_for_special("unknown"), ())

    def test_transparent_label_falls_through(self):
        self.assertEqual(self.l46.resolved_labels(1)[0], "Esc")
        self.assertEqual(self.l46.resolved_labels(1)[1], "!")


class LayoutFileValidationTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def _write(self, data):
        path = os.path.join(self.tmpdir, "layout.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(data, handle)
        return path

    def test_valid_user_file_loads(self):
        layout = load_layout_file(self._write(_minimal_layout()))
        self.assertEqual(layout.keys_for_char("A"), ("B", "A"))
        self.assertEqual(layout.encoders, ())

    def test_layer_length_mismatch(self):
        data = _minimal_layout()
        data["layers"] = [["a"]]
        with self.assertRaisesRegex(ValueError, "layer 0"):
            load_layout_file(self._write(data))

    def test_duplicate_key_id(self):
        data = _minimal_layout()
        data["keys"][1]["id"] = "A"
        with self.assertRaisesRegex(ValueError, "duplicate"):
            load_layout_file(self._write(data))

    def test_unknown_layer_reference(self):
        data = _minimal_layout()
        data["layers"] = [["a", "MO(3)"]]
        with self.assertRaisesRegex(ValueError, "MO\\(3\\)"):
            load_layout_file(self._write(data))

    def test_invalid_finger(self):
        data = _minimal_layout()
        data["keys"][0]["finger"] = "toe"
        with self.assertRaisesRegex(ValueError, "finger"):
            load_layout_file(self._write(data))

    def test_malformed_json(self):
        path = os.path.join(self.tmpdir, "broken.json")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("{not json")
        with self.assertRaises(ValueError):
            load_layout_file(path)


if __name__ == "__main__":
    unittest.main()
