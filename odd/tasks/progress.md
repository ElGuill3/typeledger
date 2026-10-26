# TypeLedger — Phase 2: progress tracking

Objective: a Progress view with day streaks, WPM/accuracy charts and a per-key error heatmap on the Corne, all derived from the SQLite history saved in phase 1. Branch: `feat/progress` (stacked on `feat/practice-mvp`). Delivery: `ask-on-risk` (ask the oversized-delivery menu before opening a PR). Test runner: `/usr/bin/python3 -m unittest discover -s tests -t .` (system Python).

## Specs

- **S1 Streaks.** User (L1): "tener un seguimiento del progreso, con rachas de dias y graficos de progreso". Accepted design: "Racha de días: un día cuenta si completaste al menos una sesión, usando la fecha local." Current streak = consecutive practiced days ending today, or ending yesterday when today has no session yet (still alive until the day ends). Also show the longest streak and whether today is done. Assumption: days come from the local date of `SessionResult.started_at`.
- **S2 Charts.** User (L3): "los graficos de seguimiento, racha y todo eso". Accepted design: "Gráficos de WPM y precisión en el tiempo, dibujados con Cairo." Assumption: one point per day (average WPM, average accuracy), range selector 7/30/90 days, days without sessions are gaps, not zeros.
- **S3 Error heatmap.** Accepted design: "Mapa de calor de errores sobre el Corne. Ahí ves qué dedos te cuestan." Per-character error rate (misses / (hits + misses)) over all history, painted on the key that types that character in the selected layout. Assumption: characters with fewer than 5 samples are ignored.
- **S4 Overview.** Assumption (supports S1/S2): totals shown above the charts: total sessions, total practice time, best WPM, average WPM and accuracy over the last 7 days. Empty history shows an empty state instead of charts.
- **S5 Navigation and freshness.** Practice and Progress are two views switched from the header bar; Progress reflects a session as soon as it is saved.
- **S6 i18n.** New UI strings go through gettext and get Spanish translations (phase 1 S7 rule; `tests/test_translations.py` enforces it).
- **Out of scope:** coding-language practice (phase 3), GNOME Shell panel extension (phase 4).

### Shared contracts (parallel units rely on these)

- Pure logic in `typeledger/core/` (no GTK); widgets in `typeledger/ui/`. Reuse `SessionResult`/`CharStat` (`core/models.py`), `Storage.list_sessions()` (`core/storage.py`), `KeyboardLayout.keys_for_char` (`core/layout.py`: ids ordered layer key, Shift, then the char key last).
- Parent owns `typeledger/meson.build`, `po/POTFILES.in`, `po/*.po*`, `typeledger/window.py`.

## Tasks

- T1 [S1, S2, S3, S4] `core/progress.py`: streak, daily summaries, char error rates, key heat, overview — delegated (writer A) — pending
- T2 [S2] `ui/chart_view.py`: cairo line chart with gaps and empty state — delegated (writer B) — pending
- T3 [S3] Heat levels in `ui/keyboard_view.py` — delegated (writer C) — pending
- T4 [S4, S5, S6] `ui/progress_page.py`, view switcher in the window, refresh after save, Spanish strings — delegated (after T1-T3) — pending

## Log

- L1 (2026-10-25, user): "si, continuemos" — phase 2 authorized after phase 1 (`odd/tasks/practice-mvp.md`).
- L2 Assumptions above were stated to the user before starting; context backstop already reached in the parent session, so every multi-step unit is delegated.
