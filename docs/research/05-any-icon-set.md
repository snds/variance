# 05 · Any icon set: six more sets, same patterns?

_Research note · 2026-11-26 · Live version with figures:
[05-any-icon-set.html](05-any-icon-set.html)_

Can Variance take any icon set, rebuild it, and correct it toward a variable
font? Six more sets tested: Lucide and Tabler (drawn as strokes), Phosphor
(five weights), Fluent (six sizes, regular and filled), Heroicons (outline,
solid at three sizes) and Remix (line and fill).

## Answer

- **The fitter works on real stroke drawings.** Lucide and Tabler ship their
  true centre-lines, so they are an answer key. From the outline alone, the
  fitter got all 300 icons exact, with a median of 98% (Lucide) and 97%
  (Tabler) of ink in rules. Recovered centre-lines sit a median 0.02 px from
  the true ones.
- **The test found a real bug.** Whole circles came out as zero-length arcs.
  Fixed. Three research 03 icons improved by 22 to 57 points (now 93% median
  Material, 31 of 40 icons at 90%+).
- **Filled icons rebuild too.** All 200 filled icons from five sets came out
  exact as solids + knockouts, with a median of 98–99.6% in rules.
- **Every miss was the geometry engine, not the fitter.** The first run had 291
  of 300 and 188 of 200. All 21 misses were Skia booleans returning a wrong
  shape for the final fix-up patch. Trying the patch on slightly rounded copies
  and keeping the best fixed all 21, and research 03's last two (now 40/40).
- **The same five correction kinds show up in every set** (rule, resize,
  anchor, crowding, reshape). The amounts are each set's own style.
- **Weight has two house styles.** Phosphor's weights are the same centre-line
  with a wider or narrower pen: one rule explains 99.9% of thin and light, and
  85% of bold. Material splits the change by context (outside moves, counters
  stay). Material's rule explains only 12% of Phosphor thin.
- **FILL is the same recipe in all six sets.** Flood the counters; inner detail
  strokes turn into knockouts exactly one stroke wide; slash cuts carry
  through. That covers 48–88% of icons per set. The rest mostly leave a chosen
  counter open (10–24%).
- **Small sizes are redraws everywhere.** Heroicons 16 px: 26% of edges
  reshaped. Fluent 16 px: 10%. Carbon 16 px (research 04): same story.

## How it works

1. **One loader for any SVG** (`anyset.py`). Every shape is read with its own
   fill, stroke and fill rule. Strokes are outlined with their pen; helper
   shapes with no fill and no stroke are dropped. Everything lands on the
   960-unit grid.
2. **Edge moves from pixels** (`edgemove.py`, `pairs.py`). Research 04 followed
   points, which needs point-identical masters. Other sets don't have them, so
   this measures from images instead: for every edge pixel of style A, how far
   along its normal B's edge is. Same contexts, same five tiers.
3. **Checked against Material first.** On 300 Material icons, the pixel method
   gives the same rule as research 04's exact edges on the stroke contexts that
   cover most edges: within 0.05 px at weight (outside edge at wght 700:
   +0.88 px vs +0.86 px), within 0.15 px at size. Solids and stroke ends differ,
   because pixels can't tell them apart.
4. **FILL fingerprint** (`fillfp.py`): the filled style compared with "flood
   every counter of the outline".
5. **Answer-key test** (`gtruth.py`): outline Lucide/Tabler, rebuild, compare
   with the true centre-lines.

## Weight and size: which kinds repeat

Share of edge pixels in each kind (300 icons per pair). "Rule" uses the
pair's own context rule.

| Pair | Width change | Rule | Resize | Anchor | Crowding | Reshape |
|---|---|---|---|---|---|---|
| Material wght 100 | −1.30 px | 60% | 18% | 10% | 3% | 9% |
| Material wght 700 | +1.15 px | 57% | 25% | 7% | 4% | 7% |
| Material opsz 20 | −0.20 px | 61% | 26% | 7% | 1% | 5% |
| Material opsz 48 | −0.50 px | 80% | 11% | 4% | 1% | 4% |
| Phosphor thin | −0.75 px | 99.9% | 0.1% | 0% | 0% | 0% |
| Phosphor light | −0.40 px | 99.9% | 0.1% | 0% | 0% | 0% |
| Phosphor bold | +0.75 px | 85% | 9% | 4% | 2% | 1% |
| Fluent 16 vs 24 | 0 | 36% | 36% | 13% | 6% | 10% |
| Fluent 20 vs 24 | −0.30 px | 58% | 24% | 13% | 2% | 4% |
| Fluent 28 vs 24 | −0.20 px | 61% | 22% | 11% | 2% | 4% |
| Fluent 32 vs 24 | 0 | 57% | 27% | 9% | 3% | 5% |
| Fluent 48 vs 24 | −0.25 px | 78% | 16% | 4% | 1% | 2% |
| Heroicons solid 20 vs 24 | +0.29 px | 38% | 35% | 7% | 2% | 17% |
| Heroicons solid 16 vs 24 | +0.68 px | 31% | 34% | 7% | 3% | 26% |

Sizes are compared after scaling each to the same box. Width change is in
pixels at 24 px.

What each rule explains, on the same pixels:

| Pair | Even outline offset | Material's rule, rescaled | Pair's own rule |
|---|---|---|---|
| Phosphor thin | 99.9% | 12% | 99.9% |
| Phosphor bold | 85% | 78% | 85% |
| Fluent 20 | 48% | 45% | 58% |
| Fluent 28 | 38% | 39% | 61% |
| Heroicons 16 | 14% | 8% | 31% |

- **Phosphor = centred pen.** Every edge moves the same amount. Variance's
  simplest generator (same skeleton, new stroke width) reproduces it.
- **Material = anchored.** The context table is a style setting, not a law. It
  can be learned from one pair of masters per set.
- **Fluent keeps stroke weight per size.** 16 px and 24 px have the same stroke
  relative to the icon. Sizes move and resize parts to fit the pixel grid.
- **Heroicons' small sizes are redrawn**, like Carbon's.

Icons with 95%+ of edge pixels within 0.25 px, adding one fix at a time:

| Pair | Rule | + resize | + anchor | + crowding |
|---|---|---|---|---|
| Material wght 700 | 2% | 15% | 33% | 50% |
| Material opsz 48 | 18% | 44% | 63% | 68% |
| Phosphor thin / light | 100% | 100% | 100% | 100% |
| Phosphor bold | 53% | 70% | 81% | 93% |
| Fluent 20 | 2% | 16% | 55% | 71% |
| Fluent 48 | 37% | 65% | 87% | 90% |
| Fluent 16 | 3% | 16% | 36% | 48% |
| Heroicons 16 | 1% | 14% | 16% | 16% |

This is one master at a time. Research 04's 63% needs all six at once.

## FILL: what filled styles do

300 icons per set. Each icon is classed by what explains most of the
difference between its filled style and "flood every counter of the outline".

| Set | Flood | Knockout | Cut | Open counter | Bolder | Reshape |
|---|---|---|---|---|---|---|
| Material | 37% | 27% | 8% | 23% | 4% | 0% |
| Phosphor | 16% | 27% | 4% | 24% | 8% | 20% |
| Tabler | 32% | 56% | 1% | 10% | 1% | 0% |
| Remix | 20% | 46% | 5% | 16% | 7% | 5% |
| Heroicons | 37% | 37% | 5% | 20% | 1% | 0% |
| Fluent | 9% | 38% | 15% | 17% | 19% | 3% |

- **Flood**: filled = outline with counters filled. Under 3% difference.
- **Knockout**: an inner detail stroke became a gap through the fill. Median
  knockout width = the outline's stroke width (ratio 0.98–1.00 in all six
  sets). The detail stroke itself is cut out.
- **Cut**: a slash's gap carries on through the fill.
- **Open counter**: the fill left one counter empty (Phosphor's acorn keeps
  its body open; Material's shadow_minus keeps its front square open).
- **Bolder**: the filled style's strokes are heavier (Fluent most).
- **Reshape**: open shapes closed (a chevron becomes a triangle). Phosphor.

Flood + knockout + cut, which Variance can generate from the skeleton: Material
72%, Phosphor 48%, Tabler 88%, Remix 71%, Heroicons 79%, Fluent 62%.

## Rebuilding filled icons

40 filled icons per set, rebuilt as solids + knockouts (+ strokes where the
fitter finds them):

| Set | Exact | Median rule share | 90%+ rules |
|---|---|---|---|
| Heroicons solid | 40/40 | 99.4% | 39 |
| Remix fill | 40/40 | 99.4% | 38 |
| Phosphor fill | 40/40 | 99.6% | 39 |
| Tabler filled | 40/40 | 99.6% | 40 |
| Fluent filled | 40/40 | 98.4% | 30 |

## Closing the last misses

The first run left 9 stroke icons and 12 filled icons short of exact. In all
21, the fit was fine (for some, already exact before patching). The miss came
from the last step: Skia's boolean difference, used to build the fix-up patch,
returned a wrong shape where two outlines share nearly the same edge. The
patch then added or removed the wrong ink.

The patch step now tries, in order: exact booleans; booleans on copies rounded
to 1/16, 1/4 and 1 unit; and last, a patch traced from the pixel difference.
It keeps whichever scores best and never keeps a patch that makes the icon
worse. Of the 500 icons, 61 needed no patch, 426 closed with exact booleans
and 13 needed a rounded copy (1/16 unit in 11, coarser in 2). None needed the
traced fallback.
Research 03's two remaining misses, fingerprint-recognition and
logo--kubernetes, are exact now too (logo--kubernetes: 45% → 88% rules).

## Answer-key test (Lucide, Tabler)

| | Lucide | Tabler |
|---|---|---|
| Icons | 150 | 150 |
| Exact | 150 | 150 |
| Median rule share | 98.5% | 97% |
| 90%+ rules | 149 | 138 |
| True centre-line found (median) | 99% | 96% |
| Recovered line that is real (median) | 99% | 98% |
| Median distance from true line | 0.6 units (0.015 px) | 0.7 units (0.018 px) |

Within 0.25 px counts as found. Remaining misses: dots (a tiny round stroke
reads as a blob), dense arrowheads, and stroke count (the fitter splits at
junctions, so pieces rarely equal the file's sub-paths; the ink is the same).

## What this means for Variance

- **Import any set**: outline it (strokes with their own pen), fit the
  skeleton, and keep the fit as the source. That works on stroke-drawn and
  filled sets alike.
- **If the set has a second style, learn its rule from it.** One pair of
  masters gives the context table: centred (Phosphor), anchored (Material) or
  per-size layout (Fluent). If it has none, offer those as presets.
- **FILL needs one more source flag: `open`.** A counter that stays empty at
  FILL 1. The other parts of FILL are already in the format: flood counters,
  detail strokes become knockouts of the same width, cuts carry through.
- **This supports the FILL midpoint test.** Every set's FILL 1 is "counters
  close around inner details", research 01's third option. The ten-icon test
  should start there.
- **Plan hand work for small sizes.** 16 px is a redraw in Carbon, Heroicons
  and (partly) Fluent. Larger sizes and weights are mostly rules + resize +
  anchor.

## Caveats

- Pixel method: 1/20 px resolution, so it can't see moves under 2 units. Stroke
  ends and solids share one context, so their rules are mixed.
- Samples of 300 icons per pair (FILL and weight/size), 150 per answer-key set,
  40 per filled rebuild. Seeded, so reruns pick the same icons.
- "Anchor" here is judged from the stroke behind each edge pixel; research 04
  judged it from point pairs. Close, not identical.
- Icon files aren't committed. Licences: Lucide ISC; Tabler, Phosphor, Fluent,
  Heroicons MIT; Remix Apache-2.0.
