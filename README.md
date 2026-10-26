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

## Flatpak

```sh
flatpak-builder --user --install --force-clean _flatpak build-aux/flatpak/io.github.elguill3.TypeLedger.json
```
