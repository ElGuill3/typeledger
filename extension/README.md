# TypeLedger Streak (GNOME Shell extension)

Shows your TypeLedger practice streak in the top bar (`🔥 N`, dimmed until you
practice today) with a menu holding the current and longest streak, today's
status, the last 7 days' average WPM and accuracy, and an "Open TypeLedger"
action.

At 20:00 (local time), if you have not practiced today, it shows one "Keep
your streak going" notification with your current streak and a "Practice now"
button that opens the app. There is at most one reminder per day, also across
disabling and enabling the extension: the last reminded day is kept in
`~/.cache/typeledger-extension/state.json` (or `$XDG_CACHE_HOME`). The hour is
the `REMINDER_HOUR` constant in `reminder.js`; there are no settings yet.

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
    --podir=../po --extra-source=streak.js --extra-source=reminder.js \
    --force -o _build/extension
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

The pure streak and reminder logic runs under plain GJS:

```sh
gjs -m extension/tests/test_streak.js
gjs -m extension/tests/test_reminder.js
```

The Python suite (`/usr/bin/python3 -m unittest discover -s tests -t .`) also
runs it, validates `metadata.json`, the Spanish catalog and the packed zip.
When `gnome-shell` and `dbus-run-session` are available it also starts a
throwaway headless GNOME Shell (temporary HOME, XDG dirs, D-Bus session and
keyfile GSettings, so your session is never touched) with the test-only
`tests/panel-probe@typeledger.test` extension, which crowds the top bar and
checks that the label keeps its full `🔥 N` width.

## Translations

Strings are listed from the files in `po/POTFILES`. To refresh the template
after changing strings:

```sh
cd extension
xgettext --from-code=UTF-8 --language=JavaScript --keyword=_ --keyword=ngettext:1,2 \
    --package-name=typeledger-extension --add-comments -f po/POTFILES -o po/typeledger-extension.pot
msgmerge --update po/es.po po/typeledger-extension.pot
```
