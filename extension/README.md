# TypeLedger Streak (GNOME Shell extension)

Shows your TypeLedger practice streak in the top bar (`🔥 N`, dimmed until you
practice today) with a menu holding the current and longest streak, today's
status, the last 7 days' average WPM and accuracy, and an "Open TypeLedger"
action.

- UUID: `typeledger@elguill3.github.io`
- Supports GNOME Shell 50.
- Reads only the `summary.json` file the app exports, never the SQLite history:
  `~/.local/share/typeledger/summary.json` (or `$XDG_DATA_HOME`) and, for the
  Flatpak build, `~/.var/app/io.github.elguill3.TypeLedger/data/typeledger/summary.json`.
  When both exist the one with the newest `generated_at` wins. Without a valid
  file the indicator shows `🔥 0` and "No practice yet".

## Build

From the repository root:

```sh
mkdir -p _build/extension  # pack crashes if the output directory is missing
gnome-extensions pack extension/typeledger@elguill3.github.io \
    --podir=../po --extra-source=streak.js --force -o _build/extension
```

This creates `_build/extension/typeledger@elguill3.github.io.shell-extension.zip`
with the Spanish translation compiled in.

## Install and enable

```sh
gnome-extensions install --force _build/extension/typeledger@elguill3.github.io.shell-extension.zip
```

On Wayland, log out and back in so GNOME Shell picks up the new extension
(on X11 you can restart the shell with Alt+F2, `r`). Then:

```sh
gnome-extensions enable typeledger@elguill3.github.io
```

## Logs

```sh
journalctl -f -o cat /usr/bin/gnome-shell
```

## Tests

The pure streak logic runs under plain GJS:

```sh
gjs -m extension/tests/test_streak.js
```

The Python suite (`/usr/bin/python3 -m unittest discover -s tests -t .`) also
runs it, validates `metadata.json`, the Spanish catalog and the packed zip.

## Translations

Strings are listed from the files in `po/POTFILES`. To refresh the template
after changing strings:

```sh
cd extension
xgettext --from-code=UTF-8 --language=JavaScript --keyword=_ --keyword=ngettext:1,2 \
    --package-name=typeledger-extension --add-comments -f po/POTFILES -o po/typeledger-extension.pot
msgmerge --update po/es.po po/typeledger-extension.pot
```
