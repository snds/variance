# Rebuild

Turns outlined icons into Variance sources and checks them (research 03),
and measures how Google corrects Material across masters (research 04).

    export VARIANCE_SRC=/path/to/src   # ms-*.ttf instances, ms-outlined.codepoints, carbon/package/svg/32
    python batch.py OUT [material|carbon] [names...]
    python summarize.py OUT

| File | Job |
|---|---|
| `icons_io.py` | Load Material (font) and Carbon (SVG) onto one 960-unit grid |
| `score.py`, `picks.json` | Difficulty score; the 20 hardest per set |
| `source.py` | Source model and generator (strokes, solids, knockouts, cuts) |
| `extract.py`, `refine.py` | Outline → skeleton + roles (refine.py is the unfinished exact-fit v2) |
| `residual.py` | Patches that close the remaining gap |
| `batch.py`, `summarize.py`, `view.py` | Run, tabulate, proof images |
| `edge_stats.py` | How Google's masters move edges |
| `results.json` | Results for the 40 icons (research 03) |
| `edges.py` | Research 04: every edge of every Material glyph, measured across six masters |
| `fingerprints.py`, `tiers.py` | Context rules, fingerprint labels, fix tiers, families |
| `risk.py` | Predict hand work from shape; checks on Material, applies to Carbon |
| `carbon16.py` | Carbon's 16 px redraws against its 32 px drawings |
| `overlay.py` | Default vs master contact sheets |
| `material-ranking.csv`, `material-rules.json`, `material-tiers-summary.json`, `carbon16-results.json` | Research 04 outputs |
