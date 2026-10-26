# TypeLedger — Phase 3: code practice

Objective: practice typing real code (symbols, brackets, newlines) in the same practice view, with sessions saved and shown in Progress. Branch: `feat/code-practice` (stacked on `feat/progress`). Delivery: `ask-on-risk`. Test runner: `/usr/bin/python3 -m unittest discover -s tests -t .` (system Python).

## Specs

- **S1 Code sources.** User (phase 1 L3): "e incluso posibilidad de practicar lenguajes de programacion". Accepted design: "Modo código: snippets de Python, JS, Rust, etc. Hay que resolver bien la indentación y el Tab". Assumption: languages Python, JavaScript, Rust, Go, chosen in the same dropdown as the text language (English, Spanish, Python, JavaScript, Rust, Go).
- **S2 Snippets.** Assumption: bundled, original, short snippets (3-12 lines, ASCII, at least 12 per language), idiomatic and realistic; no copied third-party code.
- **S3 Newlines and indentation.** Assumption: Enter types the newline ("\n") and is required; after a newline the next line's leading indentation is filled automatically (no keystrokes, no stats); Tab is never needed. Newlines are visible in the practice text (e.g. a "⏎" marker) and lines break where the code breaks.
- **S4 Modes.** Assumption: time mode works as for prose (snippets appended as needed); words mode counts whitespace-separated tokens and always ends at a snippet boundary (at least N tokens).
- **S5 History.** Code sessions are saved with their language id (`python`, `javascript`, `rust`, `go`) and appear in Progress like any other session; the heatmap maps "\n" to the Enter key.
- **S6 Keyboard hints.** The next-key hint and pressed flash work for code characters, including "\n" → Enter.
- **S7 i18n.** New strings through gettext with Spanish translations (`tests/test_translations.py` enforces it).
- Keyboard disconnected during this phase: verification is automated (tests and rendered screenshots) only.

## Tasks

- T1 [S1-S7] Code practice end to end: language ids + validation, snippet data + generator, engine auto-indent, newline-aware wrapping/markup, Enter handling and hints, dropdown, heat for "\n", translations — delegated (context backstop) — pending

## Log

- L1 (2026-10-25, user): "si porfa, una cosa para que tengas en cuenta, desconecte el teclado, puedes seguir trabajando asi? sino nos esperamos" — push of `feat/progress` done; phase 3 started (user had confirmed "arrancamos la fase 3" path in the same reply).
- L2 Assumptions S1-S4 stated to the user before starting.
