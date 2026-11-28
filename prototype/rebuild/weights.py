"""Weight test: does a rebuilt source reproduce a set's real weights?

Phosphor ships thin / light / regular / bold drawn by its own designers.
Research 05 found its weights are one centre-line drawn with a different
pen. So the test is strict: rebuild ONLY the regular weight from its outline,
then change ONLY the stroke width (Phosphor's own pen sizes: 8, 12, 16, 24 on
its 256 grid) and compare with Phosphor's real thin, light and bold.

Scores per icon and weight:
  exact   no difference thicker than 1/20 px (same test as the default style)
  px2     area that differs, px^2 at 24 px
  edges   share of the real weight's edge pixels within 0.25 px of ours
Compared with the naive approach: grow or shrink the regular outline evenly.
Usage: weights.py OUTDIR N"""
import sys, os, json, random, time
import numpy as np
from scipy import ndimage as ndi
from multiprocessing import Pool
import pathops
import anyset as A, extract as X, residual as RS, source as V, edgemove as E

PEN = {"thin": 30, "light": 45, "regular": 60, "bold": 90}   # Phosphor's stroke widths, x960/256

def at_width(parts, W):
    out = []
    for p in parts:
        if p.get("patch") and p["patch"]["type"] == "sliver": continue   # fitting tolerance of the default only
        q = dict(p)
        if q["kind"] == "stroke": q["width"] = W
        out.append(q)
    return out

def naive(orig, d):
    s = pathops.Path(); orig.draw(s.getPen()); s.stroke(2 * abs(d), V.CAP["round"], V.JOIN["round"], 4); s = V.fill(s)
    return pathops.op(orig, s, pathops.PathOp.UNION if d > 0 else pathops.PathOp.DIFFERENCE)

def edges_within(gen_mask, real_mask):
    """Share of the real weight's edge pixels within 0.25 px (10 units) of ours."""
    edge = real_mask & ~ndi.binary_erosion(real_mask)
    s = E.sdf(gen_mask)                   # px at 480, + inside ours
    return float((np.abs(s[edge] - 0.5) * E.U <= 10).mean()) if edge.any() else 1.0

def run(args):
    n, outdir = args
    f = os.path.join(outdir, f"{n}.json")
    if os.path.exists(f): return json.load(open(f))
    t = time.time(); W = PEN["regular"]
    try:
        c = A.contours("phosphor", "regular", n)
        X.stroke_parts_v2 = lambda mask, outline, W_, grid, join_, prefix: X.stroke_parts_from_mask(mask, W_, grid, "round", join_, prefix)
        parts, fitted = X.rebuild(c, W, grid=0, cap="round", join="round")
        full, _ = RS.close_gap(parts, c, W)
        orig = X.contours_to_path(c)
        ink = RS.area(orig) / 1600
        patch_area = sum(p["patch"]["area"] for p in full if p.get("patch")) / 1600
        rec = {"icon": n, "default_core": X.score(V.generate(full), X.mask_of(orig))[1],
               "rule_share": round(1 - min(patch_area, ink) / ink, 3), "dots": sum(bool(p.get("dot")) for p in full), "weights": {}}
        for w in ("thin", "light", "bold"):
            real = X.contours_to_path(A.contours("phosphor", w, n)); rm = X.mask_of(real)
            ours = V.generate(at_width(full, PEN[w])); nv = naive(orig, (PEN[w] - W) / 2)
            so, sn = X.score(ours, rm), X.score(nv, rm)
            rm2, om2, nm2 = (E.mask(V.to_contours(p)) for p in (real, ours, nv))
            rec["weights"][w] = {"ours_px2": round(so[0], 2), "ours_core": so[1], "ours_edges": round(edges_within(om2, rm2), 4),
                                 "naive_px2": round(sn[0], 2), "naive_core": sn[1], "naive_edges": round(edges_within(nm2, rm2), 4)}
    except Exception as e:
        rec = {"icon": n, "error": repr(e)[:160]}
    rec["secs"] = round(time.time() - t, 1)
    json.dump(rec, open(f, "w")); return rec

if __name__ == "__main__":
    outdir, N = sys.argv[1], int(sys.argv[2]); os.makedirs(outdir, exist_ok=True)
    names = A.common("phosphor", "regular", "thin", "light", "bold"); random.Random(7).shuffle(names)
    with Pool(4) as pool:
        for r in pool.imap_unordered(run, [(n, outdir) for n in names[:N]]):
            w = r.get("weights", {})
            print(r["icon"], r.get("rule_share"), {k: (v["ours_core"], v["ours_edges"], v["naive_edges"]) for k, v in w.items()}, r.get("error", ""), flush=True)
