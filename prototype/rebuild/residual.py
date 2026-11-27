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

def _patch(kind, diff, W, report):
    d = " ".join(X.d_of_contour(c, nd=6) for c in V.to_contours(diff))
    m = X.mask_of(diff); lab, n = ndi.label(m)
    dist = ndi.distance_transform_edt(m)
    for k in range(1, n + 1):
        px = lab == k; ar = float(px.sum())
        if ar < 4: continue
        t = 2 * float(dist[px].max())
        report.append({"op": kind, "area": ar, "thick": t, "type": "detail" if t > 0.5 * W else "sliver"})
    thick = max((r["thick"] for r in report if r["op"] == kind), default=0)
    return {"id": f"patch_{kind}", "kind": "solid", "d": d,
            "role": {"knockout": True} if kind == "remove" else None,
            "patch": {"op": kind, "area": area(diff), "type": "detail" if thick > 0.5 * W else "sliver"}}

def _vector_diffs(parts, orig, quant):
    """Patches from Skia booleans. quant: None = exact inputs, else inputs
    rounded to that grid first (a different rounding often gets Skia past a
    near-coincident edge it can't resolve)."""
    gen = V.generate(parts)
    a0, b0 = (gen, orig) if quant is None else (V._rounded(gen, quant), V._rounded(orig, quant))
    out = {}
    for kind, a, b in (("remove", a0, b0), ("add", b0, a0)):
        try: out[kind] = pathops.op(a, b, pathops.PathOp.DIFFERENCE)
        except pathops.PathOpsError: return None
    return out

def _traced_diffs(parts, orig):
    """Patches traced from the pixel difference at 960 px (1 unit). The
    outline follows pixel edges, so it is exact to well under 1/20 px; used
    only when every boolean attempt fails."""
    from skimage import measure
    gm, om = X.mask_of(V.generate(parts)), X.mask_of(orig)
    out = {}
    for kind, m in (("remove", gm & ~om), ("add", om & ~gm)):
        p = pathops.Path(); pen = p.getPen()
        for c in measure.find_contours(np.pad(m, 1).astype(float), 0.5):
            pts = [(x - 0.5, X.RES - (y - 0.5)) for y, x in c]   # (row, col) -> y-up units
            if len(pts) < 3: continue
            pen.moveTo(pts[0])
            for q in pts[1:]: pen.lineTo(q)
            pen.closePath()
        p.fillType = pathops.FillType.EVEN_ODD
        try: p.simplify()
        except pathops.PathOpsError: pass
        out[kind] = p
    return out

def close_gap(parts, orig_contours, W):
    """Returns the source with one `remove` patch and one `add` patch (each may
    hold many pieces), plus a per-piece report. Pieces are kept together in
    one path so Skia's own winding decides holes; splitting them by hand is
    where exactness gets lost.

    Skia sometimes returns a wrong difference when two outlines share nearly
    coincident edges (research 05: 21 of 500 icons). So several ways of
    building the patches are tried, and the one that scores best against the
    original wins: exact booleans, booleans on inputs rounded to 1/16, 1/4 and
    1 unit, and as a last resort a patch traced from the pixel difference.
    A patch that makes things worse is never kept."""
    orig = X.contours_to_path(orig_contours)
    om = X.mask_of(orig)
    base = X.score(V.generate(parts), om)
    best = (base[1], base[0], parts, [])
    names = ["exact", "round 1/16", "round 1/4", "round 1", "traced"]
    tries = [lambda q=q: _vector_diffs(parts, orig, q) for q in (None, 1 / 16, 1 / 4, 1)]
    tries.append(lambda: _traced_diffs(parts, orig))
    for i, make in enumerate(tries):
        try: diffs = make()
        except Exception: diffs = None
        if diffs is None: continue
        report, out = [], []
        for kind in ("remove", "add"):
            if area(diffs[kind]) < 4: continue
            out.append(_patch(kind, diffs[kind], W, report)); out[-1]["patch"]["via"] = names[i]
        try: s = X.score(V.generate(parts + out), om)
        except Exception: continue
        if (s[1], s[0]) < best[:2]: best = (s[1], s[0], parts + out, report)
        if best[0] == 0 and i < len(tries) - 1: break   # exact: stop (traced patch only as a last resort)
    return best[2], best[3]
