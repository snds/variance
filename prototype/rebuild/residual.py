"""Close the gap between a fitted Variance source and the original.

After strokes, solids, cuts and knockouts are fitted, whatever still differs
is added as explicit parts, so the default style matches exactly:
  - ink the source misses  -> `solid` parts      (role: patch)
  - ink the source adds    -> `knockout` parts   (role: patch)
Each patch is labelled by thickness:
  - detail : thicker than half a stroke. A real design part the stroke model
             didn't pick up (a bell's clapper, a rounded tip). It should be a
             proper solid in the source.
  - sliver : thinner than that. Fitting tolerance along an edge.
The share of ink still owned by rules is what varies cleanly with weight."""
import numpy as np, pathops
from scipy import ndimage as ndi
from fontTools.pens.areaPen import AreaPen
import source as V, extract as X

def area(p):
    pen = AreaPen(); p.draw(pen); return abs(pen.value)

def split(path):
    """One pathops path per outer contour (holes kept with their outer)."""
    out = []
    for o, holes in X.components(path):
        out.append((X.contours_to_path([o] + holes), o, holes))
    return out

def thickness(p):
    m = X.mask_of(p)
    if not m.any(): return 0.0
    return 2 * float(ndi.distance_transform_edt(m).max())

def close_gap(parts, orig_contours, W):
    """Returns the source with one `remove` patch and one `add` patch (each may
    hold many pieces), plus a per-piece report. Pieces are kept together in
    one path so Skia's own winding decides holes; splitting them by hand is
    where exactness gets lost."""
    orig = X.contours_to_path(orig_contours)
    gen = V.generate(parts)
    out, report = [], []
    for kind, a, b in (("remove", gen, orig), ("add", orig, gen)):
        try: diff = V.op(a, b, pathops.PathOp.DIFFERENCE)
        except pathops.PathOpsError: continue
        if area(diff) < 4: continue
        d = " ".join(X.d_of_contour(c, nd=6) for c in V.to_contours(diff))
        m = X.mask_of(diff); lab, n = ndi.label(m)
        dist = ndi.distance_transform_edt(m)
        for k in range(1, n + 1):
            px = lab == k; ar = float(px.sum())
            if ar < 4: continue
            t = 2 * float(dist[px].max())
            report.append({"op": kind, "area": ar, "thick": t, "type": "detail" if t > 0.5 * W else "sliver"})
        thick = max((r["thick"] for r in report if r["op"] == kind), default=0)
        out.append({"id": f"patch_{kind}", "kind": "solid", "d": d,
                    "role": {"knockout": True} if kind == "remove" else None,
                    "patch": {"op": kind, "area": area(diff), "type": "detail" if thick > 0.5 * W else "sliver"}})
    return parts + out, report
