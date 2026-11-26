"""Nonzero-winding rasterizer (what font renderers do), plus comparison helpers.
Samples pixel centres on the 960 grid at a chosen resolution."""
import numpy as np

def flatten(contours, steps=16):
    """Contours of cubics -> list of (N,2) polylines."""
    t = np.linspace(0, 1, steps, endpoint=False)[:, None]
    polys = []
    for c in contours:
        pts = []
        for p0, c1, c2, p3 in c:
            p0, c1, c2, p3 = map(np.array, (p0, c1, c2, p3))
            mt = 1 - t
            pts.append(mt**3*p0 + 3*mt*mt*t*c1 + 3*mt*t*t*c2 + t**3*p3)
        if pts: polys.append(np.vstack(pts))
    return polys

def raster(contours, res=480, steps=16):
    """Boolean mask res x res; row 0 = top (y=960)."""
    polys = flatten(contours, steps)
    if not polys: return np.zeros((res, res), bool)
    A = np.vstack([p for p in polys]); B = np.vstack([np.roll(p, -1, axis=0) for p in polys])
    x0, y0, x1, y1 = A[:, 0], A[:, 1], B[:, 0], B[:, 1]
    s = 960.0 / res
    ys = 960 - (np.arange(res) + 0.5) * s
    xs = (np.arange(res) + 0.5) * s
    mask = np.zeros((res, res), bool)
    for r, y in enumerate(ys):
        up = (y0 <= y) & (y1 > y); dn = (y0 > y) & (y1 <= y)
        sel = up | dn
        if not sel.any(): continue
        xi = x0[sel] + (y - y0[sel]) * (x1[sel] - x0[sel]) / (y1[sel] - y0[sel])
        wd = np.where(up[sel], 1, -1)
        o = np.argsort(xi); xi, wd = xi[o], wd[o]
        wn = np.cumsum(wd)
        # spans where winding != 0 between consecutive crossings
        for k in range(len(xi) - 1):
            if wn[k] != 0:
                mask[r, (xs >= xi[k]) & (xs < xi[k+1])] = True
    return mask

def diff_px2(a, b, res):
    """Area (px^2 at 24 px) where two masks disagree."""
    unit = 960.0 / res / 40.0
    return float(np.count_nonzero(a != b)) * unit * unit
