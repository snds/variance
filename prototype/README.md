# Prototype

A small proof that skeleton-sourced icons give compatible masters and
reproducible builds. Two icons (`check_circle` at U+E000, `radio_button` at
U+E001), four axes, eight masters.

Stroke widths and correction tables here are **placeholders**, not Material's values.

## Run

```sh
cd /absolute/path/to/variance/prototype && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/python gen.py
```

| Script | What it shows |
|---|---|
| `gen.py` | Builds `build/proto.ttf` and its masters. Run it twice: the printed SHA-256 matches. |
| `skia_counts.py` | A general stroker (Skia) changes point count with stroke width. This is why exported outlines can't be masters. |
| `corner.py` | How far axis corners drift from the recipe when only single-axis masters exist. Run `gen.py` first. |
| `neg_control.py` | Moves one start point on one master and builds into `build/neg/`. Check it with `python -m fontTools.varLib.interpolatable build/neg/master*.ttf`. |

Check compatibility of the main build:

```sh
.venv/bin/python -m fontTools.varLib.interpolatable build/master*.ttf
```

Expect one known false alarm: "contour order differs" at FILL 1, because the
collapsed counter has zero area. Order is fixed by construction.
