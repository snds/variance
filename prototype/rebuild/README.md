# Rebuild

Turns outlined icons into Variance sources and checks them (research 03),
measures how Google corrects Material across masters (research 04), and runs
the same tests on any SVG icon set (research 05).

    export VARIANCE_SRC=/path/to/src   # ms-*.ttf instances, ms-outlined.codepoints, carbon/package/svg/32
    python batch.py OUT [material|carbon] [names...]
    python summarize.py OUT
    # research 05: six more sets under $VARIANCE_SRC/sets/<npm package>/package
    python pairs.py OUT.json [job ...]          # weight/size edge moves from pixels
    python fillfp.py OUT.json [set ...]         # FILL fingerprints
    python gtruth.py OUTDIR <set> <variant> N   # answer-key / filled rebuilds
    python fig05.py PAIRS.json FILL.json OUTDIR

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
| `anyset.py` | Research 05: load any SVG set (strokes outlined with their pen, fill rules, helpers dropped) |
| `edgemove.py`, `pairs.py` | Edge moves measured from pixels, for sets without matching points |
| `fillfp.py` | FILL fingerprints: filled style vs the outline with counters flooded |
| `gtruth.py` | Answer-key test on Lucide/Tabler centre-lines; filled rebuilds |
| `fig05.py` | Research 05 figures |
| `anyset-pairs.json`, `anyset-fill.json`, `anyset-rebuilds.csv` | Research 05 outputs |
| `weights.py` | Research 06: rebuild Phosphor regular, change only the pen, score against thin/light/bold |
| `anchor.py` | Research 06: learn Material's edge moves (anchor choice) and score on held-out icons |
| `weights-phosphor.csv`, `anchor-material.json`, `results-dots.json` | Research 06 outputs (results-dots = research 03's 40 icons with the dot primitive) |
| `learned.py`, `learned-material20.json` | Research 07: per-side stroke moves in the generator (learned rule vs table vs centred), scored on research 03's 20 Material icons |
