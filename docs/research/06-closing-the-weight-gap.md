# 06 · Closing the weight gap

_Research note · 2026-11-27 · Live version:
[06-closing-the-weight-gap.html](06-closing-the-weight-gap.html)_

Every icon in research 03 and 05 now rebuilds exactly at the default style.
This note works on the next gap: matching a set's other weights without
hand fixes. Three steps: a dot primitive in the fitter, a strict weight test
on Phosphor, and a test of whether Google's anchor choice can be predicted.

## Answer

- **Dots are now a primitive.** A dot is a zero-length stroke with round caps,
  so it grows with the pen. All 540 rebuilds stay exact. Tabler icons with 90%+
  of ink in rules: 138 → 146 of 150. Research 03 medians: 93% → 95% (Material),
  96% → 97% (Carbon).
- **For a pen-style set, Variance already matches the real weights.** Rebuild
  only Phosphor regular, change only the pen, compare with Phosphor's own thin,
  light and bold. Thin and light land within 0.25 px on 95%+ of edges for
  98–100% of icons. That is as good as a perfect outline offset of the
  original, so the fitter adds no error.
- **What's left in Phosphor bold is Phosphor's own redraws.** 54% of icons pass
  (an ideal offset: 59%). The rest have parts moved or resized by hand, the same
  kinds research 04 found in Material.
- **Google's anchor choice is partly predictable.** A rule learned from half
  of Material, tested on the other half, matches 10–13 points more edge length
  than research 04's context rule at every master (wght 700: 53% → 64%).
  Icons fully matched at one master go up 2–6×.
- **It's about space, not keylines.** Nearly all of the gain comes from
  measuring the room in front of and behind each stroke exactly, instead of in
  buckets. Position in the icon and the 20 px live area add about 1 point.

## Dot primitive

A round component no wider than about two strokes is fitted as a dot: a
stroke of zero length with round caps. A dot drawn larger than the stroke
keeps the difference (`extra`), so it still follows the pen. Round holes of
the same size become knockout dots.

| Set | 90%+ rules before | after | Exact |
|---|---|---|---|
| Lucide (150) | 149 | 149 | 150 |
| Tabler (150) | 138 | 146 | 150 |
| Filled, five sets (200) | 186 | 187 | 200 |
| Research 03 (40) | 31 | 32 | 40 |

Biggest gains: Tabler `grip-vertical` 0% → 99.8%, `circle-dotted-letter-k`
51% → 99%, Fluent `dialpad_question_mark` 59% → 96%. No icon lost more than
4 points.

## Phosphor weight test

104 icons. Rebuild regular from its outline only, set the stroke to
Phosphor's thin, light or bold pen (8, 12, 24 on its 256 grid), and compare
with Phosphor's real file. "Ideal offset" grows or shrinks the original
regular outline evenly: the best any pen-only method can do.

| Weight | Variance: icons with 95%+ edges within 0.25 px | Ideal offset |
|---|---|---|
| Thin | 98% | 100% |
| Light | 100% | 100% |
| Bold | 54% | 59% |

- At the strict default-style test (nothing off by more than 1/20 px), few
  icons pass even for the ideal offset (thin 20 of 104). Phosphor's own weights
  aren't exact offsets at that scale, so 0.25 px is the fair bar here.
- Bold misses are designer changes: `folders` and `vibrate` move whole parts.
  Only 6 icons pass with the ideal offset and fail with Variance.

## Predicting Google's anchors

Research 04 measured all 172,000 Material edges at six masters. Here a
gradient-boosted tree learns each edge's move from what the source knows (its
context, space in front and behind, stroke thickness, facing, place in the
icon and the live area, part size). It is trained on half the icons and scored
on the other half, so it can't memorise an icon.

| Master | Edges matched: context rule | Learned | Icons fully matched: context rule | Learned |
|---|---|---|---|---|
| wght 100 | 52% | 64% | 1% | 6% |
| wght 700 | 53% | 64% | 2% | 13% |
| opsz 20 | 57% | 70% | 2% | 15% |
| opsz 48 | 77% | 85% | 14% | 33% |
| GRAD 200 | 60% | 71% | 5% | 18% |
| GRAD −50 | 74% | 87% | 12% | 52% |

"Matched" means moving within 0.25 px of Google's master. "Fully matched" =
95%+ of an icon's edge length matched at that master. These are rule-only
numbers. Research 04's resize and per-stroke anchor settings still come on
top.

What drives it (wght 700, edges matched):

| Inputs | Edges |
|---|---|
| Research 04 context buckets | 53% |
| The same quantities, measured exactly | 62.5% |
| + which way the edge faces | 62.5% |
| + distance to the icon's box and the live area | 63.9% |
| + part size | 64.0% |

Google's split depends smoothly on how much room is on each side of a
stroke. A designer-readable version of the rule is a curve, not a table.

## What this means for Variance

- **Ship the dot primitive.** It's the last common fitter gap on stroke sets.
- **For pen-style sets, weights are solved.** Changing the stroke width of the
  rebuilt source is as good as it gets. The rest is hand work the set's own
  designers did, which the override layer holds.
- **For anchored sets, replace the bucket table with a learned curve.** Use it
  as each stroke's default anchor. The per-stroke override stays for the rest
  and now covers fewer edges.
- **Keylines don't explain Google's choices.** Don't build a keyline rule.

## Next tests

- Put the learned anchor into the generator as a per-stroke default (a side
  offset of the centre-line), regenerate the 20 research 03 Material icons at
  wght 100 and 700, and score against Google.
- Turn the learned rule into a few curves a designer can read and edit.
- Learn Phosphor bold's per-part resizes the same way.

## Caveats

- The learned rule is checked on Material only; it is Material's style.
- Phosphor sample: 104 icons. Learned-rule split: by icon, seed 7.
- Code: `extract.py` (`dot_part`), `weights.py`, `anchor.py` in
  `prototype/rebuild/`. Results: `weights-phosphor.csv`, `anchor-material.json`.
