# 03 · Rebuilding 40 hard icons

_Research note · 2026-11-26 · Live version with proof images:
[03-rebuilding-real-icons.html](03-rebuilding-real-icons.html)_

The 20 hardest Material Symbols and 20 hardest IBM Carbon icons, rebuilt as
Variance sources (centre lines, solids, knockouts, cut rules), checked against
the originals and, for Material, against Google's weight 100 and 700 masters.

## Answer

- **Default style: exact.** 38 of 40 match to within 1/20 px. The other 2 hit a
  Skia boolean bug, not a source-format limit.
- **Exact is the easy part.** Patches (fixed shapes) can match anything. What
  counts is the share of ink driven by rules. The automatic rebuild reached a
  median of 92% (Material) and 95% (Carbon). 26 of 40 reached 90%.
- **Weight is the big finding.** No single rule reproduces Google's masters.
  The best explains about 50% of the change at weight 100 and 14% at 700.
  Material anchors counters and moves the silhouette (the opposite of research
  01's placeholder), shifts lines, and redraws details per icon.

## Method

1. Score every icon (4,004 Material, 2,569 Carbon) for overlaps, gaps, holes,
   knockouts and solids. Take the top 20 of each (`picks.json`).
2. Rebuild: centre lines (medial axis, fixed seed), lines and arcs, stroke vs
   solid vs knockout, then a search over cut rules (gap, side).
3. Patch the rest: fixed shapes that add or remove ink. Thin = edge tolerance,
   thick = a missed part.
4. Check at 960×960. Exact = no difference thicker than 1/20 px.

Rebuilds are byte-identical run to run.

## Gaps in the automatic rebuild

| Gap | Example | Fix |
|---|---|---|
| Dot or short stroke? Same width, can't tell from the outline. | deselect, padel | Layer name `solid`. |
| Gap learned as stroke ends, not a cut. Closes at heavier weight. | notification--off | Layer name `cut gap=1`. |
| Closed rings and organic curves missed by the centre-line finder. | emoji_language, portfolio--management | Drawn as strokes in a real source; add a closed-loop case to the tool. |
| Filled shapes with knockouts patched instead of built. | kubernetes--control-plane-node | Layer name `knockout`. |

Carbon needed one-sided cuts (`side=left|right`); Material didn't.

## Weight (Material only)

Median share of Google's own change reproduced (100% = perfect, 0% = no better
than not changing):

| Recipe | wght 100 | wght 700 |
|---|---|---|
| Centre strokes (both edges move) | 22% | 9% |
| Grow the outline (no source) | 31% | 0% |
| Counters stay put (measured from Google) | 50% | 14% |

## What this means

1. Intent goes in layer names: `solid`, `cut`, `knockout` are required where
   they apply; the linter should flag likely misses.
2. Strokes need an anchor rule (inner / outer / centre edge stays put).
3. Matching Material at every weight needs override masters; that moves the
   override editor into scope for the weight extremes.
4. A Variance set can define its own weight behaviour from rules alone.
   Matching Google's masters is a choice.

## Next tests

- Fit the anchor rule per stroke against Google's masters.
- Hand-build five icons with no patches, to confirm the gaps are the tool's.
- Fix the closed-ring case.

## Per-icon results

Parts = strokes / solids / knockouts / cuts.

| Set | Icon | Default | Rules | Parts |
|---|---|---|---|---|
| carbon | `chart--spiral` | exact | 94% | 9/0/0/0 |
| carbon | `document--signed` | exact | 96% | 6/0/0/1 |
| carbon | `encryption` | exact | 98% | 14/0/0/0 |
| carbon | `fingerprint-recognition` | engine bug | 81% | 2/3/0/1 |
| carbon | `firewall--classic` | exact | 98% | 6/0/0/0 |
| carbon | `group-objects` | exact | 95% | 15/0/0/0 |
| carbon | `ibm--mq` | exact | 90% | 8/0/0/0 |
| carbon | `ibm-cloud--security-compliance-center-workload-protection` | exact | 98% | 4/0/0/1 |
| carbon | `iot--platform` | exact | 98% | 16/0/0/0 |
| carbon | `keyboard--off` | exact | 88% | 9/0/0/0 |
| carbon | `kubernetes--control-plane-node` | exact | 56% | 0/2/3/0 |
| carbon | `load-balancer--pool` | exact | 99% | 13/0/0/1 |
| carbon | `logo--kubernetes` | engine bug | 45% | 1/1/1/1 |
| carbon | `microservices--2` | exact | 85% | 0/8/2/0 |
| carbon | `notification--off` | exact | 98% | 11/0/0/0 |
| carbon | `portfolio--management` | exact | 38% | 4/0/0/0 |
| carbon | `qiskit` | exact | 95% | 25/0/0/0 |
| carbon | `result--new` | exact | 94% | 7/1/0/0 |
| carbon | `smoke` | exact | 99% | 5/0/0/0 |
| carbon | `soil-moisture--global` | exact | 98% | 10/0/0/0 |
| material | `assignment_globe` | exact | 89% | 10/0/0/3 |
| material | `dataset_linked` | exact | 92% | 14/0/0/1 |
| material | `deselect` | exact | 60% | 5/0/0/0 |
| material | `desktop_cloud_stack` | exact | 97% | 6/0/0/0 |
| material | `emoji_language` | exact | 52% | 15/0/0/0 |
| material | `fingerprint_off` | exact | 59% | 1/4/0/0 |
| material | `hdr_plus_off` | exact | 90% | 10/1/0/2 |
| material | `keyboard_lock` | exact | 77% | 3/2/0/0 |
| material | `notifications_off` | exact | 93% | 10/0/0/0 |
| material | `order_approve` | exact | 94% | 5/1/1/0 |
| material | `padel` | exact | 77% | 3/9/0/0 |
| material | `poker_chip` | exact | 98% | 24/1/0/0 |
| material | `prescriptions` | exact | 96% | 7/0/0/2 |
| material | `repeat_one_on` | exact | 97% | 9/1/9/0 |
| material | `shuffle_on` | exact | 98% | 9/1/9/0 |
| material | `supervised_user_circle_off` | exact | 86% | 6/2/5/0 |
| material | `swap_driving_apps_wheel` | exact | 93% | 8/0/0/0 |
| material | `theater_comedy` | exact | 91% | 8/0/0/2 |
| material | `water_do` | exact | 88% | 13/0/0/0 |
| material | `yoshoku` | exact | 96% | 10/0/0/0 |

Code: `prototype/rebuild/` (`batch.py` runs everything; `results.json` holds
the numbers). Icon data is not committed; set `VARIANCE_SRC` to a folder with
the Material Symbols font instances and the `@carbon/icons` package.

Material Symbols © Google and Carbon icons © IBM, both Apache License 2.0,
shown in the HTML for research. Material's internal values are not public; all
numbers here are measurements.
