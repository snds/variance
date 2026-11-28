"""Fit to a drawing: turn a hand-drawn master into settings on the source.

For every stroke segment, look along the centre-line's normal on each side
and measure where the drawing's edge is. The median of those distances
becomes that segment's left and right setting at the drawing's weight. Open
ends are measured the same way along the stroke. The drawing itself is kept
only as a reference for scoring (docs/design/app-flows.md, "Fit to a drawing").
"""
import math
import numpy as np
from . import geom, raster as R, model as M

SAMPLES = (0.2, 0.35, 0.5, 0.65, 0.8)

def _ray(mask, p, d, limit, res=R.RES):
    """Distance (units) from p along d to the first pixel outside the ink,
    or None if p itself isn't on ink."""
    s = 960.0 / res
    def ink(q):
        c, r = int(q[0] / s), int(q[1] / s)
        return 0 <= r < res and 0 <= c < res and mask[r, c]
    if not ink(p): return None
    t = 0.0
    while t < limit:
        t += 1.0
        if not ink((p[0] + d[0] * t, p[1] + d[1] * t)): return t
    return None

def fit(icon, style, wght, ref_polys):
    """Settings that make `icon` at `wght` match the drawing. Returns
    (sides, ends): {part: {"c.s": [left, right]}}, {part: {c: [start, end]}}."""
    m = R.mask(ref_polys)
    sides, ends = {}, {}
    for part in icon.parts:
        if part["kind"] != "stroke": continue
        W = icon.width(part, wght); lim = max(3 * W, 120)
        for ci, (segs, closed, dot) in enumerate(icon.sk[part["id"]]):
            if not segs: continue
            for si, s in enumerate(segs):
                L, Rr = [], []
                for t in SAMPLES:
                    p = geom.bez(s, t); nl = geom.left_of(geom.tangent(s, t))
                    a = _ray(m, p, nl, lim); b = _ray(m, p, (-nl[0], -nl[1]), lim)
                    if a is not None and b is not None: L.append(a); Rr.append(b)
                if len(L) >= 2:
                    l, r = float(np.median(L)), float(np.median(Rr))
                    # a side that runs into a neighbouring part reads too far;
                    # cap it at twice the rule's half width
                    l, r = min(l, W * 1.25), min(r, W * 1.25)
                    sides.setdefault(part["id"], {})[f"{ci}.{si}"] = [round(l, 1), round(r, 1)]
            if not closed and part.get("cap") in ("butt", "square", "round"):
                base = W / 2 if part["cap"] in ("square", "round") else 0.0
                e = []
                for end, (seg, t, sign) in enumerate([(segs[0], 0.0, -1), (segs[-1], 1.0, 1)]):
                    p = geom.bez(seg, t); tg = geom.tangent(seg, t); d = (tg[0] * sign, tg[1] * sign)
                    x = _ray(m, p, d, lim)
                    e.append(round(max(-W, min(W, x - base)), 1) if x is not None else 0.0)
                if any(abs(v) > 2 for v in e):
                    ends.setdefault(part["id"], {})[str(ci)] = e
    return sides, ends

def apply(settings, sides, ends, wght, by="fit"):
    """Write a fit into settings as Manual amounts tagged with where they came from."""
    wk = M.wkey(wght)
    st = settings.setdefault("sides", {})
    for pid, segs in sides.items():
        for key, lr in segs.items():
            ent = st.setdefault(pid, {}).setdefault(key, {})
            ent.setdefault("amount", {})[wk] = lr; ent["by"] = by
    en = settings.setdefault("ends", {})
    for pid, cs in ends.items():
        for ci, se in cs.items():
            en.setdefault(pid, {}).setdefault(ci, {})[wk] = se
    return settings

def score(icon, style, wght, ref_polys, fill=0):
    ours = R.mask([c for c, _ in icon.outline({"wght": wght, "FILL": fill}, style)])
    return R.edge_score(ours, R.mask(ref_polys))
