"""Rebuild an outlined icon as a Variance source: skeleton strokes, solids,
knockouts and cut rules. Then check it against the original.

Steps
  1. Split the original into ink components. A component mostly made of
     stroke-width ink becomes strokes; anything else becomes a solid.
  2. Strokes: medial axis of the ink -> prune corner spurs -> chain branches
     through junctions -> fit lines and circular arcs -> snap to the grid.
  3. Holes inside solids that are stroke-like become knockout strokes.
  4. Try cut rules (gap size, side) on each stroke that crosses another, and
     keep any that bring the result closer to the original.
"""
import math, itertools
import numpy as np
import pathops
from skimage.morphology import medial_axis
from scipy import ndimage as ndi
from skan import Skeleton, summarize
import raster as R
import source as V

RES = 960  # 1 raster px = 1 unit

# ---------------------------------------------------------------- helpers
def contours_to_path(contours):
    p = pathops.Path(); pen = p.getPen()
    for c in contours:
        pen.moveTo(c[0][0])
        for s in c: pen.curveTo(s[1], s[2], s[3])
        pen.closePath()
    p.fillType = pathops.FillType.WINDING; p.simplify(); return p

def mask_of(path): return R.raster(V.to_contours(path), RES, steps=12)

def score(gen_path, orig_mask):
    m = mask_of(gen_path); x = m != orig_mask
    # differences thicker than 2 units survive a 1-px erosion each way
    core = ndi.binary_erosion(x, iterations=1)
    return float(np.count_nonzero(x)) / 1600.0, int(np.count_nonzero(core))

def px_to_xy(rc): return (rc[1] + 0.5, RES - (rc[0] + 0.5))

# ---------------------------------------------------------------- skeleton
def skeleton_paths(mask, W, min_tip=None):
    """Centre lines of stroke-like ink as lists of (x, y) points."""
    skel, dist = medial_axis(mask, return_distance=True, rng=0)  # fixed tie-breaking: same skeleton every run
    thick = 2 * dist
    skel &= thick < 1.6 * W
    skel &= thick > 0.55 * W
    min_tip = min_tip or 0.9 * W
    for _ in range(6):  # prune short tips (corner and cap spurs) until stable
        if skel.sum() < 3: break
        sk = Skeleton(skel); st = summarize(sk, separator="_")
        tips = st[(st["branch_type"] == 1) & (st["branch_distance"] < min_tip)]
        if tips.empty: break
        deg = ndi.convolve(skel.astype(int), np.ones((3, 3), int), mode="constant") - 1
        for i in tips.index:
            coords = sk.path_coordinates(i).astype(int)
            for r, c in coords:  # keep junction pixels so the trunk stays connected
                if deg[r, c] <= 2: skel[r, c] = False
        skel = _thin(skel)
    if skel.sum() < 3: return [], dist
    sk = Skeleton(skel)
    paths = []
    for i in range(sk.n_paths):
        rc = sk.path_coordinates(i)
        if len(rc) < 3: continue
        paths.append([px_to_xy(p) for p in rc])
    return paths, dist

def _thin(sk):
    from skimage.morphology import skeletonize
    return skeletonize(sk)

def chain(paths, W):
    """Join branches that meet end-to-end and run on in the same direction."""
    paths = [list(p) for p in paths]
    def tangent(p, at_end):
        a, b = (p[-1], p[-min(len(p), 12)]) if at_end else (p[0], p[min(len(p) - 1, 11)])
        dx, dy = a[0] - b[0], a[1] - b[1]; L = math.hypot(dx, dy) or 1
        return dx / L, dy / L  # pointing out of the path at that end
    changed = True
    while changed:
        changed = False
        best = None
        for i, j in itertools.permutations(range(len(paths)), 2):
            for ei, ej in itertools.product((True, False), repeat=2):
                pi, pj = paths[i], paths[j]
                a = pi[-1] if ei else pi[0]; b = pj[-1] if ej else pj[0]
                if math.dist(a, b) > 3: continue
                ti, tj = tangent(pi, ei), tangent(pj, ej)
                straight = -(ti[0] * tj[0] + ti[1] * tj[1])  # 1 = runs straight on
                if straight > 0.8 and (best is None or straight > best[0]):
                    best = (straight, i, j, ei, ej)
        if best:
            _, i, j, ei, ej = best
            pi = paths[i] if ei else paths[i][::-1]
            pj = paths[j][::-1] if ej else paths[j]
            merged = pi + pj[1:]
            paths = [p for k, p in enumerate(paths) if k not in (i, j)] + [merged]
            changed = True
    return paths

# ---------------------------------------------------------------- fitting
def rdp(pts, eps):
    if len(pts) < 3: return list(range(len(pts)))
    a, b = np.array(pts[0]), np.array(pts[-1]); P = np.array(pts)
    ab = b - a; L = np.hypot(*ab)
    d = np.abs(ab[0] * (P[:, 1] - a[1]) - ab[1] * (P[:, 0] - a[0])) / L if L else np.hypot(*(P - a).T)
    i = int(np.argmax(d))
    if d[i] > eps:
        left = rdp(pts[:i + 1], eps); right = rdp(pts[i:], eps)
        return left[:-1] + [k + i for k in right]
    return [0, len(pts) - 1]

def fit_circle(P):
    x, y = P[:, 0], P[:, 1]
    A = np.c_[2 * x, 2 * y, np.ones(len(P))]; b = x * x + y * y
    (cx, cy, c), *_ = np.linalg.lstsq(A, b, rcond=None)
    r = math.sqrt(max(c + cx * cx + cy * cy, 0))
    res = np.abs(np.hypot(x - cx, y - cy) - r)
    return cx, cy, r, float(res.max())

def snap(v, g): return round(v / g) * g if g else v

def fit_path(pts, grid, eps=1.6, arc_tol=1.6):
    """Points along a centre line -> SVG path d of lines and circular arcs."""
    P = np.array(pts); closed = math.dist(pts[0], pts[-1]) < 3 and len(pts) > 20
    idx = rdp(pts, eps)
    segs = []  # ("L", end) or ("A", r, large, sweep, end)
    k = 0
    while k < len(idx) - 1:
        best = None
        for m in range(len(idx) - 1, k + 1, -1):  # longest arc first
            seg = P[idx[k]:idx[m] + 1]
            if len(seg) < 8: continue
            cx, cy, r, err = fit_circle(seg)
            if err < arc_tol and r < 2000:
                best = (m, cx, cy, r); break
        if best:
            m, cx, cy, r = best
            a0 = math.atan2(P[idx[k]][1] - cy, P[idx[k]][0] - cx)
            mid = P[(idx[k] + idx[m]) // 2]; am = math.atan2(mid[1] - cy, mid[0] - cx)
            a1 = math.atan2(P[idx[m]][1] - cy, P[idx[m]][0] - cx)
            sweep_ccw = ((am - a0) % (2 * math.pi)) < ((a1 - a0) % (2 * math.pi))
            span = (a1 - a0) % (2 * math.pi) if sweep_ccw else (a0 - a1) % (2 * math.pi)
            segs.append(("A", (cx, cy), r, span > math.pi, sweep_ccw, idx[m])); k = m
        else:
            segs.append(("L", idx[k + 1])); k += 1
    # build d with snapped coordinates; arcs keep their snapped centre and radius
    def pt(i): return (snap(P[i][0], grid), snap(P[i][1], grid))
    out = []; s0 = pt(0); out.append(f"M{s0[0]:.2f} {s0[1]:.2f}")
    for s in segs:
        if s[0] == "L":
            e = pt(s[1]); out.append(f"L{e[0]:.2f} {e[1]:.2f}")
        else:
            _, c, r, large, ccw, i = s
            c = (snap(c[0], grid), snap(c[1], grid)); r = snap(r, grid)
            e = P[i]; ang = math.atan2(e[1] - c[1], e[0] - c[0])
            e = (c[0] + r * math.cos(ang), c[1] + r * math.sin(ang))
            # SVG sweep flag 1 = clockwise in screen space = counter-clockwise in y-up
            out.append(f"A{r:.2f} {r:.2f} 0 {int(large)} {int(ccw)} {e[0]:.2f} {e[1]:.2f}")
    if closed: out.append("Z")
    return " ".join(out), closed

# ---------------------------------------------------------------- rebuild
def components(orig_path):
    """Split ink into outer contours with their holes. Nesting depth decides
    what is a hole (odd depth) and which outer owns it (the nearest one), so
    it works whatever direction the contours run and however deep they nest."""
    cs = V.to_contours(orig_path)
    if not cs: return []
    polys = [_flat(c) for c in cs]
    def contains(i, j):  # does contour i contain contour j?
        return i != j and abs(_area_of(polys[i])) > abs(_area_of(polys[j])) and _pip(polys[j][len(polys[j]) // 2], polys[i])
    parents = {j: [i for i in range(len(cs)) if contains(i, j)] for j in range(len(cs))}
    depth = {j: len(parents[j]) for j in parents}
    outers = [j for j in depth if depth[j] % 2 == 0]
    comps = []
    for o in outers:
        holes = [j for j in depth if depth[j] == depth[o] + 1 and o in parents[j]]
        comps.append((cs[o], [cs[h] for h in holes]))
    return comps

def _flat(c):
    pts = []
    for seg in c:
        for t in (0, 0.25, 0.5, 0.75):
            mt = 1 - t
            pts.append(tuple(sum(w * q[k] for w, q in zip((mt**3, 3*mt*mt*t, 3*mt*t*t, t**3), seg)) for k in (0, 1)))
    return pts

def _area_of(P): return sum(P[i][0] * P[i - 1][1] - P[i - 1][0] * P[i][1] for i in range(len(P))) / 2

def _pip(p, P):
    x, y = p; inside = False
    for i in range(len(P)):
        (x1, y1), (x2, y2) = P[i - 1], P[i]
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1): inside = not inside
    return inside

def _inside(h, po):
    hp = contours_to_path([h])
    return abs(_parea(pathops.op(hp, po, pathops.PathOp.INTERSECTION)) - _parea(hp)) < 1

def _parea(p):
    from fontTools.pens.areaPen import AreaPen
    pen = AreaPen(); p.draw(pen); return abs(pen.value)

def d_of_contour(c, nd=2):
    """SVG path data for one closed cubic contour, nd decimals. Patches use
    more: their edges lie on the fitted edges, and Skia's booleans misbehave
    when two edges are almost (but not exactly) on top of each other."""
    f = lambda v: f"{v:.{nd}f}"
    s = [f"M{f(c[0][0][0])} {f(c[0][0][1])}"]
    for p0, c1, c2, p3 in c: s.append(f"C{f(c1[0])} {f(c1[1])} {f(c2[0])} {f(c2[1])} {f(p3[0])} {f(p3[1])}")
    return " ".join(s) + " Z"

def stroke_parts_from_mask(mask, W, grid, cap, join, prefix):
    paths, _ = skeleton_paths(mask, W)
    paths = chain(paths, W)
    parts = []
    for k, p in enumerate(paths):
        if len(p) < 4: continue
        d, closed = fit_path(p, grid)
        parts.append({"id": f"{prefix}{k}", "kind": "stroke", "d": d, "width": W, "align": "center",
                      "cap": "butt" if closed else cap, "join": join, "role": None})
    return parts

def rebuild(orig_contours, W, grid=10, cap="square", join="miter", verbose=False):
    import refine as F
    outline = F.Outline(orig_contours)
    orig = contours_to_path(orig_contours)
    omask = mask_of(orig)
    parts = []
    for ci, (outer, holes) in enumerate(components(orig)):
        comp = contours_to_path([outer] + holes)
        cmask = mask_of(comp)
        dist = ndi.distance_transform_edt(cmask)
        stroke_like = np.count_nonzero((2 * dist > 0.8 * W) & (2 * dist <= 1.25 * W)) > 0 and \
                      np.count_nonzero(2 * dist > 1.45 * W) < 0.08 * np.count_nonzero(cmask)
        if stroke_like:
            parts += stroke_parts_v2(cmask, outline, W, grid, join, f"s{ci}_")
        else:
            parts.append({"id": f"solid{ci}", "kind": "solid", "d": d_of_contour(outer), "role": None})
            for hi, h in enumerate(holes):
                hmask = mask_of(contours_to_path([h]))
                hd = ndi.distance_transform_edt(hmask)
                if np.count_nonzero(2 * hd > 1.45 * W) < 0.05 * np.count_nonzero(hmask):
                    ks = stroke_parts_v2(hmask, outline, W, grid, join, f"k{ci}_{hi}_")
                    for p in ks: p["role"] = {"knockout": True}
                    parts += ks
                else:
                    parts.append({"id": f"k{ci}_{hi}", "kind": "solid", "d": d_of_contour(h), "role": {"knockout": True}})
    # put knockouts after everything they cut is drawn
    parts = [p for p in parts if not (p.get("role") or {}).get("knockout")] + [p for p in parts if (p.get("role") or {}).get("knockout")]
    base = score(V.generate(parts), omask)
    if verbose: print("strokes+solids", base)
    parts, best = improve_caps(parts, omask, base)
    parts, best = find_cuts(parts, omask, best, W, verbose)
    return parts, best

def improve_caps(parts, omask, best):
    for p in parts:
        if p["kind"] != "stroke" or p["d"].endswith("Z"): continue
        for cap in ("butt", "round", "square"):
            if cap == p["cap"]: continue
            old = p["cap"]; p["cap"] = cap
            s = score(V.generate(parts), omask)
            if s[0] < best[0] - 0.01: best = s
            else: p["cap"] = old
    return parts, best

def find_cuts(parts, omask, best, W, verbose=False):
    gaps = [W / 4, W / 2, 3 * W / 4, W]
    improved = True
    while improved:
        improved = False
        for i, p in enumerate(parts):
            if p["kind"] != "stroke" or (p.get("role") or {}).get("knockout") or "cut" in (p.get("role") or {}): continue
            trial_best = None
            for g in gaps:
                for side in ("both", "left", "right"):
                    q = dict(p); q["role"] = {"cut": g, "side": side}
                    trial = [x for k, x in enumerate(parts) if k != i] + [q]
                    s = score(V.generate(trial), omask)
                    if s[0] < best[0] - 0.05 and (trial_best is None or s[0] < trial_best[0][0]):
                        trial_best = (s, trial)
            if trial_best:
                best, parts = trial_best; improved = True
                if verbose: print("cut", p["id"], parts[-1]["role"], best)
                break
    return parts, best

# ---------------------------------------------------------------- exact refinement (v2)
import refine as F

def rough_prims(pts, eps=1.6, arc_tol=2.0):
    P = np.array(pts); idx = rdp(pts, eps); prims = []; k = 0
    while k < len(idx) - 1:
        best = None
        for m in range(len(idx) - 1, k + 1, -1):
            seg = P[idx[k]:idx[m] + 1]
            if len(seg) < 10: continue
            cx, cy, r, err = fit_circle(seg)
            if err < arc_tol and r < 1500: best = (m, cx, cy, r); break
        if best:
            m, cx, cy, r = best
            a0 = math.atan2(P[idx[k]][1] - cy, P[idx[k]][0] - cx)
            angs = np.unwrap(np.arctan2(P[idx[k]:idx[m] + 1, 1] - cy, P[idx[k]:idx[m] + 1, 0] - cx))
            prims.append(("A", (cx, cy), r, float(angs[0]), float(angs[-1]))); k = m
        else:
            prims.append(("L", tuple(P[idx[k]]), tuple(P[idx[k + 1]]))); k += 1
    return prims

def snap_val(v, g, tol):
    s = round(v / g) * g
    return s if abs(s - v) <= tol else v

def snap_prim(pr, g, tol):
    if pr[0] == "L":
        return ("L", tuple(snap_val(v, g, tol) for v in pr[1]), tuple(snap_val(v, g, tol) for v in pr[2]))
    return ("A", tuple(snap_val(v, g, tol) for v in pr[1]), snap_val(pr[2], g, tol), pr[3], pr[4])

def exact_path(pts, outline, W, grid):
    closed = math.dist(pts[0], pts[-1]) < 3 and len(pts) > 20
    prims = rough_prims(pts)
    prims = [F.refine_prim(p, outline, W)[0] for p in prims]
    if grid: prims = [snap_prim(p, grid, 0.75) for p in prims]
    # rebuild corners between neighbours
    n = len(prims)
    pairs = range(n if closed else n - 1)
    for i in pairs:
        a, b = prims[i], prims[(i + 1) % n]
        jp = F.join_point(a, b)
        prims[i] = F.set_end(a, jp); prims[(i + 1) % n] = F.set_start(prims[(i + 1) % n], jp)
    ends = {}
    if not closed:
        # run free ends out to the original's cap edge (butt cap); remember the
        # alternative of a round cap ending half a stroke short
        for at_end in (False, True):
            pr = prims[-1] if at_end else prims[0]
            p = F.end(pr) if at_end else F.start(pr)
            t = F.tangent_out(pr, at_end)
            h = outline.ray(p, t, 3 * W)
            if h is not None:
                q = (p[0] + t[0] * h, p[1] + t[1] * h)
                if pr[0] == "L":
                    pr = F.set_end(pr, q) if at_end else F.set_start(pr, q)
                    if at_end: prims[-1] = pr
                    else: prims[0] = pr
                ends[at_end] = h
    return prims, closed

def stroke_parts_v2(mask, outline, W, grid, join, prefix):
    paths, _ = skeleton_paths(mask, W)
    paths = chain(paths, W)
    parts = []
    for k, p in enumerate(paths):
        if len(p) < 6: continue
        prims, closed = exact_path(p, outline, W, grid)
        parts.append({"id": f"{prefix}{k}", "kind": "stroke", "d": F.to_d(prims, closed), "width": W,
                      "align": "center", "cap": "butt", "join": join, "role": None, "_prims": prims})
    return parts
