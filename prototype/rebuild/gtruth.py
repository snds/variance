"""Ground-truth test for the fitter, using sets that are drawn as strokes.

Lucide and Tabler ship their real centre-lines (stroke-width 2, round caps and
joins). We outline each icon first, hand ONLY the outline to the fitter (as if
it were a filled icon from any other set), and then compare:
  - exactness and rule share, as in research 03
  - the recovered centre-lines against the true ones:
      recall    share of the true centre-line within 1/4 px of a recovered one
      precision share of the recovered centre-line within 1/4 px of a true one
      parts     recovered strokes vs true sub-paths
Filled styles (FILLED) are rebuilt the same way, without the centre-line check.
Usage: gtruth.py OUTDIR set variant N"""
import sys, os, json, random, time
import numpy as np
from scipy.spatial import cKDTree
from multiprocessing import Pool
import anyset as A, extract as X, residual as RS, source as V, raster as R

# filled styles rebuilt as solids + knockouts; W = the matching outline style's stroke
FILLED = {("heroicons", "solid24"): 60, ("remix", "fill"): 80, ("phosphor", "fill"): 60,
          ("tabler", "filled"): 80, ("fluent", "24_filled"): 60}

def dense(polys, step=2.0):
    """Resample polylines to <= step units apart, so a point-to-point distance
    is a point-to-curve distance."""
    out = []
    for p in polys:
        p = np.asarray(p)
        if len(p) < 2: out.append(p); continue
        for a, b in zip(p[:-1], p[1:]):
            n = max(1, int(np.ceil(np.hypot(*(b - a)) / step)))
            out.append(a + (b - a) * (np.arange(n)[:, None] / n))
        out.append(p[-1:])
    return np.vstack(out) if out else np.zeros((0, 2))

def run(args):
    s, v, n, outdir = args
    f = os.path.join(outdir, f"{s}-{n}.json")
    if os.path.exists(f): return json.load(open(f))
    t = time.time()
    try:
        if (s, v) in FILLED:     # filled sets: no centre-lines to check, the set's outline stroke width
            lines, W, cap, join = [], FILLED[(s, v)], "round", "round"
        else:
            lines, W, cap, join = A.skeleton(s, v, n)
        c = A.contours(s, v, n)
        X.stroke_parts_v2 = lambda mask, outline, W_, grid, join_, prefix: X.stroke_parts_from_mask(mask, W_, grid, cap, join_, prefix)
        parts, fitted = X.rebuild(c, W, grid=0, cap=cap, join=join)
        full, patches = RS.close_gap(parts, c, W)
        orig = X.contours_to_path(c); om = X.mask_of(orig)
        final = X.score(V.generate(full), om)
        ink = RS.area(orig) / 1600
        patch_area = sum(p["patch"]["area"] for p in full if p.get("patch")) / 1600
        true = dense(lines)
        rec = [P for p in parts if p["kind"] == "stroke" and not (p.get("role") or {}).get("knockout")
               for P in R.flatten(V.to_contours(V.path_from_d(p["d"])), 12)]
        recp = dense(rec)
        out = {"set": s, "icon": n, "W": W, "fit_px2": round(fitted[0], 2), "fit_core": fitted[1],
               "final_px2": round(final[0], 2), "final_core": final[1],
               "rule_share": round(1 - min(patch_area, ink) / ink, 3),
               "patch_via": sorted({p["patch"].get("via", "") for p in full if p.get("patch")}),
               "true_paths": len(lines), "strokes": sum(p["kind"] == "stroke" for p in parts),
               "solids": sum(p["kind"] == "solid" and not (p.get("role") or {}).get("knockout") for p in parts),
               "knockouts": sum(bool((p.get("role") or {}).get("knockout")) for p in parts)}
        if len(true) and len(recp):
            dt = cKDTree(recp).query(true)[0]; dr = cKDTree(true).query(recp)[0]
            out.update(recall=round(float((dt <= 10).mean()), 3), precision=round(float((dr <= 10).mean()), 3),
                       median_err=round(float(np.median(dt)), 1))
        else:
            out.update(recall=0.0, precision=0.0, median_err=None)
    except Exception as e:
        out = {"set": s, "icon": n, "error": repr(e)[:160]}
    out["secs"] = round(time.time() - t, 1)
    json.dump(out, open(f, "w"))
    return out

if __name__ == "__main__":
    outdir, s, v, N = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
    os.makedirs(outdir, exist_ok=True)
    names = A.names(s, v); random.Random(7).shuffle(names)
    with Pool(4) as pool:
        for r in pool.imap_unordered(run, [(s, v, n, outdir) for n in names[:N]]):
            print(r.get("icon"), r.get("final_core"), r.get("rule_share"), r.get("recall"), r.get("precision"), r.get("error", ""), r.get("secs"), flush=True)
