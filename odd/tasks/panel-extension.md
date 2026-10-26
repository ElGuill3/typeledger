# TypeLedger — Phase 4: GNOME Shell panel extension

Objective: a GNOME Shell extension that shows the practice streak in the top bar and opens the app, fed by a small JSON summary the app exports. Branch: `feat/panel-extension` (stacked on `feat/code-practice`). Delivery: `ask-on-risk`. Test runner: `/usr/bin/python3 -m unittest discover -s tests -t .` (system Python; it also runs the GJS tests through `gjs -m`).

## Specs

- **S1 Panel streak.** User (phase 1, accepted design): "Indicador en el panel de GNOME (extensión)" / "La extensión del panel ... Muestra la racha 🔥, recordatorio diario, botón para abrir la app" — reminder deferred (assumption: no notifications in this phase). Top bar shows `🔥 N`; dimmed when today has no practice yet.
- **S2 Menu.** Assumption: current streak, longest streak, today done / not yet, last-7-days average WPM and accuracy, "Open TypeLedger".
- **S3 Data contract.** Accepted design: the extension never reads SQLite; the app writes `<user data dir>/typeledger/summary.json` atomically after every saved session and at startup. Schema v1: `{"schema": 1, "generated_at": ISO-8601, "practiced_days": ["YYYY-MM-DD", ...] (sorted, unique, last 400 days at most), "longest_streak": int, "total_sessions": int, "recent_days": 7, "recent_avg_wpm": float, "recent_avg_accuracy": float (0..1), "recent_sessions": int}`.
- **S4 Freshness.** The extension computes the current streak itself from `practiced_days` and today's local date (same rule as phase 2 S1: alive until the day ends), reloads when the file changes and re-evaluates after midnight. It looks for the file in `GLib.get_user_data_dir()/typeledger/summary.json` and in `~/.var/app/io.github.elguill3.TypeLedger/data/typeledger/summary.json` (Flatpak), newest wins. Missing or invalid file → `🔥 0` and a "No practice yet" menu line, never an exception.
- **S5 Compatibility.** ESM extension for GNOME Shell 50 (the only version available to test); UUID `typeledger@elguill3.github.io`.
- **S6 i18n.** Extension strings through the extension's gettext with Spanish translations.

## Tasks

- T1 [S3] App: `core/summary.py` builds and atomically writes `summary.json`; written at startup and after each saved session — delegated (writer A) — done (RED ModuleNotFoundError/ImportError → GREEN 24 tests; suite minus in-progress test_extension 213 OK incl. -W error::ResourceWarning)
- T2 [S1, S2, S4, S5, S6] Extension: `extension/typeledger@elguill3.github.io/` (metadata, extension.js, pure streak/summary logic module, stylesheet, es translation), GJS tests run from the Python suite, pack check, README install steps — delegated (writer B) — done (035b87a; RED ImportError/6 errors → GREEN 18 GJS + 11 Python tests; suite 224 OK incl. -W error::ResourceWarning; pack OK; isolated headless gnome-shell 50.5: ACTIVE, 3 disable/enable cycles clean, no JS errors; rendered label/menu and app launch not verified)

## Log

- L1 (2026-10-25, user): "si porfa, sube los cambios, y haz el cambio, luego avanza con la fase 4" — pushed feat/code-practice, previous-line context fix 4c177bd pushed, phase 4 started.
- L2 Assumptions S1-S5 stated to the user before starting. Installing/enabling the extension in the user's session writes outside the project (~/.local/share/gnome-shell/extensions) and needs the user's go-ahead.
- L3 T1 accepted: 400 cap = 400 most recent practiced days; future days excluded; export only after a saved session with keystrokes; in-memory fallback never exports.
- L4 T2 accepted after parent review of disable/destroy cleanup. Deviations: GioUnix.DesktopAppInfo (Gio one deprecated); dim = fixed grey (#8a8a8f) since St CSS has no opacity; date check re-armed hourly; menu open refreshes. RDD assess 4c177bd..035b87a: medium, reviewDue false. Daily reminder from the original design deferred. Not installed in the user's session (needs approval); branch not pushed.
- L5 (user): "si, sube los cambios e instala la extension" — pushed feat/panel-extension; packed to _build/extension, installed with `gnome-extensions install --force` into ~/.local/share/gnome-shell/extensions/typeledger@elguill3.github.io; `gnome-extensions enable` failed (shell not rescanned on Wayland), so the UUID was appended to org.gnome.shell enabled-extensions (existing 15 entries kept). Loads after the user logs out/in. ~/.local/share/typeledger/ has typeledger.db but no summary.json yet: it appears after the app (this branch) starts once.
- L6 (user, after login): "asi se ve con la extension" (menu data correct) then, asked whether the bar shows 🔥 1: "la marca solo". Reproduced in an isolated headless gnome-shell 50.5 with the user's extensions at 1024 px: St.Label ellipsizes by default (min width 1 px), the crowded right box shrank the button to its padding. Fix bb293d3: `clutter_text.ellipsize = Pango.EllipsizeMode.NONE` (Vitals does the same); RED 3 failures → GREEN; headless regression test (skips without gnome-shell); suite 226 OK incl. -W error::ResourceWarning. Reinstalled with `gnome-extensions install --force`; needs logout/login. Not pushed.
