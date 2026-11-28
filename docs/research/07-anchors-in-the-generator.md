# 07 · Anchors in the generator

_Research note · 2026-11-27 · Live version with figure:
[07-anchors-in-the-generator.html](07-anchors-in-the-generator.html)_

Research 06 learned a rule for which side of a stroke Google moves when the
weight changes. This note builds it into the generator and regenerates the
20 hardest Material icons (from research 03) at wght 100 and 700.

## Answer

- **The learned rule works end to end.** On these 20 icons it matches more
  of Google's master than either earlier recipe, at both weights.
  - wght 100: 67% of Google's edges within 0.25 px, against 57% for research
    04's table and 53% for centred growth.
  - wght 700: 55%, against 47% and 31%.
- **It wins on most icons.** The learned rule beats the table on 15 of 20 icons
  at both weights, and beats centred growth on 16 of 20 (wght 100) and 20 of
  20 (wght 700).
- **One move per stroke side has a ceiling.** Even Google's own moves, reduced
  to one number per side, reach 77% (wght 100) and 61% (wght 700). Only 2 icons
  pass 95% that way. These are the hardest icons in the set. The rest needs
  finer control: an anchor per segment, per-part resize, and crowding.

## What changed in the generator

- **A stroke can move each side by its own amount.** At a master, a stroke's
  left side moves `kL` and its right side `kR`. The generator turns that into a
  new width (W + kL + kR) and a sideways shift of the centre-line
  ((kL − kR) / 2). The skeleton stays the source; the shift is computed per
  master from the rule, never stored as a second drawing.
- **Solids get one grow amount.** Every edge moves the same distance.
- **Corners stay sharp.** A shifted centre-line is offset segment by segment
  and the offset lines meet at their intersection (a mitre). An earlier,
  simpler version made long spikes at corners.
- **Booleans fall back harder.** When Skia can't combine two shapes, the
  generator retries on copies snapped to 1/16, 1/4 and 1 unit.

## Results (20 icons, Google's edge pixels within 0.25 px)

| How each side moves | wght 100 | wght 700 |
|---|---|---|
| Centred: every stroke gets Google's new width | 53% | 31% |
| Research 04 table | 57% | 47% |
| Learned rule (research 06) | 67% | 55% |
| Google's own moves, one number per side | 77% | 61% |

Median area that differs from Google, px² at 24 px:

| How each side moves | wght 100 | wght 700 |
|---|---|---|
| Centred | 96 | 98 |
| Table | 61 | 83 |
| Learned | 42 | 66 |
| Google's own, per side | 34 | 64 |

- **Biggest wins:** `shuffle_on` and `repeat_one_on` (filled squares with
  knocked-out arrows) go from 26–38% to 68–88%. The learned rule keeps the
  square's outside still and moves the arrows, which is what Google does.
- **Where it loses to the table:** `fingerprint_off` and `theater_comedy` at
  wght 100, and `padel` at wght 700. All three are long curved strokes where
  one move per side is too coarse.

## What this means for Variance

- **Use the learned rule as each stroke's default anchor.** It is the best
  automatic recipe so far.
- **Next lever: anchors per segment, not per stroke.** The fitter chains long
  strokes, so one stroke can hold several segments that Google treats
  differently. Splitting the anchor per segment raises the ceiling.
- **Then add per-part resize and crowding** from research 04 to the same
  generator, and score all six masters.

## Caveats

- Research 08 found two measuring bugs behind these numbers (the edge search
  and flipped edge normals). Corrected and finer results are in
  [research 08](08-toward-100.md).
- The learned rule was trained on all Material icons except these 20.
- The score covers edges only (within 0.25 px). It doesn't check that the
  masters stay point-compatible; that is a separate step.
- Code: `source.py` (`offset_d`, `grow`, boolean fallbacks), `learned.py`.
  Results: `prototype/rebuild/learned-material20.json`.
