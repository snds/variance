"""Research 08: anchors per segment, stroke-end moves, and where the rest of
the error lives.

Research 07 gave each stroke one move per side. A long fitted stroke can hold
several segments that Google moves differently, so here every segment of the
centre-line gets its own left and right move (`sides` in the source), and
open strokes with butt or square caps get a move at each end (`ends`).

Recipes, each read from Google's measured edge moves ("best", an upper bound)
or from research 06's learned rule ("learned", trained on all other icons):
  stroke07 one move per side per stroke, as research 07 measured it
  stroke   the same, with edges found along their whole length
  segment  one move per side per segment
  +ends    segment, plus each open end's own move
  +solids  +ends, and every outline segment of a solid or a detail patch
           moves by its own amount (research 07 grew solids evenly and kept
           patches fixed)
Then, for the best recipe, every Google edge pixel we still miss is traced to
the source part nearest to it, to say what kind of part holds the error.
Usage: segments.py EDGES.npz SOURCES.pkl OUT.json"""
import sys, json, pickle, math
import numpy as np
from scipy.spatial import cKDTree
from scipy import ndimage as ndi
from sklearn.ensemble import HistGradientBoostingRegressor
import pathops
import extract as X, icons_io as IO, source as V, edgemove as E, weights as WT
import anchor as AN, learned as LN

W = LN.W
LOCS = LN.LOCS
R14 = 14          # search radius for edges near a sample, units

def _bez(seg, t):
    p0, c1, c2, p3 = (np.asarray(q, float) for q in seg); mt = 1 - t
    return mt**3 * p0 + 3 * mt * mt * t * c1 + 3 * mt * t * t * c2 + t**3 * p3

def _tan(seg, t):
    a, b = _bez(seg, max(0, t - 1e-4)), _bez(seg, min(1, t + 1e-4)); v = b - a; L = np.linalg.norm(v)
    return v / L if L > 1e-12 else None

class Edges:
    """One icon's glyph edges as short line pieces (research 04's edge table:
    middle, normal, length). Research 07 searched by an edge's middle only,
    so a long straight edge was found only near its middle; here the search
    measures the distance to the whole edge."""
    def __init__(self, rows, ink=None):
        self.m = rows[:, 5:7]; self.n = rows[:, 7:9]; self.n_raw = self.n; self.tree = cKDTree(self.m)
        # The table's normal is the contour's left side. Overlapping contours
        # in Material's fonts don't all run the same way, so on some edges it
        # points into the ink. `out` flips those, so a normal always points
        # out of the ink and a + move always grows the ink.
        self.out = np.ones(len(rows))
        if ink is not None:
            q = self.m - 6 * self.n                               # a little behind the edge
            c = np.clip((q[:, 0] / E.U).astype(int), 0, ink.shape[1] - 1); r = np.clip(((960 - q[:, 1]) / E.U).astype(int), 0, ink.shape[0] - 1)
            self.out = np.where(ink[r, c], 1.0, -1.0)
            self.n = self.n * self.out[:, None]
        self.h = np.stack([self.n[:, 1], -self.n[:, 0]], 1) * (rows[:, 1:2] / 2)    # half the edge, along it
    def dist(self, q):
        v = q - self.m; hh = (self.h ** 2).sum(1)
        t = np.clip((v * self.h).sum(1) / np.maximum(hh, 1e-9), -1, 1)
        return np.linalg.norm(v - t[:, None] * self.h, axis=1)
    def near(self, q, n=None, r=R14):
        ok = self.dist(np.asarray(q, float)) <= r
        if n is not None: ok &= self.n @ np.asarray(n, float) > 0.7
        return np.nonzero(ok)[0]

class Ref:
    """Fit to a drawing (research 09): instead of research 04's edge table,
    read moves straight off a reference master. At a point on our default
    outline, the reference's signed distance (+ inside its ink) is how far
    the reference's edge sits beyond ours, so it is the move (+ = ink
    grows). Works for any reference: another set's master or a designer's
    drawing."""
    R = 90                                                        # how far along the normal to look, units
    def __init__(self, ref_mask):
        self.m = ref_mask
        self.s = (E.sdf(ref_mask) - 0.5) * E.U                    # units, + inside the reference's ink
    def _px(self, q):
        q = np.atleast_2d(q)
        c = np.clip((q[:, 0] / E.U).astype(int), 0, self.m.shape[1] - 1); r = np.clip(((960 - q[:, 1]) / E.U).astype(int), 0, self.m.shape[0] - 1)
        return r, c
    def at(self, q, n=None):
        """With a direction n: walk along n through q and return the nearest
        place where the reference's ink ends (ink behind, empty ahead), as a
        distance from q. Without one: the signed distance to the nearest edge."""
        if n is None:
            r, c = self._px(q); return float(self.s[r[0], c[0]])
        n = np.asarray(n, float) / (np.linalg.norm(n) or 1.0); t = np.arange(-self.R, self.R + 1, 1.0)
        r, c = self._px(np.asarray(q, float)[None, :] + t[:, None] * n[None, :]); ink = self.m[r, c]
        cross = np.nonzero(ink[:-1] & ~ink[1:])[0]
        if not len(cross): return None
        return float(t[cross[np.argmin(np.abs(t[cross] + 0.5))]] + 0.5)

def near_moves(ed, k, q, n):
    """Moves (+ = ink grows) of glyph edges near point q whose outward normal points along n."""
    if isinstance(ed, Ref):
        v = ed.at(q, n); return [] if v is None else [v]
    j = ed.near(q, n); return list(k[j] * ed.out[j])

def seg_moves(part, ed, k, Wd=W, angled=False):
    """Per contour, per segment: (left move, right move); per open contour:
    (start move, end move). None where no glyph edge was found. A knockout's
    glyph edges face in, toward its centre-line."""
    fc = -1 if (part.get("role") or {}).get("knockout") else 1
    sides, ends = [], []
    for c in V.segs_of(part["d"]):
        cs = []
        for seg in c:
            got = ([], [])
            for t in np.linspace(0.08, 0.92, 10):            # stay off the corners, where the next segment's edges are
                tg = _tan(seg, t)
                if tg is None: continue
                p = _bez(seg, t); nl = np.array([-tg[1], tg[0]])
                for i, sgn in enumerate((1, -1)):
                    got[i].extend(near_moves(ed, k, p + sgn * nl * Wd / 2, fc * sgn * nl))
            cs.append(tuple(float(np.median(v)) if v else None for v in got))
        sides.append(cs)
        closed = math.dist(c[0][0], c[-1][3]) < 1e-6
        if closed: ends.append(None); continue
        reach = Wd / 2 if part.get("cap") in ("square", "round") else 0.0
        e = []
        for seg, t, s in ((c[0], 0.0, -1), (c[-1], 1.0, 1)):
            tg = _tan(seg, t)
            if tg is None: e.append(None); continue
            out = s * tg; p0 = _bez(seg, t) + out * reach
            if angled:                                        # each corner on its own: (left of the stroke, right of it)
                nl = np.array([-tg[1], tg[0]]); cs_ = []
                for side in (1, -1):
                    v = near_moves(ed, k, p0 + side * nl * Wd * 0.35, fc * out); cs_.append(float(np.median(v)) if v else None)
                e.append(None if None in cs_ else tuple(cs_)); continue
            v = near_moves(ed, k, p0, fc * out)
            e.append(float(np.median(v)) if v else None)
        ends.append(tuple(e))
    return sides, ends

def fill_gaps(sides, fallback):
    """Segments with no measured move take the stroke's own move."""
    out = []
    for cs in sides:
        out.append([tuple(v if v is not None else f for v, f in zip(s, fallback)) for s in cs])
    return out

def whole_moves(part, ed, k, Wd=W):
    """One move per side for the whole stroke (research 07's anchor, with the
    full-edge search). A dot is one point with a move all round. A
    knockout's glyph edges face in, toward its centre-line."""
    fc = -1 if (part.get("role") or {}).get("knockout") else 1
    if part.get("dot"):
        x, y = map(float, part["d"][1:].split(" L")[0].split()); r = Wd / 2 + part.get("extra", 0) / 2
        if isinstance(ed, Ref):
            v = [ed.at((x + r * np.cos(a), y + r * np.sin(a))) for a in np.linspace(0, 2 * np.pi, 16, endpoint=False)]
            m = float(np.median(v)); return (m, m)
        v = [k[j] * ed.out[j] for a in np.linspace(0, 2 * np.pi, 16, endpoint=False)
             for j in ed.near((x + r * np.cos(a), y + r * np.sin(a)), (fc * np.cos(a), fc * np.sin(a)))]
        m = float(np.median(v)) if v else None
        return (m, m)
    got = ([], [])
    for c in V.segs_of(part["d"]):
        for seg in c:
            for t in np.linspace(0.08, 0.92, 10):
                tg = _tan(seg, t)
                if tg is None: continue
                p = _bez(seg, t); nl = np.array([-tg[1], tg[0]])
                for i, sgn in enumerate((1, -1)): got[i].extend(near_moves(ed, k, p + sgn * nl * Wd / 2, fc * sgn * nl))
    return tuple(float(np.median(v)) if v else None for v in got)

def solid_move(part, ed, k):
    import raster as R
    c = V.to_contours(V.path_from_d(part["d"]))
    P = np.vstack(R.flatten(c, 12)) if c else np.zeros((0, 2))
    v = [ed.at(p) for p in P[::2]] if isinstance(ed, Ref) else [k[j] * ed.out[j] for p in P[::2] for j in ed.near(p, None, 6)]
    return float(np.median(v)) if v else None

def solid_edge_moves(part, ed, k, ink):
    """Per contour, per outline segment: the move (+ = left of the segment)
    read from the glyph edges right on that segment. `ink` is the part's own
    default mask, used to tell which side of each contour is inside. A
    knockout's outline faces the other way: its ink is outside it."""
    ko = bool((part.get("role") or {}).get("knockout")); out = []; allv = []
    per = []
    for c in V.segs_of(part["d"]):
        votes = 0; rows = []
        for seg in c:
            got = []; nls = []
            for t in np.linspace(0.1, 0.9, 5):
                tg = _tan(seg, t)
                if tg is None: continue
                p = _bez(seg, t); nl = np.array([-tg[1], tg[0]]); nls.append((p, nl))
            for p, nl in nls[::2]:
                q = p + 4 * nl; cc = int(np.clip(q[0] / E.U, 0, ink.shape[1] - 1)); rr = int(np.clip((960 - q[1]) / E.U, 0, ink.shape[0] - 1))
                votes += 1 if ink[rr, cc] else -1
            rows.append(nls)
        left_in = votes > 0                                     # the part's inside is to the left of this contour
        # outward from the glyph's ink: away from the part's inside, flipped for a knockout
        sgn_out = (-1 if left_in else 1) * (-1 if ko else 1)
        cs = []
        for nls in rows:
            v = []
            for p, nl in nls: v.extend(near_moves(ed, k, p, sgn_out * nl))
            m = float(np.median(v)) if v else None
            cs.append(m); allv.extend(v)
        per.append((cs, sgn_out))
    whole = float(np.median(allv)) if allv else 0.0
    thick = []                                                  # 2 x area / perimeter: about the width of a thin piece
    for c in V.segs_of(part["d"]):
        P = [tuple(_bez(sg, t)) for sg in c for t in (0, .25, .5, .75)]
        per_ = sum(math.dist(a, b) for a, b in zip(P, P[1:] + P[:1]))
        thick.append(2 * abs(V._area(P)) / per_ if per_ else 0.0)
    for cs, sgn_out in per:
        if part.get("patch"):
            # A patch is the fitter's leftover: it can hold slivers along other
            # parts' edges. Move only the outline pieces that sit on a glyph
            # edge, and only in contours that mostly do; leave the rest.
            if sum(m is not None for m in cs) < 0.75 * len(cs) or thick[len(out)] < 12: out.append([0.0] * len(cs)); continue
            out.append([0.0 if m is None else sgn_out * m for m in cs]); continue
        # a + move pushes the ink edge outward = along sgn_out * left normal; for the part's own outline
        out.append([sgn_out * (whole if m is None else m) for m in cs])
    return out

def visible_patches(parts):
    """A detail patch keeps only what it changes at the default: an added
    patch minus the ink the other parts already draw, a removing patch only
    where it meets that ink. The default rebuild is unchanged; at other
    masters the hidden overlap no longer pins ink in place."""
    base = V.generate([p for p in parts if not p.get("patch")])
    out = []
    for p in parts:
        if p.get("patch") and p["patch"]["type"] == "detail" and p["kind"] == "solid":
            ko = bool((p.get("role") or {}).get("knockout"))
            sh = V.op(V.fill(V.path_from_d(p["d"])), base, pathops.PathOp.INTERSECTION if ko else pathops.PathOp.DIFFERENCE)
            q = dict(p); q["d"] = sh.d if hasattr(sh, "d") else _d_of(sh); out.append(q)
        else: out.append(p)
    return out

def _d_of(path):
    from fontTools.pens.svgPathPen import SVGPathPen
    pen = SVGPathPen(None); path.draw(pen); return pen.getCommands()

def at_master(parts, Wn, mode, ed, k):
    """The source at one master. mode: stroke07 | stroke | segment | ends |
    solids | angled (solids, with each end corner moved on its own)."""
    angled = mode == "angled"
    if angled: mode = "solids"
    if mode == "solids": parts = visible_patches(parts)
    out = []
    for p in parts:
        if p.get("patch") and p["patch"]["type"] == "sliver": continue
        q = dict(p); ko = bool((p.get("role") or {}).get("knockout")); sg = -1 if ko else 1
        if q["kind"] == "solid" and mode == "solids":
            ink = E.mask(V.to_contours(V.part_shape(p)))
            q["edges"] = solid_edge_moves(p, ed, k, ink)
        elif q["kind"] == "solid" and not p.get("patch"):
            m = LN.solid_move(p, ed.tree, None, k) if mode == "stroke07" else solid_move(p, ed, k)
            if m is not None: q["grow"] = sg * m
        elif q["kind"] == "stroke" and not p.get("patch"):
            whole = LN.side_moves(p, ed.tree, None, ed.n_raw, k, W) if mode == "stroke07" else whole_moves(p, ed, k)
            if p.get("dot") or mode in ("stroke", "stroke07"):
                if whole is None or None in whole: q["width"] = Wn
                else:
                    kl, kr = sg * whole[0], sg * whole[1]
                    q["width"] = max(4.0, W + kl + kr); q["offset"] = (kl - kr) / 2
            else:
                fb = tuple(whole) if whole and None not in whole else ((Wn - W) / 2, (Wn - W) / 2)
                sides, ends = seg_moves(p, ed, k, angled=angled)
                sides = fill_gaps(sides, fb)
                def widths(a, b):              # a side may cross the centre-line; only the total width must stay positive
                    l, r = W / 2 + sg * a, W / 2 + sg * b; short = max(0.0, 4.0 - l - r) / 2
                    return l + short, r + short
                q["sides"] = {"left": [[widths(a, b)[0] for a, b in cs] for cs in sides],
                              "right": [[widths(a, b)[1] for a, b in cs] for cs in sides]}
                if mode in ("ends", "solids"):
                    sq = p.get("cap") == "square"
                    def end_extra(v, sd):                      # a square cap already moves half the end segment's width change
                        return 0.0 if v is None else sg * v - (sg * (sd[0] + sd[1]) / 2 if sq else 0.0)
                    def one(v, sd, start):
                        if isinstance(v, tuple):               # angled: (left corner, right corner); a start cap runs right to left
                            l_, r_ = end_extra(v[0], sd), end_extra(v[1], sd); return (r_, l_) if start else (l_, r_)
                        return end_extra(v, sd)
                    q["sides"]["ends"] = [(0.0, 0.0) if e is None else (one(e[0], cs[0], True), one(e[1], cs[-1], False))
                                          for e, cs in zip(ends, sides)]
        out.append(q)
    return out

def kind_of(p):
    ko = (p.get("role") or {}).get("knockout")
    if p.get("patch"): return "patch"
    if p.get("dot"): return "dot"
    return ("knockout " if ko else "") + ("stroke" if p["kind"] == "stroke" else "solid")

def blame(parts, gen, real):
    """Trace each of Google's edge pixels we miss to the nearest default
    part; for strokes, split sides from ends (within 1.5 stroke widths of an
    open end). Returns missed pixel counts by kind, and the total."""
    edge = real & ~ndi.binary_erosion(real)
    s = E.sdf(gen); miss = edge & (np.abs(s - 0.5) * E.U > 10)
    best = np.full(real.shape, np.inf); who = np.full(real.shape, -1)
    for i, p in enumerate(parts):
        try: m = E.mask(V.to_contours(V.part_shape(p)))
        except Exception: continue
        if not m.any(): continue
        dist = np.abs(E.sdf(m)); upd = dist < best; best[upd] = dist[upd]; who[upd] = i
    endz = np.zeros(real.shape, bool)
    for p in parts:
        if p["kind"] != "stroke" or p.get("dot"): continue
        for c in V.segs_of(p["d"]):
            if math.dist(c[0][0], c[-1][3]) < 1e-6: continue
            for pt in (c[0][0], c[-1][3]):
                b = pathops.Path(); pen = b.getPen(); r = 1.5 * W
                pen.moveTo((pt[0] - r, pt[1] - r)); pen.lineTo((pt[0] + r, pt[1] - r)); pen.lineTo((pt[0] + r, pt[1] + r)); pen.lineTo((pt[0] - r, pt[1] + r)); pen.closePath()
                endz |= E.mask(V.to_contours(b))
    out = {}
    for r_, c_ in zip(*np.nonzero(miss)):
        i = who[r_, c_]; kd = "none" if i < 0 else kind_of(parts[i])
        if kd.endswith("stroke") and endz[r_, c_]: kd += " end"
        out[kd] = out.get(kd, 0) + 1
    return out, int(edge.sum())

def main(npz, pkl, out):
    Z = np.load(npz); A = Z["edges"]; names = [str(x) for x in Z["names"]]
    Xf, ctx, g, L = AN.features(A)
    picks = json.load(open(__file__.replace("segments.py", "picks.json")))["material"]
    src = pickle.load(open(pkl, "rb"))
    inpick = np.isin(g, [names.index(n) for n in picks])
    preds = {}
    for loc, (li, Wn) in LOCS.items():
        k = A[:, 9 + li]; tr = ~inpick & (A[:, 15 + li] <= 10)
        m = HistGradientBoostingRegressor(loss="absolute_error", max_iter=300, max_leaf_nodes=63, categorical_features=[0], random_state=7)
        m.fit(Xf[tr], k[tr], sample_weight=L[tr]); preds[loc] = {"learned": m.predict(Xf), "best": k}
        print("trained", loc, flush=True)
    res = {}
    for n in picks:
        gi = names.index(n); ix = np.nonzero(g == gi)[0]
        ed = Edges(A[ix], E.mask(IO.ms_contours(n))); full = src[n]; res[n] = {}
        for loc, (li, Wn) in LOCS.items():
            real = E.mask(IO.ms_contours(n, loc)); r = {}
            for how in ("best", "learned"):
                kk = preds[loc][how][ix]
                for mode in ("stroke07", "stroke", "segment", "ends", "solids"):
                    key = f"{how} {mode}"
                    try:
                        parts = at_master(full, Wn, mode, ed, kk); gen = E.mask(V.to_contours(V.generate(parts)))
                        r[key] = {"edges": round(WT.edges_within(gen, real), 4)}
                        if how == "best" and mode == "solids":
                            r[key]["blame"], r[key]["edge_px"] = blame(parts, gen, real)
                    except (pathops.PathOpsError, ValueError) as e:
                        r[key] = {"error": repr(e)[:80]}
            res[n][loc] = r
            print(n, loc, {h: v.get("edges") for h, v in r.items()}, flush=True)
        json.dump(res, open(out, "w"), indent=1)

# Research 09: all six masters. Stroke width at each master: the median
# thickness Google's master gives a default 80-unit stroke (measured from the
# edge table; a measurement, not Google's internal value).
LOCS6 = {"w100": (0, 28), "w700": (1, 124), "o20": (2, 72), "o48": (3, 60), "g200": (4, 106), "gm50": (5, 70)}

def main9(npz, pkl, out):
    """Every master, four recipes: Google's edge moves through research 04's
    table (best), a fit read straight off Google's master (fit), the same
    with angled ends (angled), and the learned rule (learned)."""
    Z = np.load(npz); A = Z["edges"]; names = [str(x) for x in Z["names"]]
    Xf, ctx, g, L = AN.features(A)
    picks = json.load(open(__file__.replace("segments.py", "picks.json")))["material"]
    src = pickle.load(open(pkl, "rb")); inpick = np.isin(g, [names.index(n) for n in picks])
    pred = {}
    for loc, (li, Wn) in LOCS6.items():
        k = A[:, 9 + li]; tr = ~inpick & (A[:, 15 + li] <= 10)
        m = HistGradientBoostingRegressor(loss="absolute_error", max_iter=300, max_leaf_nodes=63, categorical_features=[0], random_state=7)
        m.fit(Xf[tr], k[tr], sample_weight=L[tr]); pred[loc] = m.predict(Xf); print("trained", loc, flush=True)
    res = {}
    for n in picks:
        ix = np.nonzero(g == names.index(n))[0]; ed = Edges(A[ix]); res[n] = {}
        for loc, (li, Wn) in LOCS6.items():
            real = E.mask(IO.ms_contours(n, loc)); ref = Ref(real); r = {}
            for key, e, mode, kk in (("best", ed, "solids", A[ix, 9 + li]), ("fit", ref, "solids", None),
                                     ("angled", ref, "angled", None), ("learned", ed, "solids", pred[loc][ix])):
                try:
                    parts = at_master(src[n], Wn, mode, e, kk); gen = E.mask(V.to_contours(V.generate(parts)))
                    r[key] = {"edges": round(WT.edges_within(gen, real), 4)}
                    if key == "angled": r[key]["blame"], r[key]["edge_px"] = blame(parts, gen, real)
                except (pathops.PathOpsError, ValueError) as ex:
                    r[key] = {"error": repr(ex)[:80]}
            res[n][loc] = r
            print(n, loc, {h: v.get("edges") for h, v in r.items()}, flush=True)
        json.dump(res, open(out, "w"), indent=1)

if __name__ == "__main__":
    if sys.argv[1] == "nine": main9(*sys.argv[2:5])
    else: main(*sys.argv[1:4])

def figure(npz, pkl, items, out, size=170):
    """Google's master against ours: one move per stroke side (research 07's
    controls, measured as research 07 did), then all of research 08's
    with Google's own moves, then with the learned rule. grey = both, blue =
    Google only, red = ours only. items: [(icon, loc)]."""
    from PIL import Image
    import fig05
    Z = np.load(npz); A = Z["edges"]; names = [str(x) for x in Z["names"]]
    Xf, ctx, g, L = AN.features(A)
    picks = json.load(open(__file__.replace("segments.py", "picks.json")))["material"]
    src = pickle.load(open(pkl, "rb")); inpick = np.isin(g, [names.index(n) for n in picks]); models = {}
    rows = []
    for n, loc in items:
        li, Wn = LOCS[loc]; k = A[:, 9 + li]
        if loc not in models:
            tr = ~inpick & (A[:, 15 + li] <= 10)
            m = HistGradientBoostingRegressor(loss="absolute_error", max_iter=300, max_leaf_nodes=63, categorical_features=[0], random_state=7)
            m.fit(Xf[tr], k[tr], sample_weight=L[tr]); models[loc] = m.predict(Xf)
        ix = np.nonzero(g == names.index(n))[0]; real = E.mask(IO.ms_contours(n, loc))
        ed = Edges(A[ix], E.mask(IO.ms_contours(n))); cells = []
        for cap, mode, kk in (("per stroke, Google", "stroke07", k[ix]), ("per segment, Google", "solids", k[ix]), ("per segment, learned", "solids", models[loc][ix])):
            ours = E.mask(V.to_contours(V.generate(at_master(src[n], Wn, mode, ed, kk))))
            im = np.full(real.shape + (3,), 255, np.uint8)
            im[real & ours] = (190, 190, 190); im[real & ~ours] = (30, 90, 220); im[ours & ~real] = (220, 40, 40)
            cells.append((f"{cap} {WT.edges_within(ours, real):.0%}", Image.fromarray(im).resize((size, size), Image.LANCZOS)))
        rows.append((f"{n} at {loc}", cells))
    fig05.grid(rows, out, size)
