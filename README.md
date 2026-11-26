# Variance

Turn SVG icons from any source (Figma, Illustrator, or hand-written) into a
variable icon font, with Google Material Symbols as the quality bar: the
`FILL`, `wght`, `GRAD` and `opsz` axes.

The core idea: **draw the skeleton, not the outline.** Each icon is stored as
centre-lines plus a few construction rules. Every master is generated from that
one source by fixed recipes, so masters match point-for-point by construction
and a rebuild gives a byte-identical font.

## Status

Research phase. See [docs/research](docs/research/).

| Doc | What it covers |
|---|---|
| [01 · Construction and idempotency](docs/research/01-construction-and-idempotency.md) | How to build icons for variability, the correction recipes, and what the prototype proved. A live version with the prototype font is [01-construction-and-idempotency.html](docs/research/01-construction-and-idempotency.html). |
| [02 · Boolean construction](docs/research/02-boolean-construction.md) | Five ways to build merges, cut-outs and clips from skeletons, tested against true booleans. Proof tables: [02-boolean-construction.html](docs/research/02-boolean-construction.html). |

## Prototype

[`prototype/`](prototype/) builds a two-icon, four-axis variable font from
skeleton definitions. See its [README](prototype/README.md).

## Layout

- `docs/research/` — research write-ups, numbered.
- `prototype/` — throwaway proof code. The real pipeline will get its own package.
