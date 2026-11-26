# 04 · How Google corrects Material Symbols

_Research note · 2026-11-26 · Live version with figures:
[04-correction-fingerprints.html](04-correction-fingerprints.html)_

Every edge of all 4,004 Material Symbols (172,000 edges), measured between the
default style and six of Google's masters, then sorted by what kind of
correction Google made and what it would cost us to make it.

## Answer

- A fixed rule by context covers half to three quarters of all edges.
- A resize per icon or per part covers another 4–16%.
- A per-stroke anchor setting covers another 12–32%. It's the biggest lever.
- Under 4% of edges are reshaped at any master. That work is concentrated:
  159 icons have 10%+ of edges reshaped, 20 have 20%+.
- With rules + resize + anchor + a crowding rule, 63% of icons land within
  0.25 px on 95%+ of their edges at every master. Rules alone: 5 icons.
- Carbon's only redraws are 65 icons redrawn at 16 px (22 really changed,
  mostly parts shifted about 1 px onto the pixel grid). Material's rates do
  not predict them: the fingerprint kinds carry over, the rates don't.

## Base rule (px at 24 px; + = away from ink)

| Edge | wght 100 | wght 700 | opsz 20 | opsz 48 | GRAD 200 | GRAD −50 |
|---|---|---|---|---|---|---|
| Outside edge, ink behind | -1.32 | +0.86 | -0.40 | -0.03 | +0.82 | -0.48 |
| Lone stroke | -0.63 | +0.57 | -0.07 | -0.25 | +0.33 | -0.10 |
| Counter edge | +0.01 | +0.30 | +0.38 | -0.51 | -0.12 | +0.25 |
| Stroke end | -0.65 | +0.00 | -0.17 | -0.02 | +0.30 | -0.12 |
| Solid edge | +0.02 | +0.85 | -0.42 | +0.03 | +0.34 | -0.14 |

Weight moves the outside and keeps counters; optical size 48 keeps the
silhouette and thins inward; grade grows the outside first.

## Fingerprints (share of all edges)

| Kind | wght 100 | wght 700 | opsz 20 | opsz 48 | GRAD 200 | GRAD −50 |
|---|---|---|---|---|---|---|
| Rule | 51% | 52% | 57% | 77% | 59% | 74% |
| Resize | 11% | 13% | 16% | 4% | 16% | 13% |
| Anchor | 32% | 23% | 23% | 16% | 20% | 12% |
| Crowding | 3% | 9% | 2% | 2% | 3% | 1% |
| Reshape | 4% | 3% | 3% | 1% | 2% | 0% |

- **Rule**: standard move for the context.
- **Resize**: whole icon or whole part scales or slides.
- **Anchor**: standard width change, different side moves.
- **Crowding**: width changes less beside tight gaps (at wght 700, ~0.9 px
  instead of 1.15 px next to gaps under 2 px).
- **Reshape**: edge tilts or bends.

## How far each fix gets us (icons with 95%+ edges within 0.25 px at all six masters)

| With | Icons |
|---|---|
| Rules only | 5 |
| + resize | 31 |
| + anchor | 1,055 (26%) |
| + crowding | 2,531 (63%) |

## Redraw list

544 icons with 5%+ reshaped, 159 with 10%+, 20 with 20%+. Top 20:
chromecast_2, podiatry, conversation, brand_family, draw_abstract, bomb, interpreter_mode, music_note_2, mountain_steam, scatter_plot, sports, translate_indic, roundabout_left, roundabout_right, acupuncture, reminder, atr, productivity, tty, drawing_recognition.
Full ranking: `prototype/rebuild/material-ranking.csv`.

## Carbon

- 65 icons have a hand-drawn 16 px version; 22 differ from the 32 px drawing.
- Main move: a part shifted about 1 px onto the pixel grid (Material's resize
  fingerprint). Also re-proportioned arrowheads and redrawn small curves.
- Predicting hand work from shape with Material's rates: rank correlation
  0.57 inside Material (top-decile hit rate 41%), but slightly negative on
  Carbon's 16 px pairs. Each style needs its own masters to learn rates.

## What this means

1. Build the context rules in as the default recipe per axis.
2. Add a per-stroke anchor setting, defaulted from context.
3. Add per-icon and per-part resize (scale + shift) per master.
4. Add a crowding rule: less growth beside tight gaps.
5. Keep hand-drawn overrides for about 159 icons, spot fixes for about 544.

## Caveats

Single-axis instances only (corner masters mixed in). Tolerance 0.25 px.
Measurements of the shipped font, not Google's internal values.
Material Symbols © Google, Carbon © IBM, Apache 2.0.
