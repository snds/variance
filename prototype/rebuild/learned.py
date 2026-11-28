"""Research 07: put a per-stroke anchor into the generator and score it.

Each stroke in a source gets, per master, one move for its left side and one
for its right side. That is the same as a new width (W + left + right) and a
small sideways shift of the centre-line ((left - right) / 2). Solids get one
grow amount. Patches and cut gaps stay as in the default.

Where the per-side moves come from (all compared on research 03's 20 Material
icons, against Google's wght 100 and wght 700):
  centred   every stroke just gets Google's new width (research 03's recipe)
  table     research 04's context rule, read at each stroke side
  learned   research 06's learned rule, trained on all OTHER Material icons
  best      Google's own edge moves at each side (one number per side): the
            most a per-stroke anchor can do, an upper bound
Scores: edges = share of Google's edge pixels within 0.25 px of ours;
icon passes if 95%+. Also px2 of differing area.
Usage: learned.py EDGES.npz OUT.json"""
import sys, json
import numpy as np
from scipy.spatial import cKDTree
from sklearn.ensemble import HistGradientBoostingRegressor
import pathops
import extract as X, icons_io as IO, residual as RS, source as V, edgemove as E, raster as R
import anchor as AN, weights as WT

LOCS = {"w100": (0, 28), "w700": (1, 126)}     # column in edges, Google's measured new stroke width
W = 80
X.stroke_parts_v2 = lambda mask, outline, W_, grid, join, prefix: X.stroke_parts_from_mask(mask, W_, grid, "square", join, prefix)

def side_moves(part, tree, mids, nrm, k, Wd):
    """Median move of the glyph edges along each side of a stroke part."""
    if part.get("dot"):
        pts = [tuple(map(float, part["d"][1:].split(" L")[0].split()))]; nn = [(0.0, 0.0)]
    else:
        polys = R.flatten(V.to_contours(V.path_from_d(part["d"])), 12)
        if not polys: return None
        P = np.vstack(polys)
        if len(P) < 2: return None
        d = np.gradient(P, axis=0); d /= np.maximum(np.linalg.norm(d, axis=1, keepdims=True), 1e-9)
        pts = P; nn = np.stack([-d[:, 1], d[:, 0]], 1)      # left normal
    out = []
    for sgn in (1, -1):                                     # left side, right side
        vals = []
        for p, n in zip(pts, nn):
            if n[0] == 0 and n[1] == 0: continue
            q = np.asarray(p) + sgn * n * Wd / 2
            for j in tree.query_ball_point(q, 14):
                if np.dot(nrm[j], sgn * n) > 0.7: vals.append(k[j])
        out.append(float(np.median(vals)) if vals else None)
    return out

def at_master(parts, Wn, moves_of):
    """The source at a master: per-side moves -> width + centre-line shift."""
    out = []
    for p in parts:
        if p.get("patch") and p["patch"]["type"] == "sliver": continue
        q = dict(p)
        if q["kind"] == "stroke" and not p.get("patch"):
            m = moves_of(p)
            if m is None or None in m:
                q["width"] = Wn
            else:
                kl, kr = m
                if (p.get("role") or {}).get("knockout"): kl, kr = -kl, -kr   # a knockout's edges are ink edges facing in
                q["width"] = max(4.0, W + kl + kr); q["offset"] = (kl - kr) / 2
        elif q["kind"] == "solid" and not p.get("patch"):
            m = moves_of(p)
            if m is not None: q["grow"] = m if not (p.get("role") or {}).get("knockout") else -m
        out.append(q)
    return out

def solid_move(part, tree, mids, k):
    c = V.to_contours(V.path_from_d(part["d"]))
    P = np.vstack(R.flatten(c, 12)) if c else np.zeros((0, 2))
    vals = [k[j] for p in P for j in tree.query_ball_point(p, 6)]
    return float(np.median(vals)) if vals else None

def main(npz, out):
    Z = np.load(npz); A = Z["edges"]; names = [str(x) for x in Z["names"]]
    Xf, ctx, g, L = AN.features(A)
    rules = json.load(open(__file__.replace("learned.py", "material-rules.json")))
    picks = json.load(open(__file__.replace("learned.py", "picks.json")))["material"]
    pid = {names.index(n) for n in picks if n in names}
    inpick = np.isin(g, list(pid))
    preds = {}
    for loc, (li, Wn) in LOCS.items():
        k = A[:, 9 + li]; par = A[:, 15 + li] <= 10
        tr = ~inpick & par
        m = HistGradientBoostingRegressor(loss="absolute_error", max_iter=300, max_leaf_nodes=63, categorical_features=[0], random_state=7)
        m.fit(Xf[tr], k[tr], sample_weight=L[tr])
        preds[loc] = {"learned": m.predict(Xf), "table": np.array([rules[loc]["move"].get(c, 0.0) for c in ctx]), "best": k}
        print("trained", loc, flush=True)
    res = {}
    for n in picks:
        gi = names.index(n); ix = np.nonzero(g == gi)[0]
        mids = A[ix][:, 5:7]; nrm = A[ix][:, 7:9]; tree = cKDTree(mids)
        c = IO.ms_contours(n)
        parts, _ = X.rebuild(c, W, grid=0)
        full, _ = RS.close_gap(parts, c, W)
        res[n] = {}
        for loc, (li, Wn) in LOCS.items():
            real = X.contours_to_path(IO.ms_contours(n, loc)); rm = E.mask(V.to_contours(real)); rmx = X.mask_of(real)
            r = {}
            for how in ("centred", "table", "learned", "best"):
                if how == "centred":
                    src = at_master(full, Wn, lambda p: None)
                else:
                    kk = preds[loc][how][ix]
                    src = at_master(full, Wn, lambda p: side_moves(p, tree, mids, nrm, kk, W) if p["kind"] == "stroke" else solid_move(p, tree, mids, kk))
                try:
                    gen = V.generate(src)
                    r[how] = {"edges": round(WT.edges_within(E.mask(V.to_contours(gen)), rm), 4), "px2": round(X.score(gen, rmx)[0], 2)}
                except pathops.PathOpsError as e:
                    r[how] = {"error": repr(e)[:80]}
            res[n][loc] = r
            print(n, loc, {h: v.get("edges") for h, v in r.items()}, flush=True)
        json.dump(res, open(out, "w"), indent=1)

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

def figure(npz, names_, out, loc="w700", size=170):
    """Google's master against ours, per recipe: grey = both, blue = Google
    only, red = ours only."""
    from PIL import Image
    import fig05
    Z = np.load(npz); A = Z["edges"]; names = [str(x) for x in Z["names"]]
    Xf, ctx, g, L = AN.features(A)
    rules = json.load(open(__file__.replace("learned.py", "material-rules.json")))
    picks = json.load(open(__file__.replace("learned.py", "picks.json")))["material"]
    inpick = np.isin(g, [names.index(n) for n in picks])
    li, Wn = LOCS[loc]; k = A[:, 9 + li]; par = A[:, 15 + li] <= 10
    m = HistGradientBoostingRegressor(loss="absolute_error", max_iter=300, max_leaf_nodes=63, categorical_features=[0], random_state=7)
    m.fit(Xf[~inpick & par], k[~inpick & par], sample_weight=L[~inpick & par]); pl = m.predict(Xf)
    tb = np.array([rules[loc]["move"].get(c, 0.0) for c in ctx])
    rows = []
    for n in names_:
        gi = names.index(n); ix = np.nonzero(g == gi)[0]; mids = A[ix][:, 5:7]; nrm = A[ix][:, 7:9]; tree = cKDTree(mids)
        c = IO.ms_contours(n); parts, _ = X.rebuild(c, W, grid=0); full, _ = RS.close_gap(parts, c, W)
        real = E.mask(IO.ms_contours(n, loc)); cells = []
        for how, kk in (("centred", None), ("table", tb[ix]), ("learned", pl[ix])):
            fn = (lambda p: None) if kk is None else (lambda p, kk=kk: side_moves(p, tree, mids, nrm, kk, W) if p["kind"] == "stroke" else solid_move(p, tree, mids, kk))
            ours = E.mask(V.to_contours(V.generate(at_master(full, Wn, fn))))
            im = np.full(real.shape + (3,), 255, np.uint8)
            im[real & ours] = (190, 190, 190); im[real & ~ours] = (30, 90, 220); im[ours & ~real] = (220, 40, 40)
            cells.append((f"{how}", Image.fromarray(im).resize((size, size), Image.LANCZOS)))
        rows.append((f"{n} at {loc}", cells))
    fig05.grid(rows, out, size)
