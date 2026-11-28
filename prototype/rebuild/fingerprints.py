"""Turn the edge measurements (edges.py) into rules and fingerprints.

Rule: every edge moves along its normal by a fixed amount that depends only
on the master and the edge's context (the most common move in Google's font):
  open      the outside edge of the icon, nothing in front of it
  counter   an edge of an enclosed space; split by how big the space is
  facing    an outside edge with other ink in front; split by the gap size
For each master and context, `a` is the most common value in Google's font.

Fingerprints: every edge the rule misses by more than 0.25 px is labelled by
what Google did instead:
  tilt       the edge doesn't stay parallel: the shape itself was redrawn
  thinned    the stroke changes width less than the standard (tight spots)
  thickened  the stroke changes width more than the standard
  moved      the stroke keeps its width change but slides sideways
  held       the edge stays put where the rule moves it (often keeping a gap)
  resize     explained once the whole glyph is scaled or shifted a little
  part       one part (a whole contour) moved or resized as a unit
Contexts also cover caps, solids and thin parts, each with its own move.
Usage: fingerprints.py EDGES.npz OUT.json"""
import sys, json
import numpy as np

TOL, NEAR = 4.0, 10.0   # 0.1 px and 0.25 px at 24 px

def space(f):
    """Empty space in front of a side: open (nothing), or a gap size class."""
    return np.where(f < 0, "open", np.where(f < 80, "tight", "room"))

def context(role, free, thick, L, back, inward):
    """Where an edge sits. A stroke side is described by both sides of its
    stroke: what is in front of it, and what is beyond the far side. That is
    what decides how the width change is split between the two sides."""
    stroke = (thick >= 70) & (thick <= 90)
    cap = (thick > 90) & (L >= 60) & (L <= 100)
    front = np.where((role == 1) & (free >= 0), "counter", space(free))
    side = np.char.add(np.char.add(front.astype(str), "|"), space(back).astype(str))
    # which way the side faces: toward the icon's centre or away from it
    side = np.char.add(side, np.where(inward, " in", " out"))
    # with space on both sides, which side has more room matters
    both = (free >= 0) & (back >= 0)
    rel = np.where(free > 1.3 * back, " more", np.where(back > 1.3 * free, " less", " same"))
    side = np.where(both, np.char.add(side, rel), side)
    return np.where(stroke, side, np.where(cap, "cap", np.where(thick > 90, "solid", "thin")))

def mode(x, w, step=2.0):
    lo, hi = np.percentile(x, 1) - step, np.percentile(x, 99) + step
    h, e = np.histogram(x, bins=np.arange(lo, hi + step, step), weights=w)
    i = int(np.argmax(h)); return round(float((e[i] + e[i + 1]) / 2), 1)

def glyph_fit(k_res, mx, my, nx, ny, L, ok):
    """Glyph-wide resize: k_res ~ s*((m-c).n) + tx*nx + ty*ny. Robust: refit
    after dropping edges that are far off."""
    if ok.sum() < 6: return None
    c = np.array([np.average(mx[ok], weights=L[ok]), np.average(my[ok], weights=L[ok])])
    X = np.stack([(mx - c[0]) * nx + (my - c[1]) * ny, nx, ny], 1)
    m = ok.copy()
    for _ in range(3):
        if m.sum() < 6: return None
        w = np.sqrt(L[m]); p, *_ = np.linalg.lstsq(X[m] * w[:, None], k_res[m] * w, rcond=None)
        r = np.abs(k_res - X @ p); m = ok & (r <= NEAR)
    return p, X @ p

LABELS = ["rule", "near", "resize", "part", "held", "moved", "thinned", "thickened", "tilt"]

def analyse(path):
    Z = np.load(path); A = Z["edges"]; locs = [str(x) for x in Z["locs"]]; names = [str(x) for x in Z["names"]]
    g = A[:, 0].astype(int); L = A[:, 1]; role = A[:, 2]; free = A[:, 3]; thick = A[:, 4]
    mx, my, nx, ny = A[:, 5], A[:, 6], A[:, 7], A[:, 8]
    back = A[:, 33]
    # centre of each glyph = middle of its edges' bounding box
    cx = np.zeros(len(A)); cy = np.zeros(len(A))
    for gi in np.unique(g):
        m = g == gi
        cx[m] = (mx[m].min() + mx[m].max()) / 2; cy[m] = (my[m].min() + my[m].max()) / 2
    inward = (nx * (mx - cx) + ny * (my - cy)) < 0
    ctx = context(role, free, thick, L, back, inward)
    order = np.argsort(g, kind="stable"); gs = g[order]
    bounds = np.searchsorted(gs, np.arange(len(names) + 1))
    rules, label, resize = {}, {}, {}
    for li, loc in enumerate(locs):
        k = A[:, 9 + li]; par = A[:, 15 + li] <= NEAR; th = A[:, 21 + li]; dW = th - thick
        stroke = (thick >= 70) & (thick <= 90)
        DW = float(np.median(dW[stroke & par & (th > 0)]))
        rules[loc] = {"width_change": DW, "move": {}}
        for c in np.unique(ctx):
            m = par & (ctx == c)
            if m.sum() > 50: rules[loc]["move"][str(c)] = mode(k[m], L[m])
        pred = np.array([rules[loc]["move"].get(c, 0.0) for c in ctx])
        err = np.abs(k - pred)
        # glyph-wide resize where it explains much more of the glyph
        gres = np.zeros(len(A)); resize[loc] = {}
        for gi in range(len(names)):
            ix = order[bounds[gi]:bounds[gi + 1]]
            if len(ix) < 6: continue
            f = glyph_fit(k[ix] - pred[ix], mx[ix], my[ix], nx[ix], ny[ix], L[ix], par[ix])
            if f is None: continue
            p, fitted = f
            before = L[ix][err[ix] <= NEAR].sum(); after = L[ix][np.abs(k[ix] - pred[ix] - fitted) <= NEAR].sum()
            if after - before > 0.15 * L[ix].sum():
                gres[ix] = fitted; resize[loc][names[gi]] = [round(float(v), 4) for v in p]
        err2 = np.abs(k - pred - gres)
        lab = np.full(len(A), "rule", dtype=object)
        lab[err > TOL] = "near"
        lab[(err > NEAR) & (err2 <= NEAR)] = "resize"
        off = (err > NEAR) & (err2 > NEAR)
        wdev = dW - DW
        sameW = np.abs(wdev) <= 6
        lab[off & sameW & (np.abs(k) <= TOL)] = "held"
        lab[off & sameW & (np.abs(k) > TOL)] = "moved"
        lab[off & ~sameW & (np.sign(wdev) != np.sign(DW))] = "thinned"
        lab[off & ~sameW & (np.sign(wdev) == np.sign(DW))] = "thickened"
        lab[off & ~stroke] = np.where(np.abs(k[off & ~stroke]) <= TOL, "held", "moved")
        # an edge that bends may still belong to a part that just moved or
        # resized as a whole: fit each contour as offset + slide + scale
        tilt = ~par
        part = np.zeros(len(A), bool)
        cid = A[:, 34]
        for gi in np.unique(g[tilt]):
            for c_ in np.unique(cid[(g == gi) & tilt]):
                m = (g == gi) & (cid == c_)
                if m.sum() < 4: continue
                cx_, cy_ = np.average(mx[m], weights=L[m]), np.average(my[m], weights=L[m])
                X_ = np.stack([np.ones(m.sum()), nx[m], ny[m], (mx[m] - cx_) * nx[m] + (my[m] - cy_) * ny[m]], 1)
                p_, *_ = np.linalg.lstsq(X_, k[m], rcond=None)
                if np.abs(k[m] - X_ @ p_).max() <= NEAR and A[m, 15 + li].max() <= 3 * NEAR:
                    part[m & tilt] = True
        lab[tilt] = "tilt"
        lab[part] = "part"
        label[loc] = lab
        # how often each context ends in each label: lets us predict risk for
        # icons that have no masters at all (Carbon)
        curve = A[:, 35] > 0
        rc = {}
        for c_ in np.unique(ctx):
            for cv in (0, 1):
                m = (ctx == c_) & (curve == cv)
                if L[m].sum() < 2000: continue
                rc[f"{c_}/{'curve' if cv else 'line'}"] = {x: round(float(L[m & (lab == x)].sum() / L[m].sum()), 4) for x in LABELS}
        rules[loc]["context_rates"] = rc
        rules[loc]["coverage"] = {x: round(float(L[lab == x].sum() / L.sum()), 4) for x in LABELS}
        rules[loc]["resized_glyphs"] = len(resize[loc])
    glyphs = []
    for gi, nm in enumerate(names):
        ix = order[bounds[gi]:bounds[gi + 1]]
        if len(ix) == 0: continue
        tl = L[ix].sum(); fp = {}
        for loc in locs:
            lab = label[loc][ix]
            fp[loc] = {x: round(float(L[ix][lab == x].sum() / tl), 3) for x in LABELS if (lab == x).any()}
        miss = np.mean([1 - sum(fp[l].get(x, 0) for x in ("rule", "near", "resize")) for l in locs])
        glyphs.append({"name": nm, "edges": int(len(ix)), "miss": round(float(miss), 3), "fp": fp,
                       "resize": {l: resize[l][nm] for l in locs if nm in resize[l]}})
    glyphs.sort(key=lambda r: -r["miss"])
    return {"rules": rules, "glyphs": glyphs}

if __name__ == "__main__":
    R = analyse(sys.argv[1]); json.dump(R, open(sys.argv[2], "w"))
    for loc, r in R["rules"].items():
        print(loc, f"width {r['width_change']:+.0f}", r["coverage"])
        print("   moves:", r["move"], "resized glyphs", r["resized_glyphs"])
    import statistics as st
    miss = [g["miss"] for g in R["glyphs"]]
    print("glyphs", len(miss), "median miss", st.median(miss), "share with miss<5%", sum(m < 0.05 for m in miss) / len(miss),
          "<10%", sum(m < 0.10 for m in miss) / len(miss), ">30%", sum(m > 0.30 for m in miss) / len(miss))
    print("worst:", [(g["name"], g["miss"]) for g in R["glyphs"][:25]])
