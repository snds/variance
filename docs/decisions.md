# Decisions

Decisions Sean has made, newest first. Each links to the research that framed it.

| Date | Decision | Detail | From |
|---|---|---|---|
| 2026-11-28 | **Shared parts ship right after v1** | Part matching across icons needs research first. | [App flows](design/app-flows.md#open-decisions-for-sean) |
| 2026-11-28 | **Fix scope: intent carries, amounts stay** | A pin (which side holds) carries along wght and to GRAD; exact amounts stay at their master; opsz stays separate. | [App flows](design/app-flows.md#scope-one-master-or-along-an-axis) |
| 2026-11-28 | **Rule confidence: three levels with reasons** | No percentages. | [App flows](design/app-flows.md#open-decisions-for-sean) |
| 2026-11-28 | **References live on each icon, outside the source** | `icons/<name>/refs/<name>@wght=<w>.svg`; used for scores and fitting only. | [App flows](design/app-flows.md#on-disk-format) |
| 2026-11-28 | **Retraining is a button with an impact preview** | Never automatic. | [App flows](design/app-flows.md#open-decisions-for-sean) |
| 2026-11-28 | **The app runs locally as a web app** | `variance serve` opens a browser UI over the same Python core the CLI and CI use. | [App flows](design/app-flows.md#open-decisions-for-sean) |
| 2026-11-28 | **Variance owns the source after import, in an open local format** | Re-importing an SVG is a merge. Sean's condition: everything is saved locally as open files (skeleton SVG, settings JSON), readable without Variance. | [App flows](design/app-flows.md#on-disk-format) |
| 2026-11-28 | **Small sizes: collapse only in v1** | A part can shrink to nothing below a size. Alternate constructions (a second source swapped in by feature variations) come later. | [App flows](design/app-flows.md#open-decisions-for-sean) |
| 2026-11-28 | **Outline import is in v1** | Revises "v1 input is stroked skeleton SVG only". Outlined SVG is fitted and labelled as fitted, with guesses in the import report. | [App flows](design/app-flows.md#open-decisions-for-sean), [05](research/05-any-icon-set.md) |
| 2026-11-26 | **Design for hand-drawn overrides** (nice-to-have, not v1) | Users need a glyph editor, like Glyphs, to adjust each generated master's points. To keep builds repeatable, store an override as point moves (deltas) on top of the generated master for one icon at one axis location. It never replaces the drawing. Point moves can't add or remove points, so structural changes stay in the skeleton. When the source's structure changes, the override is flagged stale rather than applied. | [01](research/01-construction-and-idempotency.md#open-decisions) |
| 2026-11-26 | **FILL midpoints: test all three options** | An extra master at FILL 0.5, a remapped FILL curve (`avar`), and counters that shrink around details. Test them on ten real icons before choosing. | [01](research/01-construction-and-idempotency.md#open-decisions) |
| 2026-11-26 | **Ship wght and FILL first**, then opsz and GRAD | | [01](research/01-construction-and-idempotency.md#open-decisions) |
| 2026-11-26 | **v1 input is stroked skeleton SVG only** | Sean also asked for boolean construction to be tested, which became [research 02](research/02-boolean-construction.md). | [01](research/01-construction-and-idempotency.md#open-decisions) |
