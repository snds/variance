"""Can Google's anchor choice be predicted? (research 06)

Research 04: a per-stroke anchor (which side of a stroke moves when its width
changes) is the biggest lever after the context rule, 12-32% of edges. If a
rule could pick the anchor, those edges would need no per-stroke setting.

Test: learn each edge's move from things the source knows, with no access to
the target master: its context (research 04), where it sits in the icon and in
Google's 20 px live area, which way it faces, the space around it, the size of
its part. A gradient-boosted tree, trained on half the icons and scored on the
other half (split by icon, so it can't memorise an icon). Compared with the
context rule alone.
Scores, on held-out icons:
  edges   share of edge length moving within 0.25 px of Google
  icons   icons with 95%+ of edge length within 0.25 px at this master
Usage: anchor.py EDGES.npz OUT.json"""
import sys, json
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
import fingerprints as FP

LOCS = ["w100", "w700", "o20", "o48", "g200", "gm50"]
NEAR = 10

def features(A):
    g = A[:, 0].astype(int); L = A[:, 1]; role = A[:, 2]; free = A[:, 3]; thick = A[:, 4]
    x, y, nx, ny = A[:, 5], A[:, 6], A[:, 7], A[:, 8]; back = A[:, 33]; cid = A[:, 34]; curve = A[:, 35]
    # per glyph and per contour: bounding box
    gx0 = np.zeros(len(A)); gx1 = np.zeros(len(A)); gy0 = np.zeros(len(A)); gy1 = np.zeros(len(A))
    csz = np.zeros(len(A))
    order = np.lexsort((cid, g)); key = g[order] * 10000 + cid[order].astype(int)
    for gi in np.unique(g):
        m = g == gi
        gx0[m], gx1[m], gy0[m], gy1[m] = x[m].min(), x[m].max(), y[m].min(), y[m].max()
    _, start = np.unique(key, return_index=True)
    bounds = list(start) + [len(order)]
    for a, b in zip(bounds[:-1], bounds[1:]):
        ix = order[a:b]; csz[ix] = max(np.ptp(x[ix]), np.ptp(y[ix]))
    cx, cy = (gx0 + gx1) / 2, (gy0 + gy1) / 2
    inward = (nx * (x - cx) + ny * (y - cy)) < 0
    out = lambda lo, hi, v, n: (hi - v) * np.maximum(n, 0) + (v - lo) * np.maximum(-n, 0)
    to_bbox = out(gx0, gx1, x, nx) + out(gy0, gy1, y, ny)          # how far the glyph's box is in front
    to_live = out(80, 880, x, nx) + out(80, 880, y, ny)            # Google's 20 px live area (2 px padding)
    ctx = FP.context(role, free, thick, L, back, inward)
    codes = {c: i for i, c in enumerate(np.unique(ctx))}
    X = np.stack([np.vectorize(codes.get)(ctx), role, free, thick, back, inward, curve, L, nx, ny,
                  x - cx, y - cy, to_bbox, to_live, csz, gx1 - gx0, gy1 - gy0], 1)
    return X, ctx, g, L

def icons_ok(g, L, hit):
    tot = np.bincount(g, weights=L); ok = np.bincount(g, weights=L * hit)
    m = tot > 0
    return float((ok[m] >= 0.95 * tot[m]).mean())

def main(path, out):
    Z = np.load(path); A = Z["edges"]
    X, ctx, g, L = features(A)
    rules = json.load(open(__file__.replace("anchor.py", "material-rules.json")))
    rng = np.random.RandomState(7); half = rng.rand(g.max() + 1) < 0.5
    test = half[g]; res = {}
    for li, loc in enumerate(LOCS):
        k = A[:, 9 + li]; par = A[:, 15 + li] <= NEAR
        rule = np.array([rules[loc]["move"].get(c, 0.0) for c in ctx])
        m = HistGradientBoostingRegressor(loss="absolute_error", max_iter=300, learning_rate=0.1, max_leaf_nodes=63,
                                          categorical_features=[0], random_state=7)
        tr = ~test & par
        m.fit(X[tr], k[tr], sample_weight=L[tr])
        pred = m.predict(X)
        r = {}
        for name, p in (("rule", rule), ("learned", pred)):
            hit = par & (np.abs(k - p) <= NEAR)
            r[name] = {"edges": round(float(L[test & hit].sum() / L[test].sum()), 4),
                       "parallel_edges": round(float(L[test & hit].sum() / L[test & par].sum()), 4),
                       "icons": round(icons_ok(g[test], L[test], hit[test]), 4)}
        res[loc] = r
        print(loc, r, flush=True)
    json.dump(res, open(out, "w"), indent=1)

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
