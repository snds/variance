# Variance

Turn SVG icons from any source (Figma, Illustrator, or hand-written) into a
variable icon font, with Google Material Symbols as the quality bar: the
`FILL`, `wght`, `GRAD` and `opsz` axes.

The core idea: **draw the skeleton, not the outline.** Each icon is stored as
centre-lines plus a few construction rules. Every master is generated from that
one source by fixed recipes, so masters match point-for-point by construction
and a rebuild gives a byte-identical font.

## Status

Research phase. See [docs/research](docs/research/) and the [decision log](docs/decisions.md).

| Doc | What it covers |
|---|---|
| [01 · Construction and idempotency](docs/research/01-construction-and-idempotency.md) | How to build icons for variability, the correction recipes, and what the prototype proved. A live version with the prototype font is [01-construction-and-idempotency.html](docs/research/01-construction-and-idempotency.html). |
| [02 · Boolean construction](docs/research/02-boolean-construction.md) | Five ways to build merges, cut-outs and clips from skeletons, tested against true booleans. Proof tables: [02-boolean-construction.html](docs/research/02-boolean-construction.html). |
| [03 · Rebuilding real icons](docs/research/03-rebuilding-real-icons.md) | The 20 hardest Material and 20 hardest Carbon icons rebuilt as Variance sources, and what Google's weights do. [HTML](docs/research/03-rebuilding-real-icons.html). |
| [04 · Correction fingerprints](docs/research/04-correction-fingerprints.md) | Every edge of all 4,004 Material Symbols across six masters: rules, five fix kinds, and the redraw list. [HTML](docs/research/04-correction-fingerprints.html). |
| [05 · Any icon set](docs/research/05-any-icon-set.md) | Six more sets (Lucide, Tabler, Phosphor, Fluent, Heroicons, Remix): an answer-key test of the fitter, weight and size patterns, and what FILL does. [HTML](docs/research/05-any-icon-set.html). |
| [06 · Closing the weight gap](docs/research/06-closing-the-weight-gap.md) | Dot primitive, a pen-only weight test on Phosphor, and a learned anchor rule for Material. [HTML](docs/research/06-closing-the-weight-gap.html). |
| [07 · Anchors in the generator](docs/research/07-anchors-in-the-generator.md) | The learned anchor rule built into the generator, scored on the 20 hardest Material icons at wght 100 and 700. [HTML](docs/research/07-anchors-in-the-generator.html). |
| [08 · Toward 100%](docs/research/08-toward-100.md) | Finer generator controls (per-segment sides, stroke ends, edge moves for solids and patches), two measuring fixes, and editor tooling for what can't be automated. [HTML](docs/research/08-toward-100.html). |

## Prototype

[`prototype/`](prototype/) builds a two-icon, four-axis variable font from
skeleton definitions. See its [README](prototype/README.md).

## Layout

- `docs/research/` — research write-ups, numbered.
- `prototype/` — throwaway proof code. The real pipeline will get its own package.
