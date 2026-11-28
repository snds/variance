# 09 · All six masters, and fitting to a drawing

_Research note · 2026-11-28 · Live version:
[09-all-masters-and-fit.html](09-all-masters-and-fit.html)_

Research 08 reached about 90% of Google's weight masters with Google's own
moves, and 64–76% with the learned rule alone. This note runs the remaining
passes: all six masters, a fit read straight off a drawing, angled stroke
ends, and two tries at a better rule. Same 20 hard Material icons, same
score (share of Google's edge pixels within 0.25 px of ours).

## Answer

- **The controls hold up on every axis.** Fed Google's own moves, the
  generator reaches 89–95% at all six masters (wght, GRAD and opsz, both
  ends of each).
- **Fitting to a drawing works without Google's data.** Reading the moves
  straight off a reference master, with no edge table, lands within 0–2
  points of that ceiling everywhere. This is the measuring engine for the
  editor's "fit to a drawing" tool, and it works for any reference.
- **The learned rule is the limit, and it varies by axis.** 85–88% at
  opsz 48 and GRAD −50, 70–76% at opsz 20, GRAD 200 and wght 100, 64% at
  wght 700. Heavier, denser masters are where Google's judgement varies most.
- **Angled ends don't close the end gap.** Stroke ends are still the largest
  miss (4.5–6.6% of edge pixels), but cutting them at an angle scores up to
  3 points lower on average than flat ends. The misses at ends are about
  junctions and end shape, not angle. That makes them a manual job for now.
- **The rule improved a little, then stopped.** Trained on research 08's
  corrected edge table, the learned rule's per-edge match on these 20 icons
  goes from 69% to 74% (wght 100). Adding how much ink surrounds each edge
  adds under 1 point.

## Results by master (20 icons, mean edges within 0.25 px)

| Master | Google's moves | Fit to Google's drawing | Fit, angled ends | Learned rule |
|---|---|---|---|---|
| wght 100 | 94% | 93% | 92% | 76% |
| wght 700 | 89% | 89% | 88% | 64% |
| opsz 20 | 91% | 90% | 89% | 70% |
| opsz 48 | 94% | 94% | 91% | 85% |
| GRAD 200 | 89% | 87% | 87% | 75% |
| GRAD −50 | 95% | 93% | 92% | 88% |

Icons at 90% or more, out of 20:

| Master | Google's moves | Fit | Learned |
|---|---|---|---|
| wght 100 | 18 | 14 | 4 |
| wght 700 | 10 | 10 | 0 |
| opsz 20 | 10 | 13 | 2 |
| opsz 48 | 15 | 18 | 6 |
| GRAD 200 | 10 | 8 | 3 |
| GRAD −50 | 17 | 16 | 10 |

Stroke widths used for the opsz and GRAD masters are measurements of
Google's files (the median width Google gives an 80-unit stroke): opsz 20
72, opsz 48 60, GRAD 200 106, GRAD −50 70. They are not Google's internal
values.

## Where the remaining miss sits (fit with angled ends)

Share of all of Google's edge pixels missed, by the nearest source part:

| Master | Stroke end | Stroke side | Dot | Patch | Knockout end |
|---|---|---|---|---|---|
| wght 100 | 4.5% | 0.8% | 0.9% | 0.5% | 0.9% |
| wght 700 | 6.2% | 2.4% | 1.4% | 0.9% | 1.0% |
| opsz 20 | 6.2% | 1.4% | 1.6% | 0.9% | 0.7% |
| opsz 48 | 5.7% | 1.2% | 0.3% | 1.2% | 0.7% |
| GRAD 200 | 6.6% | 3.4% | 1.3% | 0.7% | 1.0% |
| GRAD −50 | 4.9% | 1.4% | 0.6% | 1.2% | 0.5% |

## How the fit works

At each sample on our default outline (each stroke side, each stroke end
corner, each solid edge), walk along the outward direction through the
reference drawing and find the nearest place where its ink ends. That
distance is the move. The median per segment becomes the segment's
setting. An earlier version used the nearest edge in any direction; near
junctions it picked up the wrong part (`deselect` at wght 100: 80% against 97%).

## What this means for Variance

- **Ship fit-to-a-drawing as the core of the manual flow.** A designer who
  draws a master once gets about 90% of it as source settings immediately.
  The editor then only needs to show the last 5–10%.
- **Treat stroke ends as a designer control.** Neither a length change nor an
  angle captures them. Give the end handle a few shapes (flat, angled,
  follow the neighbour at a junction), and expect hand work there.
- **Use the learned rule per axis, and say how sure it is.** On opsz 48 and
  GRAD −50 it is close to the ceiling; on wght 700 it needs review. The
  review queue should weight icons by axis.
- **Stop tuning the rule's features.** The next gains come from designer
  fixes feeding back as training examples (the "learn from fixes" loop),
  not from more geometry inputs.

## Caveats

- The 69% → 74% per-edge figure counts any edge whose predicted move is
  within 0.25 px, so it isn't directly comparable to research 06's table,
  which counted only edges that moved parallel.
- Fit scores read moves from the very master they are scored against, so
  they measure how well the controls can express a drawing, not a
  prediction.
- Code: `segments.py` (`Ref`, `main9`, angled ends in `seg_moves`),
  `source.py` (angled ends in `side_stroke`), `density.py` in
  `prototype/rebuild/`. Results: `segments9-material20.json`.
