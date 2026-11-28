# 08 · Toward 100%

_Research note · 2026-11-28 · Live version with figure:
[08-toward-100.html](08-toward-100.html)_

Research 07 put one anchor per stroke into the generator. This note makes the
generator's controls finer, fixes two measuring bugs that held research 06
and 07 back, and asks what is left for a designer to fix by hand. Same test:
research 03's 20 hardest Material icons at wght 100 and 700, scored as the
share of Google's edge pixels within 0.25 px of ours.

## Answer

- **With finer controls, the generator can reach about 90% of Google's
  edges.** Fed Google's own moves, it now matches 94% at wght 100 and 89% at
  wght 700 (research 07: 77% and 61%). 18 of 20 icons pass 90% at wght 100,
  and 10 of 20 at wght 700.
- **The automatic rule improves too, but it's still the bottleneck.** The
  learned rule alone now matches 76% at wght 100 and 64% at wght 700
  (research 07: 67% and 55%). It beats research 07 on 16 of 20 icons at
  wght 100 and 14 of 20 at wght 700.
- **Two bugs were hiding about a third of the gain.**
  - The edge search found a long straight edge only near its middle.
  - On 13% of Material's edges, the measured "outward" direction pointed into
    the ink. Material's overlapping contours don't all run the same way, so
    a grow read as a shrink there.
- **What's left is mostly stroke ends, plus moves no rule predicts.** With
  Google's own moves, stroke ends hold the largest remaining miss (3–5% of
  all edge pixels), then stroke sides on curves (1–3%). The 13–25 point gap
  between the learned rule and Google's own moves is designer judgement.
  That gap is the job for the editor.

## What changed in the generator

- **Each segment of a stroke moves its own sides.** A fitted stroke often
  chains several segments that Google treats differently. Each segment now
  has its own left and right distance from the centre-line. A side may even
  cross the centre-line, as long as the stroke stays positive width. With
  equal moves everywhere, this is the same as an ordinary stroke (checked
  pixel for pixel).
- **Stroke ends move.** Butt and square ends can get longer or shorter at
  each master. Round ends follow the width.
- **Solids and detail patches move edge by edge.** Each outline segment of a
  filled part moves by its own amount. A badge can now shift or shrink, which
  one grow amount couldn't do.
- **Patches keep only what they change.** A detail patch is trimmed to what
  it adds or removes at the default. That leaves the default rebuild exact,
  and the hidden overlap no longer pins ink in place at other weights. Thin
  slivers stay put; only thick, well-measured pieces move.
- **Corners are mitred only at real corners** (over 10°). A smooth join that
  changes offset is bridged straight, so no spikes.

## Results (20 icons, Google's edge pixels within 0.25 px)

Fed Google's own moves (the most each set of controls can do):

| Controls | wght 100 | Icons 90%+ | wght 700 | Icons 90%+ |
|---|---|---|---|---|
| Research 07: one move per stroke side | 77% | 3 | 61% | 1 |
| Same, with both bugs fixed | 85% | 10 | 73% | 2 |
| + a move per segment side | 89% | 14 | 81% | 5 |
| + stroke-end moves | 90% | 15 | 83% | 7 |
| + edge moves for solids and patches | 94% | 18 | 89% | 10 |

Fed the learned rule (trained on all Material icons except these 20):

| Controls | wght 100 | wght 700 |
|---|---|---|
| Research 07, as published | 67% | 55% |
| All of research 08's controls | 76% | 64% |

- **Biggest wins with Google's own moves:** `keyboard_lock` 51% → 97%
  (wght 100: the lock badge shifts, and the keys are a detail patch that now
  shrinks), `deselect` 22% → 89% (wght 700: the dashed squares), `padel`
  47% → 91% (wght 700).
- **Where the learned rule loses ground:** `shuffle_on` and `repeat_one_on`,
  the filled squares with knocked-out arrows (`shuffle_on` 88% → 51% at wght 100). With
  Google's own moves these reach 95–98%, so the controls are right and the
  rule's guess for knockouts inside a filled shape is wrong. Next fix:
  train on knockouts separately.

### Where the remaining miss sits (Google's own moves)

Share of all of Google's edge pixels we still miss, by the part nearest the
miss:

| Part | wght 100 | wght 700 |
|---|---|---|
| Stroke end | 3.0% | 4.7% |
| Stroke side | 0.9% | 2.8% |
| Knockout stroke end | 0.7% | 0.9% |
| Dot | 0.7% | 1.3% |
| Patch | 0.5% | 1.5% |
| Solid | 0.2% | 0.0% |

Ends are where Google redraws most: tapered or angled cuts, ends that shift
along the stroke, and ends at a junction that change shape. A single length
change can't express those.

## What can't be automated

Three kinds of change come from a designer's eye, not a rule:

1. **Anchor choices the rule gets wrong.** Which side holds still on a
   particular stroke. This is the 13–25 point gap above. The controls exist;
   only the choice is missing.
2. **End and junction shapes.** Angled or tapered ends, and how two strokes
   meet when one gets heavier.
3. **Real redraws.** A part moved for balance, a shape simplified at a light
   weight, a detail dropped when space runs out. Research 04 found these in
   under 4% of edges, but they are concentrated in a few icons.

## Tooling for the manual part

The principle: **every manual fix is stored as a parameter on the source,
never as a second drawing.** The source stays the only truth, so a fix
survives when the skeleton changes, and it can teach the rule.

| Tool | What the designer does | What is stored |
|---|---|---|
| **Side pins** | Click a stroke segment's side at a master to hold it still or let it move. Drag to set an exact amount. | A per-segment side move (research 08's `sides`). |
| **End handles** | Drag a stroke end along the stroke at a master; pick an end shape (flat, angled, tapered). | An end move, later an end angle. |
| **Part nudge** | Move or scale a part (a badge, a dot) at one master. | A transform on the part, per master. |
| **Fit to a drawing** | Draw or import one master by hand, once. Variance fits its own controls to it, as this note did with Google's master. | The fitted moves, so the drawing becomes parametric. |
| **Point override** | Last resort: move outline points at one master. | Per-point deltas, flagged stale if the skeleton changes (the decision in research 01). |

Around those, three support features keep the work small:

- **Diff overlay and score.** Show the master over a reference (blue and red,
  as in this note's figure), with the share of edges within 0.25 px. Click a
  miss to jump to the control that owns it.
- **Review queue.** Rank icons by risk: where the rule is unsure, or where
  the generated master breaks a check (a counter closing, two parts closer
  than a gap, a stroke thinner than the minimum). Designers see the worst
  icons first instead of checking all of them.
- **Learn from fixes.** Each pin, end move or nudge is a labelled example.
  Retrain the set's rule on them, so the next icon needs fewer fixes. For a
  new set this is the whole loop: fix 20 icons, retrain, review the rest.

"Fit to a drawing" is the strongest of these, and it already works: this
note's "Google's own moves" results are exactly that fit. With a reference
master, 18 of 20 of the hardest icons get to 90%+ with no hand edits at
wght 100.

## Next tests

- Train the anchor rule on the corrected edge table and with knockouts as
  their own case; check `shuffle_on` and `repeat_one_on` recover.
- End shapes: add an end angle, and score again by part.
- Score all six masters, not just wght 100 and 700.
- Prototype the side pins and diff overlay in a small editor page.

## Caveats

- Retraining research 06's held-out test on the corrected table moved
  wght 100 from 64% to 65% of edges matched; the other masters weren't
  re-run.
- Scores cover edges only. Point compatibility across masters is a
  separate step.
- Code: `source.py` (`side_stroke`, `solid_edges`, `offset_pts`),
  `segments.py`, `orient.py` in `prototype/rebuild/`. Results:
  `segments-material20.json`.
