"""Predict which icons will need hand work, from their default drawing alone.

Material taught us, for every edge context (what's in front of a stroke side,
what's behind the stroke, whether it faces the icon's centre, line or curve),
how often Google reshaped that edge, moved its anchor, or changed its width.
Any icon set can be cut into the same edge contexts, so the same rates give a
predicted share of hand work per icon, even for sets with a single master.

  material   check the prediction against what Google actually did
  carbon     edges for every Carbon icon, scaled so its stroke matches Material's
Usage: risk.py FP.json TIERS.json EDGES.npz OUT.json"""
import sys, json, math
import numpy as np
import icons_io as IO, extract as X
from refine import Outline
import fingerprints as F

LOCS = ["w100", "w700", "o20", "o48", "g200", "gm50"]
GROUP = {"reshape": ["tilt"], "anchor": ["moved", "held"], "width": ["thinned", "thickened"],
         "resize": ["resize", "part"], "auto": ["rule", "near"]}

def predict(rules, ctx, curve, L):
    out = {}
    for grp, labs in GROUP.items():
        vals = []
        for loc in LOCS:
            rc = rules[loc]["context_rates"]
            r = np.array([sum(rc.get(f"{c}/{'curve' if cv else 'line'}", rc.get(f"{c}/line", {})).get(x, np.nan) for x in labs)
                          for c, cv in zip(ctx, curve)], float)
            ok = ~np.isnan(r)
            vals.append(float(np.sum(L[ok] * r[ok]) / max(L[ok].sum(), 1e-9)))
        out[grp] = round(float(np.mean(vals)), 4)
    return out

def spearman(a, b):
    ra = np.argsort(np.argsort(a)); rb = np.argsort(np.argsort(b)); return float(np.corrcoef(ra, rb)[0, 1])

# ---------- edge features from plain outlines (any icon set)
def bez(seg, t):
    p0, p1, p2, p3 = map(np.array, seg); mt = 1 - t
    return mt**3 * p0 + 3 * mt * mt * t * p1 + 3 * mt * t * t * p2 + t**3 * p3
def dbez(seg, t):
    p0, p1, p2, p3 = map(np.array, seg); mt = 1 - t
    return 3 * mt * mt * (p1 - p0) + 6 * mt * t * (p2 - p1) + 3 * t * t * (p3 - p2)

def outline_edges(contours, scale):
    """Edges with the same columns fingerprints.context needs."""
    path = X.contours_to_path(contours)
    comps = X.components(path)
    cs = []
    for o, holes in comps:
        cs.append((o, 0)); cs += [(h, 1) for h in holes]
    flat = [c for c, _ in cs]
    out = Outline(flat); rows = []
    for c, role in cs:
        P = np.array([s[0] for s in c]); x, y = P[:, 0], P[:, 1]
        ccw = np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y) > 0
        # away-from-ink normal: outer contours want ink on the left when ccw
        sgn = -1 if (ccw and role == 0) or (not ccw and role == 1) else 1
        for seg in c:
            m = bez(seg, 0.5); t = dbez(seg, 0.5); tl = math.hypot(*t)
            chord = math.dist(seg[0], seg[3])
            if chord * scale < 8 or tl == 0: continue
            n = sgn * np.array([-t[1], t[0]]) / tl
            free = out.ray(m + 0.5 * n, n, 4000); thick = out.ray(m - 0.5 * n, -n, 4000)
            back = out.ray(m - (thick + 0.5) * n, -n, 4000) if thick is not None else None
            cr = lambda a, b: abs(a[0] * b[1] - a[1] * b[0])
            d1, d2, d3 = np.subtract(seg[1], seg[0]), np.subtract(seg[2], seg[0]), np.subtract(seg[3], seg[0])
            curve = cr(d1, d3) > 1e-3 * chord * chord or cr(d2, d3) > 1e-3 * chord * chord
            f = lambda v: -1 if v is None else v * scale
            rows.append([chord * scale, role, f(free), f(thick), f(back), m[0], m[1], n[0], n[1], int(curve)])
    return np.array(rows, float)

def contexts(E):
    L, role, free, thick, back, mx, my, nx, ny, curve = E.T
    cx = (mx.min() + mx.max()) / 2; cy = (my.min() + my.max()) / 2
    inward = (nx * (mx - cx) + ny * (my - cy)) < 0
    return F.context(role, free, thick, L, back, inward), curve, L

if __name__ == "__main__":
    fp = json.load(open(sys.argv[1])); rules = fp["rules"]
    tiers = {g["name"]: g for g in json.load(open(sys.argv[2]))["glyphs"]}
    # 1. check on Material: predicted vs actual, per glyph
    Z = np.load(sys.argv[3]); A = Z["edges"]; names = [str(x) for x in Z["names"]]
    g = A[:, 0].astype(int); mx, my = A[:, 5], A[:, 6]
    cx = np.zeros(len(A)); cy = np.zeros(len(A))
    for gi in np.unique(g):
        m = g == gi; cx[m] = (mx[m].min() + mx[m].max()) / 2; cy[m] = (my[m].min() + my[m].max()) / 2
    inward = (A[:, 7] * (mx - cx) + A[:, 8] * (my - cy)) < 0
    ctx = F.context(A[:, 2], A[:, 3], A[:, 4], A[:, 1], A[:, 33], inward)
    pred, act = [], []
    for gi in np.unique(g):
        m = g == gi; nm = names[gi]
        if nm not in tiers: continue
        p = predict(rules, ctx[m], A[m, 35], A[m, 1])
        t = tiers[nm]["tiers"]
        pred.append([p["reshape"], 1 - p["auto"]]); act.append([np.mean([t[l]["redraw"] for l in LOCS]), np.mean([1 - t[l]["auto"] for l in LOCS])])
    pred = np.array(pred); act = np.array(act)
    check = {"reshape_spearman": round(spearman(pred[:, 0], act[:, 0]), 3), "handwork_spearman": round(spearman(pred[:, 1], act[:, 1]), 3)}
    # top-decile hit rate: of the 10% we predict worst, how many are in the actual worst 10%?
    k = len(pred) // 10
    for i, key in enumerate(["reshape", "handwork"]):
        top_p = set(np.argsort(-pred[:, i])[:k]); top_a = set(np.argsort(-act[:, i])[:k])
        check[key + "_top10_overlap"] = round(len(top_p & top_a) / k, 3)
    print("Material check:", check)
    # 2. Carbon
    scale = 80 / 60
    car = []
    for nm in IO.carbon_names():
        try:
            E = outline_edges(IO.carbon_contours(nm), scale)
            if len(E) == 0: continue
            c, cv, L = contexts(E)
            p = predict(rules, c, cv, L)
            car.append({"name": nm, "edges": int(len(E)), **p, "handwork": round(1 - p["auto"], 4)})
        except Exception as ex:
            print("FAIL", nm, ex)
    car.sort(key=lambda r: -r["reshape"])
    json.dump({"material_check": check, "carbon": car}, open(sys.argv[4], "w"))
    print(len(car), "carbon icons")
    print("reshape top:", [(r["name"], r["reshape"]) for r in car[:20]])
    print("handwork top:", [(r["name"], r["handwork"]) for r in sorted(car, key=lambda r: -r["handwork"])[:20]])
