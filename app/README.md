# Variance app

A local web app over the `variance` Python package (decision 2026-11-28: runs
locally, `variance serve`). Plain HTML, CSS and JS; no build step.

## Run

```sh
cd /absolute/path/to/variance && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/python -m variance new /absolute/path/to/my-set "My Icons" && .venv/bin/python -m variance import /absolute/path/to/my-set examples/lucide && .venv/bin/python -m variance serve /absolute/path/to/my-set
```

It opens http://127.0.0.1:8960/. Everything you change is written to the set
folder as plain SVG and JSON (see `variance/project.py`), so git can track it.

## What works (first slice)

| Stage | In the app |
|---|---|
| Import | Drop SVGs. Live strokes import exactly; filled art imports as solids. Import report with notes. Re-import merges. |
| Style | Pen or Anchored. Switching keeps manual settings. |
| Generate + gate | wght 100/400/700 × FILL 0/1 masters with fixed structure. Blocking: structure mismatch, cuts and knockouts (not built yet). Warnings: thin strokes, counters closing, tight gaps, rule unsure, details lost at FILL 1, low reference score, stale fixes. |
| Triage | Review queue ranked by risk, reason filters, J/K/A/F keys. |
| Fix | Side pins (intent, along wght or at one weight), exact amounts, end moves, reset, match sibling, fit to a drawing. |
| Proof | The exported font in the browser: set grid, sizes 16–48 px, light and dark grounds, next to text, wght scrub. |
| Export | Variable TTF with ligatures and PUA code points, six masters and a .designspace; SHA-256, "same as last build", changelog. |

## Not yet

Cuts and knockouts in the fixed-structure build (research 02), opsz and GRAD,
learned anchor rule as a style, Learn from my set, shared parts, collapse
below, batch fix, UFO export, cubic outlines (masters are line segments for now).
