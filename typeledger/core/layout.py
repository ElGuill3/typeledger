"""Keyboard layout model: key geometry, layers and char-to-key lookup.

A layout file is JSON with ``id``, ``name``, ``keys`` (geometry in key
units), ``layers`` (one label per key, in key order) and optional
``encoders`` (decorative only).

Labels: a single character means the key outputs that character; named
tokens (``Esc Tab Bspc Enter Space Shift Ctrl Alt GUI MO(n)``) are
special keys; ``""`` is no key; ``"trns"`` falls through to the layer
below. Other multi-character labels are display-only.
"""

import json
import re
from dataclasses import dataclass
from importlib.resources import files

HANDS = ("left", "right")
FINGERS = ("pinky", "ring", "middle", "index", "thumb")

TRANSPARENT = "trns"
NO_KEY = ""

SPECIAL_LABELS = {
    "space": "Space",
    "enter": "Enter",
    "backspace": "Bspc",
    "tab": "Tab",
    "shift": "Shift",
    "ctrl": "Ctrl",
    "alt": "Alt",
    "super": "GUI",
    "esc": "Esc",
}

# US layout: unshifted char -> shifted char.
_SHIFTED = dict(zip("`1234567890-=[]\\;',./", '~!@#$%^&*()_+{}|:"<>?'))
_UNSHIFTED = {shifted: base for base, shifted in _SHIFTED.items()}

_LAYER_KEY = re.compile(r"^MO\((\d+)\)$")


@dataclass(frozen=True)
class Key:
    id: str
    x: float
    y: float
    w: float
    h: float
    rotation: float  # degrees, clockwise, around the key center
    hand: str
    finger: str


@dataclass(frozen=True)
class Encoder:
    x: float  # center, key units
    y: float
    r: float  # radius, key units


@dataclass(frozen=True)
class KeyboardLayout:
    id: str
    name: str
    keys: tuple[Key, ...]
    layers: tuple[tuple[str, ...], ...]
    encoders: tuple[Encoder, ...] = ()

    def resolved_labels(self, layer: int) -> tuple[str, ...]:
        """Labels of ``layer`` with ``trns`` replaced by the lower layer's label."""
        labels = list(self.layers[0])
        for upper in self.layers[1 : layer + 1]:
            labels = [low if up == TRANSPARENT else up for low, up in zip(labels, upper)]
        return tuple(NO_KEY if label == TRANSPARENT else label for label in labels)

    def keys_for_char(self, ch: str) -> tuple[str, ...]:
        """Key ids to press for ``ch``: layer key, then Shift, then the char key."""
        if ch == " ":
            return self.keys_for_special("space")[:1]
        if ch == "\n":
            return self.keys_for_special("enter")[:1]
        if len(ch) != 1:
            return ()
        base = _UNSHIFTED.get(ch)
        if base is None and ch != ch.lower() and len(ch.lower()) == 1:
            base = ch.lower()
        for layer in range(len(self.layers)):
            prefix = ()
            if layer > 0:
                layer_key = self._first_key(0, f"MO({layer})")
                if layer_key is None:
                    continue
                prefix = (layer_key.id,)
            char_key = self._first_key(layer, ch)
            if char_key is not None:
                return prefix + (char_key.id,)
            if base is None:
                continue
            char_key = self._first_key(layer, base)
            shift_key = self._shift_for(layer, char_key)
            if char_key is not None and shift_key is not None:
                return prefix + (shift_key.id, char_key.id)
        return ()

    def keys_for_special(self, name: str) -> tuple[str, ...]:
        """Layer-0 key ids for a special key name; empty if unknown or absent."""
        label = SPECIAL_LABELS.get(name)
        if label is None:
            return ()
        labels = self.resolved_labels(0)
        return tuple(key.id for key, own in zip(self.keys, labels) if own == label)

    def _first_key(self, layer: int, label: str) -> Key | None:
        for key, own in zip(self.keys, self.resolved_labels(layer)):
            if own == label:
                return key
        return None

    def _shift_for(self, layer: int, char_key: Key | None) -> Key | None:
        if char_key is None:
            return None
        shifts = [
            key
            for key, own in zip(self.keys, self.resolved_labels(layer))
            if own == "Shift"
        ]
        for key in shifts:
            if key.hand != char_key.hand:
                return key
        return shifts[0] if shifts else None


def _layouts_dir():
    return files("typeledger") / "data" / "layouts"


def available_layouts() -> list[tuple[str, str]]:
    """Bundled layouts as ``(id, display name)``, sorted by id."""
    result = []
    for entry in sorted(_layouts_dir().iterdir(), key=lambda item: item.name):
        if entry.name.endswith(".json"):
            layout = _parse(entry.read_text(encoding="utf-8"), entry.name)
            result.append((layout.id, layout.name))
    return result


def load_layout(layout_id: str) -> KeyboardLayout:
    """Load a bundled layout by id."""
    entry = _layouts_dir() / f"{layout_id}.json"
    if not entry.is_file():
        raise ValueError(f"Unknown keyboard layout: {layout_id!r}")
    return _parse(entry.read_text(encoding="utf-8"), entry.name)


def load_layout_file(path) -> KeyboardLayout:
    """Load a layout from a user-edited JSON file."""
    with open(path, encoding="utf-8") as handle:
        return _parse(handle.read(), str(path))


def _parse(text: str, source: str) -> KeyboardLayout:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError(f"{source}: invalid JSON: {error}") from error
    if not isinstance(data, dict):
        raise ValueError(f"{source}: top level must be an object")

    layout_id = _require_str(data, "id", source)
    name = _require_str(data, "name", source)

    raw_keys = data.get("keys")
    if not isinstance(raw_keys, list) or not raw_keys:
        raise ValueError(f"{source}: 'keys' must be a non-empty list")
    keys = tuple(_parse_key(raw, index, source) for index, raw in enumerate(raw_keys))
    seen = set()
    for key in keys:
        if key.id in seen:
            raise ValueError(f"{source}: duplicate key id {key.id!r}")
        seen.add(key.id)

    raw_layers = data.get("layers")
    if not isinstance(raw_layers, list) or not raw_layers:
        raise ValueError(f"{source}: 'layers' must be a non-empty list")
    layers = []
    for index, layer in enumerate(raw_layers):
        if not isinstance(layer, list) or not all(isinstance(label, str) for label in layer):
            raise ValueError(f"{source}: layer {index} must be a list of strings")
        if len(layer) != len(keys):
            raise ValueError(
                f"{source}: layer {index} has {len(layer)} labels but there are "
                f"{len(keys)} keys"
            )
        for label in layer:
            match = _LAYER_KEY.match(label)
            if match and not 0 < int(match.group(1)) < len(raw_layers):
                raise ValueError(f"{source}: layer {index} uses {label} but that layer does not exist")
        layers.append(tuple(layer))
    if TRANSPARENT in layers[0]:
        raise ValueError(f"{source}: layer 0 cannot contain '{TRANSPARENT}'")

    raw_encoders = data.get("encoders", [])
    if not isinstance(raw_encoders, list):
        raise ValueError(f"{source}: 'encoders' must be a list")
    encoders = tuple(
        Encoder(
            x=_number(raw, "x", f"{source}: encoder {index}"),
            y=_number(raw, "y", f"{source}: encoder {index}"),
            r=_number(raw, "r", f"{source}: encoder {index}", 0.5),
        )
        for index, raw in enumerate(raw_encoders)
    )

    return KeyboardLayout(layout_id, name, keys, tuple(layers), encoders)


def _parse_key(raw, index: int, source: str) -> Key:
    where = f"{source}: key {index}"
    if not isinstance(raw, dict):
        raise ValueError(f"{where} must be an object")
    key_id = _require_str(raw, "id", where)
    where = f"{source}: key {key_id!r}"
    hand = raw.get("hand")
    if hand not in HANDS:
        raise ValueError(f"{where}: hand must be one of {', '.join(HANDS)}")
    finger = raw.get("finger")
    if finger not in FINGERS:
        raise ValueError(f"{where}: finger must be one of {', '.join(FINGERS)}")
    return Key(
        id=key_id,
        x=_number(raw, "x", where),
        y=_number(raw, "y", where),
        w=_number(raw, "w", where, 1.0),
        h=_number(raw, "h", where, 1.0),
        rotation=_number(raw, "rotation", where, 0.0),
        hand=hand,
        finger=finger,
    )


def _require_str(data, field: str, where: str) -> str:
    value = data.get(field) if isinstance(data, dict) else None
    if not isinstance(value, str) or not value:
        raise ValueError(f"{where}: '{field}' must be a non-empty string")
    return value


def _number(data, field: str, where: str, default: float | None = None) -> float:
    if not isinstance(data, dict):
        raise ValueError(f"{where} must be an object")
    value = data.get(field, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{where}: '{field}' must be a number")
    return float(value)
