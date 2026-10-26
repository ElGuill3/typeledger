# TypeLedger — Phase 1: practice MVP

Objective: standalone GNOME app (GTK4 + libadwaita, Python/PyGObject, SQLite) to practice typing on a Corne keyboard, with the keyboard layout drawn under the practice text. Branch: `feat/practice-mvp`. Delivery: `ask-on-risk` (no remote yet; the oversized-delivery choice is asked before the first push/PR). Test runner: `/usr/bin/python3 -m unittest discover -s tests -t .` (system Python; it has PyGObject, Linuxbrew `python3` does not).

## Specs

- **S1 Stack.** Standalone GTK4 + libadwaita app in Python/PyGObject, data in SQLite (user choice: "Python + PyGObject + SQLite"). A GNOME Shell panel extension is deferred to a later phase. App ID `io.github.elguill3.TypeLedger` (assumption, from git user `ElGuill3`). Build with Meson; Flatpak manifest against `org.gnome.Platform`.
- **S2 Practice screen.** User: "solo el texto/frases para practicar y debajo el layot del teclado para ver lo que se esta pulsando". The text is on top, current char marked, errors marked; the keyboard below highlights the pressed key and hints the next expected key (accepted proposal).
- **S3 Keyboard models.** User: "es justo este layout" (Corne with number row: 4 rows × 6 columns per half) and "si, 3 por lado" (3 thumb keys per half) → 54 keys; the encoder is drawn as decoration only. Also ship the classic Corne 3x6+3 (42 keys). Default labels follow a QMK default-style keymap and live in an editable JSON file per model. User: "no, mejor no lo hagamos asi, porque seria tedioso para gente que solo tenga qmk" → no HID/VIA/Vial detection. User: "no quiero un modo aprendizaje por ahora" → no learn mode.
- **S4 Practice options.** User: "configuraciones de idioma, tiempo, longitud del texto". Text language `en`/`es`; time mode 15/30/60/120 s; words mode 10/25/50/100 words (accepted proposal).
- **S5 Metrics.** WPM = correct chars / 5 per minute; raw WPM = all typed chars / 5 per minute; accuracy = correct keystrokes / total keystrokes (corrected errors still count); per-character hits/misses.
- **S6 Persistence.** Every completed session is stored in SQLite (`sessions`, `key_stats`) at `<GLib user data dir>/typeledger/typeledger.db`. Streaks and charts are derived from these tables later, never stored separately.
- **S7 i18n.** UI strings in English through gettext; Spanish translation included from the start.
- **S8 Capture.** Keys are captured with `Gtk.EventControllerKey` only while the window has focus; no global capture, no extra permissions.
- **Out of scope for phase 1** (user asked for them, later phases): "posibilidad de practicar lenguajes de programacion" (phase 3), "los graficos de seguimiento, racha y todo eso" (phase 2), panel extension (phase 4).

### Shared contracts (parallel units rely on these)

- `typeledger/core/models.py` (T1) owns `CharStat` and `SessionResult`; engine produces it, storage persists it. Do not redefine them.
- Pure logic lives in `typeledger/core/` and imports no GTK; widgets live in `typeledger/ui/`.
- Package data lives under `typeledger/data/` and is read with `importlib.resources`.

## Tasks

- T1 [S1, S7] Scaffold: package, Adw application/window, models contract, Meson, Flatpak manifest, gettext setup — inline — done (8a1e428; unittest 2 OK, meson setup+install to DESTDIR OK, app launch smoke OK; RDD assess unavailable: root commit has no base)
- T2 [S3, S2] Layout model + Corne 4x6/3x6 definitions + keyboard drawing widget — delegated (writer A) — done (5c8181e; RED ModuleNotFoundError → GREEN 23 tests OK; parent rendered both layouts to PNG and checked them visually)
- T3 [S4, S5] Typing engine + text generator + en/es word lists — delegated (writer B) — done (dd35f8f; RED ModuleNotFoundError → GREEN 17 engine/textgen tests OK; meson install verified)
- T4 [S6] SQLite storage with schema versioning — delegated (writer C) — done (53e1342; RED ImportError → GREEN 20 storage tests OK)
- T5 [S2, S4, S8] Practice page: options bar, text view, keyboard, live stats, results, save session — inline — done (59413ef; RED→GREEN: text_display/keys 9+2, practice controller 12, window 1; page tests 6 written after the page, so they are regression tests rather than RED; full suite 94 OK; meson install OK; parent screenshot of the live window checked)
- T6 [S7, S1] Spanish translation + Meson build verification — delegated (context backstop) — done (43ba78f; RED 6 failures → GREEN 6 OK; msgfmt 27 translated; meson install puts es .mo + desktop Name[es]; installed catalog returns "Practicar de nuevo"; desktop-file-validate OK; Flatpak build NOT verified: flatpak-builder not installed)

## Log

- L1 (2026-10-25, user, original request): "Hola, quiero comenzar con la creacion de una extension para gnome para personas que esten comenzando o quieran practicar con su teclado corne, ya que justamente yo estoy comenzando con un teclado corne 4x6, la idea es que ademas del entrenamiento en si, tener un seguimiento del progreso, con rachas de dias y graficos de progreso, tomando como base esto, que diseno me recomiendas?"
- L2 (user): "qmk, el keymap no se como importarlo, no podriamos hacer que se detecte automaticamente de algun modo? aunque sea primero con qmk, luego veremos si agregamos otros"
- L3 (user): "no, mejor no lo hagamos asi, porque seria tedioso para gente que solo tenga qmk, ademas, no quiero un modo aprendizaje por ahora, solo el texto/frases para practicar y debajo el layot del teclado para ver lo que se esta pulsando, configuraciones de idioma, tiempo, longitud del texto, e incluso posibilidad de practicar lenguajes de programacion, ademas de eso, los graficos de seguimiento, racha y todo eso"
- L4 (user, with product photo): "es justo este layout" — then "si, 3 por lado" — then "si, vamos a darle" (phase 1 authorized).
- L5 (user choice): "Python + PyGObject + SQLite". Reason: GJS has no SQLite binding without bundling libgda/gom (none installed, not in the GNOME runtime); Python ships `sqlite3` and `unittest`.
- L6 Environment: GTK 4.22, libadwaita 1.9, system Python 3.14 with PyGObject, SQLite 3.51; `meson` and `flatpak-builder` not installed (`uvx meson` available); GNOME Platform 50/51 runtimes installed.
- L7 T1 done. Meson verified with `uvx meson` (launcher shebang then points to uv's python; with system meson it is /usr/bin/python3). `po/LINGUAS` left empty until T6 adds `es.po`. T2/T3/T4 launched as parallel background writers with disjoint surfaces; parent owns `typeledger/meson.build` and `po/POTFILES.in` updates.
- L8 Note for T5: accented Spanish input (á, ñ) arrives through input-method composition, so the practice page must attach a `Gtk.IMMulticontext` to the key controller and consume its `commit` text, not raw keyvals.
- L9 T3/T4 accepted after parent spot check. T3 notes for T5: the engine does not auto-finish time mode (UI calls `finish()` when `is_time_up()`) and the UI must `extend()` the text before the cursor reaches the end. T4 added a `started_at_utc` sort column and requires `mode_value > 0`. RDD assess for dd35f8f/53e1342 unavailable while T2's untracked files are in the tree ("untracked files require an explicit declaration"); assess the range 8a1e428..HEAD after T2 is committed.
- L10 T2 accepted. RDD assess 8a1e428..5c8181e (T3, T4, T2): tier medium, reviewDue false (under_budget) → deferred to slice; no native review started. For T5: the keyboard view must switch to the layer needed by the next char (a key with label `MO(n)` in `keys_for_char` → layer n), otherwise a hinted key shows its layer-0 label.
- L11 T5 done. Design: pure `core/practice.py` controller (restart, text extension in time mode, tick, save once, layer hint) + thin `ui/practice_page.py`. Key capture: EventControllerKey in CAPTURE phase on the page with a `Gtk.IMMulticontext` (commit → typed text); specials (Backspace) via key-pressed; Ctrl shortcuts pass through. History DB failure → in-memory storage + toast. Options are not persisted between runs (not requested); default text language follows the locale. RDD assess 8a1e428..59413ef: medium, reviewDue false. T6 delegated (context backstop reached at ~150k tokens).
- L12 T6 done; parent removed a stray `messages.mo` that `msgfmt` wrote to the repo root. Phase 1 closed: full suite 100 tests OK. Pending outside this phase: Flatpak build (needs `flatpak-builder`), app icon, manual typing test by the user on the real Corne (IM composition of á/ñ is only covered by unit tests with direct commit calls). Next phase per plan: progress (streak, charts, error heatmap) from `sessions`/`key_stats`.
- L13 (user): "antes de continuar arma el repo en remoto y sube los cambios porfa" — choices: public repo; `main` = scaffold (8a1e428) + `feat/practice-mvp` pushed separately. Created https://github.com/ElGuill3/typeledger (public, default branch `main`); both branches pushed with upstream. No PR opened (phase 1 is ~3.6k lines: ask the oversized-delivery menu before opening one).
