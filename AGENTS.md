# AGENTS.md — Variance

Agent contract for this repo. Owner: Sean Sands. Context profile: `personal-solo`
(branch + PR into `main`; Sean merges).

## What this is
A pipeline from SVG icons to a variable icon font matching Material Symbols'
axes (FILL 0–1, wght 100–700, GRAD −50–200, opsz 20–48).

## Read first
1. `README.md`
2. `docs/research/` — newest numbered doc first.

## Standing rules
- **Skeleton is the source of truth.** Never generate a master from another
  generated master. Every master comes from the source by a pure function.
- **Topology comes from the source.** Contour order, start point and direction
  are set by the part list, never chosen from geometry per master.
- **Builds must be reproducible.** Pin timestamps (`SOURCE_DATE_EPOCH`), round
  once at the end, convert curves jointly across masters. A rebuild with no
  source change must give the same SHA-256.
- **Don't publish Material's numbers as ours.** Material Symbols' internal
  values aren't public. Mark any guessed value as a placeholder.
- No employer (Centric) content in this repo.
- Write for a designer audience: plain language, answer first.
