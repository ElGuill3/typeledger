# TypeLedger — Polish: icon, daily reminder, review follow-ups

Objective: close the remaining items after the four planned phases. Branch: `feat/polish` (stacked on `feat/panel-extension`). Delivery: `ask-on-risk`. Test runner: `/usr/bin/python3 -m unittest discover -s tests -t .` (system Python; also runs GJS tests).

## Specs

- **S1 App icon.** Original design's pending item ("ícono"). Assumption: a full-color scalable SVG `io.github.elguill3.TypeLedger.svg` (split keyboard motif, GNOME HIG style) and a symbolic `io.github.elguill3.TypeLedger-symbolic.svg`, installed to `share/icons/hicolor/{scalable,symbolic}/apps/`; the desktop file and About dialog already reference the app id.
- **S2 Daily reminder.** Phase 1 accepted design: "recordatorio diario". Assumption: the extension shows ONE notification per local day at or after 20:00 if today has no practice; title "Keep your streak going", body mentions the current streak; action "Practice now" opens the app. No notification if practiced today, no repeat the same day (also across extension disable/enable within the day). No settings UI in this phase (the hour is a constant).
- **S3 Review follow-ups.** Non-blocking findings from native reviews: R3-indent-wpm-unpinned (engine auto-indent effect on WPM not pinned by a test), R3-partial-token-counter (practice page word counter counts a half-typed token), R3-vacuous-snippet-checks (snippet test asserts nothing real), R3-probe-silent-skip (headless shell test can skip silently), R3-squeeze-not-asserted (squeezed-panel case not asserted), R3-js-error-global (JS error check too broad).
- **S4 Flatpak build.** Pending: needs `flatpak-builder`, not installed; installing it requires the user's approval.
- User constraint (L1): cannot log out/in now; extension changes are verified in an isolated headless shell only.

## Tasks

- T1 [S1] App icon + meson install + test — delegated (writer A) — pending
- T2 [S2] Daily reminder in the extension + GJS tests + es strings — delegated (writer B) — pending
- T3 [S3] Review follow-up fixes — delegated (writer C) — pending
- T4 [S4] Flatpak build verification — blocked (waits for the user's approval to install flatpak-builder)

## Log

- L1 (2026-10-25, user): "podes seguir con lo que falte? yo digo que si funciona, lo que pasa es que por ciertas razones no puedo estar cerrando e inicnado sesion"
- L2 Assumptions S1-S2 stated to the user before starting.
