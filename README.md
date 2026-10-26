# TypeLedger

A GNOME app to practice typing on split ergonomic keyboards such as the Corne.
It shows the text to type with the keyboard layout drawn underneath, and keeps
a local history of your sessions.

## Run from source

```sh
/usr/bin/python3 -m typeledger
```

Requires GTK 4, libadwaita 1.x and PyGObject (the system Python on Fedora has them).

## Panel extension

A GNOME Shell extension shows your practice streak in the top bar and opens the
app. See [extension/README.md](extension/README.md) to build, install and enable it.

## Tests

```sh
/usr/bin/python3 -m unittest discover -s tests -t .
```

## Build with Meson

```sh
meson setup _build --prefix="$HOME/.local"
meson install -C _build
```

This also installs the app icon and its symbolic variant into `share/icons/hicolor`.

## Flatpak

Build into a local repository with [Flatpak Builder](https://flathub.org/apps/org.flatpak.Builder),
then install the app together with its translations:

```sh
flatpak run org.flatpak.Builder --user --force-clean \
    --state-dir=_build/flatpak/state --repo=_build/flatpak/repo \
    _build/flatpak/build build-aux/flatpak/io.github.elguill3.TypeLedger.json
flatpak install --user --reinstall "$PWD/_build/flatpak/repo" \
    io.github.elguill3.TypeLedger io.github.elguill3.TypeLedger.Locale
```

Use the native `flatpak-builder` command instead of `flatpak run org.flatpak.Builder`
if it is installed. Installing with `--install` alone skips the `.Locale` extension,
so translation changes would not reach the installed app.
