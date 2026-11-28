# Manual-fix tooling: brief for the app design

_Design input · 2026-11-28 · From research 08 ([08-toward-100.md](../research/08-toward-100.md)).
Read this before designing the editor's master-fixing flows._

## The problem in one paragraph

Variance builds every master (weight, grade, optical size, fill) from one
source drawing: a centre-line skeleton plus part rules. Fed a reference's own
edge moves, it now reaches 89–94% of Google's weight masters on the 20
hardest Material icons. An automatic rule alone reaches 64–76%. The gap
between those two numbers is designer judgement. The editor's job is to let a
designer close that gap quickly, and to store each fix so it survives source
changes and teaches the rule.

## Design principle

**Every manual fix is a setting on the source, never a second drawing.**

- The source stays the only truth (repo rule: never generate a master from
  another master).
- A fix keeps working when the skeleton changes, because it hangs on a named
  part and segment, not on outline points.
- Each fix is a labelled example the rule can learn from.
- Point-level edits exist only as a last resort, and are flagged stale when
  the skeleton's topology changes (decided 2026-11-26, see
  [decisions.md](../decisions.md)).

## What the generator can already take (the data the UI edits)

Per part, per master. Units are 1/960 of the em (Material's grid); at 24 px,
40 units = 1 px.

| Setting | Applies to | Meaning | Default when unset |
|---|---|---|---|
| `sides.left[c][s]`, `sides.right[c][s]` | stroke | Distance from the centre-line to each side, per contour `c` and segment `s`. A side may cross the centre-line. | Half the master's stroke width each side (centred). |
| `sides.ends[c]` | open stroke, butt or square cap | Extra length at the start and the end (+ longer, − shorter). | 0 |
| `edges[c][s]` | solid, detail patch | How far each outline segment moves (+ = to its left). | Even grow from the rule. |
| `offset`, `width` | stroke | Older one-number-per-stroke form (research 07). | — |
| `grow` | solid | Older one-number form. | — |
| point deltas | any | Last resort; stale when topology changes. | none |

The automatic rule fills every setting. A manual fix overrides one value and
is marked as manual, so the rule never overwrites it.

## Kinds of fix, and the tool for each

| Kind (how common) | Example | Tool | Stores |
|---|---|---|---|
| Which side holds still (most common) | A bar that should thin from the top, not both sides | **Side pins**: click a side of a segment to hold it, or drag it to an exact position. A pin on the other side moves it instead. | `sides` for that segment |
| End length | A stroke that should stop short at a junction | **End handles**: drag an end along the stroke. | `sides.ends` |
| End shape (next research step) | Angled or tapered cuts | **End style** picker on the end handle: flat, angled, tapered. | Planned: end angle |
| Part position or size | A badge that shifts so its gap stays even | **Part nudge**: move or scale one part at one master. | Planned: per-master transform on the part |
| Real redraw (rare, under 4% of edges) | A detail dropped at a light weight | **Point override**: edit outline points at one master. | Point deltas, staleness-checked |

## The strongest tool: fit to a drawing

If a reference exists for a master (a designer's hand drawing, or another
set's master), Variance can fit its own settings to it automatically. That is
exactly how research 08 measured its 89–94% ceiling. So the flow can be:

1. Designer draws or imports one master by hand, once.
2. Variance fits `sides`, `ends` and `edges` to it and shows the diff.
3. Designer accepts the fit; the drawing becomes settings on the source.
4. Whatever the fit can't express shows up as a short list of remaining misses.

This turns hand drawing into parametric data instead of a parallel file.

## Support features

- **Diff overlay and score.** Show a master over its reference: grey where
  they agree, blue where only the reference has ink, red where only ours
  does. Show the share of edges within 0.25 px. Clicking a miss selects the
  part and the control that owns it.
- **Review queue.** Rank icons by risk instead of asking for a full check:
  where the rule is unsure, where a check fails (a counter closes, two parts
  touch, a stroke goes under the minimum width), or where the score against a
  reference is low.
- **Learn from fixes.** Each pin, end move or nudge is a training example.
  Retrain the set's rule on them. For a new icon set the loop is: fix about
  20 icons, retrain, review the rest by the queue.
- **Scope of a fix.** A fix applies to one master by default. Offer "same at
  all heavier weights" (or lighter), because designers usually make the same
  call along an axis.

## End-to-end flow to design around

1. **Import** a set (SVGs). Variance fits sources; flags any icon not rebuilt
   exactly.
2. **Generate** all masters with the set's rule.
3. **Triage** in the review queue, worst first.
4. **Fix** with side pins, end handles, part nudge, or fit-to-drawing.
5. **Retrain** the rule from the fixes; regenerate the unfixed icons.
6. **Check** compatibility and export the variable font.

## Open questions for the design thread

- How to show a per-segment pin on a curved stroke without clutter (pins
  only on hover, or only on the selected part?).
- Whether a fix set at wght 700 should propagate to GRAD and opsz masters,
  or be per axis.
- How to present the rule's confidence so the queue feels trustworthy.
- Where reference drawings live (same file as sources, or a side layer).
