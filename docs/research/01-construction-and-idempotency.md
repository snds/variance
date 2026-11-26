# 01 · Building icons that can vary

_Research note · 2026-11-26 · Live version with the prototype font:
[01-construction-and-idempotency.html](01-construction-and-idempotency.html)_

How to construct icons so one source can become a variable font with Material
Symbols' four axes, and how to make every weight and size correction come out
the same every time it runs.

## Answer

Draw the skeleton, not the outline.

Store each icon as centre-lines plus a few rules: stroke alignment, caps,
joins, and which parts knock out. Generate every master from that one source
with a fixed recipe. Masters then match point-for-point by construction, and a
rebuild gives a byte-identical font. Exporting outlined art from Figma or
Illustrator can promise neither.

## What we're matching

From Google's [Material Symbols guide](https://developers.google.com/fonts/docs/material_symbols):

| Axis | Range | Default | What it does |
|---|---|---|---|
| `FILL` | 0 – 1 | 0 | Outline to solid. Meant for state changes. |
| `wght` | 100 – 700 | 400 | Stroke weight. Can change overall size a little. |
| `GRAD` | −50 – 200 | 0 | Finer thickness with almost no size change. About −25 for light icons on dark backgrounds, or to match a text face's grade. |
| `opsz` | 20 – 48 | 24 | Stroke thickness shifts with rendered size so icons look the same at 20 and 48 px. |

Google does not publish how the font was built, how many masters it has, or
which axis corners were drawn by hand. Some third-party pages list GRAD as
−25 to 200.

## The five things every master must share

1. Same number of contours, in the same order.
2. Same number of points in each contour.
3. Same point types (corner stays corner, handle stays handle).
4. Same start point on each contour.
5. Same direction on each contour.

Corollary: **never delete points to change a shape; collapse them.** At FILL 1
a ring's counter keeps its four points and shrinks them onto the centre.

## Why exported outlines break

General strokers add or drop points depending on width. Measured with Skia
(`prototype/skia_counts.py`):

| Shape | 0.67 px | 2 px | 3 px | Font needs |
|---|---|---|---|---|
| Check mark, round join | 12 | 14 | 14 | same in all |
| Ring | 52 | 52 | 52 | 16 |

The check loses two points at the thin weight, so it can't interpolate. The
ring matches but has over three times the points needed, with no promise they
line up across weights. Fixing that by hand per icon per master is the step
this project removes.

## Construction method

### Parts

| Part | Drawn as | Stroke rule | Why |
|---|---|---|---|
| Closed stroke | Closed centre-line | Grows inward | Silhouette holds as weight changes. |
| Open stroke | Open centre-line | Centred, butt caps, round joins | A round join is one curve at every width, so point count never changes. Miters jump at sharp angles. |
| Solid | Filled shape | Offset by a share of the stroke change | Dots still gain weight with the rest. |
| Knockout | Any of the above, tagged | Wound opposite to its container | See below. |

In Figma or Illustrator this is an ordinary un-outlined stroked drawing,
exported as SVG with strokes intact.

### Knockouts by direction

Fonts fill with the nonzero rule. A check wound opposite to its ring is ink
inside the empty counter at FILL 0 and a hole in the solid disc at FILL 1. No
point is added, removed or reversed.

### Corrections as recipes (prototype placeholders)

| Correction | Recipe |
|---|---|
| Weight | Width table: 100 → 0.67 px, 400 → 2 px, 700 → 3.33 px, linear between. |
| Optical size | Stroke × 1.10 at 20, × 1.00 at 24, × 0.85 at 48. |
| Grade | Stroke + (−0.2 px at −50, +0.67 px at 200). Silhouette fixed. |
| Fill | Counters collapse to centre; knockouts by direction. |
| Clearance | Inner details scale about their centre to keep their default share of free space as the ring thickens inward. Clamped 0.5× – 1.1×. |

## Idempotency

1. **Always start from the source.** No correction is applied to an earlier output.
2. **Topology from the source.** Start point, direction and order come from the part list, not from geometry.
3. **Round once, at the end.** Convert cubic curves to TrueType quadratics jointly across masters (`fontTools.cu2qu.curves_to_quadratic`) so every master gets the same number of pieces.
4. **Pin what isn't design.** `head.created` / `head.modified` come from `SOURCE_DATE_EPOCH`.

## Prototype results

| Test | Result | |
|---|---|---|
| Build twice, compare | Byte-identical (SHA-256 `be595f4d3c3b…`) | PASS |
| Points, types, start, direction over 8 masters | Match (`fontTools.varLib.interpolatable`) | PASS |
| Negative control: start point moved on one master | Caught, but reported as "underweight", not as a start-point error | PASS* |
| Contour order at FILL 1 | Flagged; zero-area collapsed counter confuses the heuristic. False alarm. | REVIEW |
| Heavy-weight crowding | Fixed by clearance correction | PASS |
| FILL 0.5 | Shrinking hole cuts across the check | OPEN |
| Axis corners | Up to 1.32 px drift at 24 px | OPEN |

\* The checker's start-point and order tests are best guesses. Because we own
topology, the pipeline should run its own exact check against the source and
treat fontTools' heuristic findings as review items.

### Corner drift (`prototype/corner.py`)

| Corner | Drift at 24 px |
|---|---|
| wght 700 · opsz 20 | 0.23 px |
| wght 100 · opsz 48 · GRAD −50 | 0.80 px |
| wght 700 · opsz 20 · GRAD 200 | 0.82 px |
| wght 700 · FILL 1 | 1.32 px |

A variable font adds one delta per axis. Non-linear corrections (clearance,
fill) don't add up exactly. Fix: measure drift at every corner and add a corner
master only where it passes a budget (for example 0.25 px). The recipe is
fixed, so the same corners are added every build.

## Proposed pipeline

1. **Ingest** any SVG. Shapes to paths, transforms applied (as Google's picosvg does for nanoemoji).
2. **Classify** paths: closed stroke, open stroke, solid, knockout. Tags from layer names, with guesses when missing.
3. **Lint construction**: outlined strokes, miter joins, crowded details. Explain fixes in design terms.
4. **Generate masters** from recipes.
5. **Compatibility gate**: exact checks fail the build; heuristic checks go to review.
6. **Corner pass**: add corner masters over the drift budget.
7. **Compile** with fontTools: PUA code points plus name ligatures.
8. **Proof**: proof sheet plus file hash.

## Open decisions

_All four were decided on 2026-11-26. See the [decision log](../decisions.md)._

1. **Source format.** Recommended: stroked skeleton SVG only for v1. Fitting skeletons to outlined art is much harder and lossy.
2. **Hand-drawn overrides.** Allow a hand-drawn master per icon per location (likely needed at opsz 20, where detail must go, not just thicken)?
3. **First axes.** Recommended: wght and FILL first, then opsz and GRAD.
4. **FILL midpoints.** Extra master at 0.5, a remapped FILL curve (`avar`), or counters that shrink around details. Test all three on ten real icons.

## Sources

- [Material Symbols guide](https://developers.google.com/fonts/docs/material_symbols)
- [fontTools varLib.interpolatable](https://fonttools.readthedocs.io/en/latest/_modules/fontTools/varLib/interpolatable.html)
- [nanoemoji / picosvg](https://github.com/googlefonts/nanoemoji)
- [fontTools discussion: importing SVG outlines](https://github.com/fonttools/fonttools/discussions/3090)

Prototype: fontTools 4.69.1, skia-pathops 0.9.2.
