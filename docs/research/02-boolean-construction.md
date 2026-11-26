# 02 · Boolean shapes from skeletons

_Research note · 2026-11-26 · Visual proof tables:
[02-boolean-construction.html](02-boolean-construction.html) · Code:
[`prototype/booleans.py`](../../prototype/booleans.py), [`prototype/booleans_proof.py`](../../prototype/booleans_proof.py)_

Follows [01](01-construction-and-idempotency.md). Sean's ask: test several
ways to build complex icons that need boolean operations, using stroke
skeletons, without losing the design intent.

## Answer

Don't run booleans on outlines. Turn each boolean into a rule on the skeleton.

- **Merge:** leave parts overlapping; the nonzero fill merges them. Exact.
- **Clip:** one part's edge follows another part's generated edge. Exact.
- **Cut-out with a gap** (an "off" slash, a badge notch): trim the skeleton
  where the cutter crosses it, and shape each cut end from the cutter. Masters
  stayed compatible on every test icon, with at most 0.33 px² of total error.

## Test setup

Masters at wght 100 / 400 / 700. Scored at 100–700 in steps of 75 against
the true boolean, worked out from scratch at each weight. Score: px² at 24 px
where the result and the truth disagree, sampled every 0.1 px. Below ~0.5 px²
the error spreads along edges and isn't visible.

| Icon | Boolean | Built from |
|---|---|---|
| Magnifier | Merge | Ring + handle starting inside the ring's stroke |
| Slash "off" | Cut with gap, then add | Ring − 1 px gap each side of slash + slash |
| Badge | Cut with gap, then add | Square outline − 1 px gap around a dot + dot |
| Contrast | Clip | Ring + half disc filling the left half of the counter |

## Methods

| Method | How |
|---|---|
| Overlap | Parts stay separate and overlap; nonzero fill merges them. Can't make gaps. |
| Negative shape | Cutter drawn reversed so it cancels ink beneath it. |
| Boolean per master | Real boolean (Skia) at each master. Equivalent to flattening in a design tool per weight. |
| Boolean + repair | The same, then reorder shapes and move start points to match the default. |
| Skeleton cut | Trim the skeleton at the cutter; cut ends take the cutter's shape; clearance is a rule. |

## Results (worst error in px², or ✗ = masters don't match, font can't be built)

| Method | Magnifier | Slash "off" | Badge | Contrast |
|---|---|---|---|---|
| Overlap | 0.04 | 13.76 (no gap) | 6.84 (no gap) | 0.00 |
| Negative shape | 0.04 | 83.86 | 35.77 | 0.00 |
| Boolean per master | 0.12 | ✗ shape order | ✗ 10 vs 12 points | 0.00 |
| Boolean + repair | 0.12 | 0.33 | ✗ 10 vs 12 points | 0.00 |
| **Skeleton cut** | **0.12** | **0.33** | **0.16** | **0.00** |

## Findings

1. **Merges: use overlap.** Exact, nothing to compute. Booleans per master
   also worked on the magnifier, by luck: merging didn't change the structure.
   **Trap:** overlapping parts must run the same direction. My first run had
   the handle reversed, and the overlap rendered as a hole. SVGs arrive with
   either direction, so the pipeline sets direction from the part's role.
   Overlaps are fine in variable fonts. When cutting static fonts from the
   variable one, merge overlaps at that step (the fontTools instancer can).
2. **Clips: make it a dependency.** The half disc either shares the ring's
   inner-radius formula or overlaps halfway into the ring's stroke. Both exact.
3. **Cut-outs with a gap: only the skeleton cut is reliable.**
   - Negative shapes fail whenever the cutter extends past single-layer ink.
     The gap strip shows as ink in empty space, and the badge dot cancelled into a hole.
   - Per-master booleans broke compatibility on both icons: different shape
     order on the slash, and different point counts on the badge (Skia splits
     curves at different places at the thin weight).
   - Repair fixes order and start points, but can't add missing points. It's
     also guesswork: it matches shapes by their centres.
   - The skeleton cut fixes the point count by construction.

## Keeping design intent

As far as I know, Figma and Illustrator flatten boolean groups into one path
on SVG export, so the pipeline can't recover which shape was the cutter or how
big the gap was. Both tools can write layer names into the SVG as `id`s, so a
naming grammar survives export. **Proposal to test, not settled:**

| Layer name | Meaning |
|---|---|
| `slash cut gap=1` | Drawn, and cuts every stroke it crosses with 1 px clearance |
| `notch cut gap=1 hidden` | Cuts, not drawn |
| `dot solid` | Filled part; gains a share of the weight change |
| `fill clip=ring.counter` | Edge follows the ring's inner edge |
| `check knockout` | Wound opposite to its container (flips to a hole at FILL 1) |

Alternative: a Figma plugin that reads live boolean groups. That's more
reliable inside Figma, but it doesn't cover Illustrator or hand-written SVG.
Start with layer names; add the plugin later.

## Linter rules

1. **A cut has a valid weight range.** If the gap plus half the stroke grows
   past the stroke it cuts, the structure changes. Compute the range; fail
   clearly if the axis exceeds it.
2. **Small counters have a floor.** Inward-growing strokes shrink counters.
   Below a minimum the construction must change (possibly a hand-drawn opsz 20 master).
3. **Direction comes from role**, never from the source file.
4. **Booleans per master are a fallback**: allowed only when the compatibility
   gate proves exact structural match, and flagged for review.

## Next tests

- Cuts on curved skeletons (a slash through a bell): cut ends slide along the curve as weight changes.
- Several cutters on one stroke; crossing cutters.
- Ten real icons through the layer-name grammar from both Figma and Illustrator.

Stroke widths are research 01's placeholders. Gap 1 px. skia-pathops 0.9.2,
fontTools 4.69.1, numpy for sampling.
