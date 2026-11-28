"""Collect batch records into one table (JSON + console)."""
import sys, os, json, glob
import extract as X, icons_io as IO
out = sys.argv[1]
rows = [json.load(open(f)) for f in sorted(glob.glob(os.path.join(out, "*.json"))) if not f.endswith("summary.json")]
for r in rows:
    if r["set"] == "material":
        dm = X.mask_of(X.contours_to_path(IO.ms_contours(r["name"])))
        for loc, w in r["weights"].items():
            gm = X.mask_of(X.contours_to_path(IO.ms_contours(r["name"], loc)))
            w["change_px2"] = round(float((dm != gm).sum()) / 1600, 2)   # how far Google's own master moves
json.dump(rows, open(os.path.join(out, "summary.json"), "w"), indent=1)
for r in rows:
    w = r.get("weights") or {}
    ws = " ".join(f"{k}: chg {v['change_px2']:.0f} var {v['variance_px2']:.0f} edge {v['edge_px2']:.0f} naive {v['naive_px2']:.0f}" for k, v in w.items())
    print(f"{r['set'][:3]} {r['name'][:34]:34} ink {r['ink_px2']:6.1f} fit {r['fit_px2']:5.1f} final {r['final_px2']:4.2f}/{r['final_core']:<5} rules {r['rule_share']:.3f} detail {r['detail_px2']:5.1f} S{r['strokes']} So{r['solids']} K{r['knockouts']} C{len(r['cuts'])}  {ws}")
