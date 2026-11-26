# Decisions

Decisions Sean has made, newest first. Each links to the research that framed it.

| Date | Decision | Detail | From |
|---|---|---|---|
| 2026-11-26 | **Design for hand-drawn overrides** (nice-to-have, not v1) | Users need a glyph editor, like Glyphs, to adjust each generated master's points. To keep builds repeatable, store an override as point moves (deltas) on top of the generated master for one icon at one axis location. It never replaces the drawing. Point moves can't add or remove points, so structural changes stay in the skeleton. When the source's structure changes, the override is flagged stale rather than applied. | [01](research/01-construction-and-idempotency.md#open-decisions) |
| 2026-11-26 | **FILL midpoints: test all three options** | An extra master at FILL 0.5, a remapped FILL curve (`avar`), and counters that shrink around details. Test them on ten real icons before choosing. | [01](research/01-construction-and-idempotency.md#open-decisions) |
| 2026-11-26 | **Ship wght and FILL first**, then opsz and GRAD | | [01](research/01-construction-and-idempotency.md#open-decisions) |
| 2026-11-26 | **v1 input is stroked skeleton SVG only** | Sean also asked for boolean construction to be tested, which became [research 02](research/02-boolean-construction.md). | [01](research/01-construction-and-idempotency.md#open-decisions) |
