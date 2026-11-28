"""Nonzero rasterizing and edge scores, on the 960 grid (y down)."""
import numpy as np
import pathops
from fontTools.svgLib.path.parser import parse_path
from scipy import ndimage as ndi
from . import geom, source as S

RES = 480   # 2 units per pixel; 0.25 px at 24 px = 10 units = 5 pixels here

def mask(polys, res=RES):
    """Nonzero-winding fill of point contours. Row 0 = top (y = 0)."""
    m = np.zeros((res, res), bool)
    polys = [np.asarray(p, float) for p in polys if len(p) >= 3]
    if not polys: return m
    A = np.vstack(polys); B = np.vstack([np.roll(p, -1, axis=0) for p in polys])
    s = 960.0 / res
    ys = (np.arange(res) + 0.5) * s; xs = (np.arange(res) + 0.5) * s
    x0, y0, x1, y1 = A[:, 0], A[:, 1], B[:, 0], B[:, 1]
    for r, y in enumerate(ys):
        up = (y0 <= y) & (y1 > y); dn = (y0 > y) & (y1 <= y); sel = up | dn
        if not sel.any(): continue
        xi = x0[sel] + (y - y0[sel]) * (x1[sel] - x0[sel]) / (y1[sel] - y0[sel])
        wd = np.where(up[sel], 1, -1)
        o = np.argsort(xi); xi, wd = xi[o], wd[o]
        acc = np.cumsum(wd)
        for i in range(len(xi) - 1):
            if acc[i] != 0:
                c0 = int(np.ceil(xi[i] / s - 0.5)); c1 = int(np.floor(xi[i + 1] / s - 0.5))
                if c1 >= c0: m[r, max(c0, 0):min(c1 + 1, res)] = True
    return m

def edges(m):
    return m & ~ndi.binary_erosion(m)

def edge_score(ours, ref, tol_units=10, res=RES):
    """Share of the reference's edge pixels within tol of one of ours
    (research 04-08's measure: 0.25 px at 24 px = 10 units)."""
    er, eo = edges(ref), edges(ours)
    if not er.any(): return None
    d = ndi.distance_transform_edt(~eo) * (960.0 / res)
    return float((d[er] <= tol_units).mean())

def drawing_polys(svg_text):
    """Any SVG drawing (strokes or fills) outlined to point contours, for
    references. Uses Skia's stroker: references are only scored against,
    never interpolated, so their structure doesn't matter."""
    parts, _ = S.read_svg(svg_text)
    ink = pathops.Path()
    CAP = {"butt": pathops.LineCap.BUTT_CAP, "round": pathops.LineCap.ROUND_CAP, "square": pathops.LineCap.SQUARE_CAP}
    JOIN = {"miter": pathops.LineJoin.MITER_JOIN, "round": pathops.LineJoin.ROUND_JOIN, "bevel": pathops.LineJoin.BEVEL_JOIN}
    for p in parts:
        q = pathops.Path(); parse_path(p["d"], q.getPen())
        if p["kind"] == "stroke":
            q.stroke(p["width"], CAP[p["cap"]], JOIN[p["join"]], 4)
        q.convertConicsToQuads()
        if (p.get("role") or {}).get("knockout"):
            ink = pathops.op(ink, q, pathops.PathOp.DIFFERENCE)
        else:
            ink = pathops.op(ink, q, pathops.PathOp.UNION)
    pen = geom._Pen(); ink.draw(pen); pen._flush(False)
    polys = []
    for segs in pen.contours:
        pts = []
        for s in segs:
            n = geom.steps_of(s)
            pts.extend(geom.bez(s, k / n) for k in range(n))
        if len(pts) >= 3: polys.append(pts)
    return polys
