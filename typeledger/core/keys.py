"""Map GDK keyval names of non-printing keys to layout special key names."""

_SPECIAL_KEYS = {
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


def special_key_name(keyval_name: str | None) -> str | None:
    """Return the `KeyboardLayout.keys_for_special` name, or None for other keys."""
    if keyval_name is None:
        return None
    return _SPECIAL_KEYS.get(keyval_name)
