"""Edge-move fingerprints for ANY pair of icon styles, from pixels alone.

Research 04 tracked Material's edges point by point, which only works when two
masters are point-compatible. Most icon sets are not: Phosphor's weights,
Fluent's sizes and every outline/filled pair were drawn separately. This
module measures the same thing from the two images instead:

  For every boundary pixel of style A, how far did that piece of edge move,
  along its own normal, to reach style B's edge?  (signed: + = grew)

It then reads the same context research 04 used (what is in front of the
edge, how thick the ink behind it is, what is beyond the far side, does it
face the icon's centre) so the result can be compared with Material's rules
and labelled with the same tiers:

  rule    the context's usual move explains it (within 0.25 px)
  resize  the whole icon, or one part of it, moved or scaled
  anchor  the stroke kept its new width but chose another side to grow from
  width   the stroke grew more or less than usual (crowding, emphasis)
  reshape none of the above: redrawn

Resolution 480 px over the 960 grid (1 px = 2 units, 1/20 px at 24 px)."""
import numpy as np
from scipy import ndimage as ndi
import raster as R
import fingerprints as FP

RES = 480; U = 960 / RES
NEAR = 10            # 0.25 px at 24 px, same tolerance as research 04
MAXT = RES

def mask(contours): return R.raster(contours, RES)

def sdf(M):
    """Signed distance in px, + inside. A boundary pixel sits 0.5 px in."""
    return np.where(M, ndi.distance_transform_edt(M) - 0.5, -(ndi.distance_transform_edt(~M) - 0.5))

def _ray(M, r, c, dr, dc):
    """Sample M along rays from (r, c) in direction (dr, dc), steps 1..MAXT.
    Returns ink (N, T) and inside-canvas (N, T)."""
    t = np.arange(1, MAXT + 1)[None, :]
    rr = np.rint(r[:, None] + dr[:, None] * t).astype(int)
    cc = np.rint(c[:, None] + dc[:, None] * t).astype(int)
    inb = (rr >= 0) & (rr < RES) & (cc >= 0) & (cc < RES)
    ink = np.zeros(rr.shape, bool)
    ink[inb] = M[rr[inb], cc[inb]]
    return ink, inb, rr, cc

def _first(b):
    """Index of first True per row, or -1."""
    i = np.argmax(b, 1); return np.where(b[np.arange(len(b)), i], i, -1)

def features(A, W, chunk=1500):
    """Boundary pixels of mask A with their normal and context features."""
    edge = A & ~ndi.binary_erosion(A)
    r, c = np.nonzero(edge)
    s = ndi.gaussian_filter(sdf(A), 1.2)
    gr, gc = np.gradient(s)
    nr, nc = -gr[r, c], -gc[r, c]                     # outward normal (row, col)
    ln = np.hypot(nr, nc); ok = ln > 1e-6
    nr, nc = np.where(ok, nr / np.maximum(ln, 1e-9), 0), np.where(ok, nc / np.maximum(ln, 1e-9), 0)
    bg, _ = ndi.label(~A)
    border = set(np.unique(np.concatenate([bg[0], bg[-1], bg[:, 0], bg[:, -1]]))) - {0}
    out = {k: np.zeros(len(r)) for k in ("free", "thick", "back", "counter", "far_r", "far_c")}
    for a in range(0, len(r), chunk):
        sl = slice(a, a + chunk)
        R_, C_, NR, NC = r[sl], c[sl], nr[sl], nc[sl]
        # outward: leave the ink, then find the next ink
        ink, inb, rr, cc = _ray(A, R_, C_, NR, NC)
        t0 = _first(~ink)
        after = ink & (np.arange(MAXT)[None, :] > t0[:, None])
        t2 = _first(after)
        out["free"][sl] = np.where(t2 >= 0, (t2 - t0) * U, -1)
        lab = bg[np.clip(rr[np.arange(len(R_)), np.maximum(t0, 0)], 0, RES - 1), np.clip(cc[np.arange(len(R_)), np.maximum(t0, 0)], 0, RES - 1)]
        out["counter"][sl] = np.array([(l != 0 and l not in border) for l in lab], float)
        # inward: thickness of the ink behind, then the space beyond it
        ink, inb, rr, cc = _ray(A, R_, C_, -NR, -NC)
        t1 = _first(~ink)
        t1 = np.where(t1 >= 0, t1, MAXT - 1)
        out["thick"][sl] = (t1 + 1) * U
        last = np.maximum(t1 - 1, 0)
        out["far_r"][sl] = rr[np.arange(len(R_)), last]; out["far_c"][sl] = cc[np.arange(len(R_)), last]
        beyond = ink & (np.arange(MAXT)[None, :] > t1[:, None])
        t3 = _first(beyond)
        out["back"][sl] = np.where(t3 >= 0, (t3 - t1) * U, -1)
    # context with Material's thresholds, after scaling this set's stroke to 80 units
    k = 80.0 / W
    cr, cc_ = (r.min() + r.max()) / 2, (c.min() + c.max()) / 2
    inward = (nr * (r - cr) + nc * (c - cc_)) < 0
    sc = lambda v: np.where(v < 0, v, v * k)
    ctx = FP.context(out["counter"].astype(int), sc(out["free"]), out["thick"] * k, np.zeros(len(r)), sc(out["back"]), inward)
    ctx = np.where(ctx == "cap", "solid", ctx)      # no edge lengths here; ends read as solid
    comp, _ = ndi.label(A)
    return dict(r=r, c=c, nr=nr, nc=nc, ctx=ctx, comp=comp[r, c], **out)

def moves(F, B):
    """Signed move (units) of each boundary pixel of A to reach B's edge, for
    the pixel itself and for the far side of the stroke behind it."""
    sB = sdf(B)
    k = (sB[F["r"], F["c"]] - 0.5) * U
    fr, fc = F["far_r"].astype(int), F["far_c"].astype(int)
    kf = (sB[fr, fc] - 0.5) * U
    return k, kf

def stroke_width(M):
    """Typical stroke width (units): 2 x distance on the medial ridge."""
    from skimage.morphology import skeletonize
    d = ndi.distance_transform_edt(M); sk = skeletonize(M)
    v = 2 * d[sk] * U
    return float(np.median(v)) if len(v) else 0.0

def fit(res, F, sel, ok):
    """Robust fit res ~ g + tx*n_x + ty*n_y + s*((p-c).n) over pixels `sel`."""
    if ok[sel].sum() < 12: return None
    x, y = F["c"][sel] * U, (RES - F["r"][sel]) * U
    nx, ny = F["nc"][sel], -F["nr"][sel]
    cx, cy = x.mean(), y.mean()
    X = np.stack([np.ones(sel.sum()), nx, ny, (x - cx) * nx + (y - cy) * ny], 1)
    m = ok[sel].copy(); yv = res[sel]
    for _ in range(3):
        if m.sum() < 12: return None
        p, *_ = np.linalg.lstsq(X[m], yv[m], rcond=None)
        m = ok[sel] & (np.abs(yv - X @ p) <= NEAR)
    return X @ p

def label(F, k, kf, rule, dW):
    """Tier per boundary pixel, given the rule (context -> move) and the
    pair's typical stroke width change dW."""
    pred = np.array([rule.get(c, dW / 2) for c in F["ctx"]])
    err = np.abs(k - pred)
    lab = np.full(len(k), "reshape", dtype=object)
    lab[err <= NEAR] = "rule"
    res = k - pred; ok = np.ones(len(k), bool)
    # whole icon first, then each connected part
    best = np.zeros(len(k), bool)
    allsel = np.ones(len(k), bool)
    g = fit(res, F, allsel, ok)
    if g is not None:
        hit = np.abs(res - g) <= NEAR
        if hit.sum() - (err <= NEAR).sum() > 0.15 * len(k): best |= hit
    for ci in np.unique(F["comp"]):
        sel = F["comp"] == ci
        p = fit(res, F, sel, ok)
        if p is None: continue
        hit = np.zeros(len(k), bool); hit[sel] = np.abs(res[sel] - p) <= NEAR
        if hit.sum() - ((err <= NEAR) & sel).sum() > 0.15 * sel.sum(): best |= hit
    lab[(lab != "rule") & best] = "resize"
    stroke = ~np.isin(F["ctx"], ["solid", "thin"])
    w = k + kf                                      # this stroke's width change
    rest = lab == "reshape"
    sameW = np.abs(w - dW) <= NEAR
    lab[rest & stroke & sameW] = "anchor"
    lab[rest & stroke & ~sameW & (np.abs(w - dW) <= 4 * NEAR)] = "width"
    # solid and thin areas: no stroke to re-anchor; a uniform move is anchor-like
    lab[rest & ~stroke & (np.abs(k) <= NEAR)] = "anchor"
    return lab, pred

def own_rule(ctx, k, min_n=200):
    out = {}
    for c in np.unique(ctx):
        m = ctx == c
        if m.sum() >= min_n: out[str(c)] = FP.mode(k[m], np.ones(m.sum()))
    return out

TIERS = ["rule", "resize", "anchor", "width", "reshape"]

def pair_features(cA, cB, W):
    A, B = mask(cA), mask(cB)
    if A.sum() == 0 or B.sum() == 0: return None
    F = features(A, W); k, kf = moves(F, B)
    return F, k, kf, stroke_width(A), stroke_width(B)
