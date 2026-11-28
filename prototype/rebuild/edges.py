"""Edge-level view of Material's corrections, for every glyph.

Each TrueType contour is split into segments that are either straight or one
quadratic curve (implied on-curve points between two handles are made
explicit; they exist in every master, so this keeps the masters matched).
Every segment is an edge. For each master we measure how far the edge moved
along its normal at both ends and at its middle (on a curve, each end
uses the curve's own normal there). If all three moved the
same amount (within 0.1 px) the edge moved parallel to itself: an offset of
that one edge, which a rule can produce. If not, the edge tilted or bent.

We also record two facts about the edge's surroundings, at the default style
and again on each master at the moved edge:
  thick  how much ink is behind it (stroke width there)
  free   how much empty space is in front of it before the next ink (-1 = open)
Columns: glyph, length, role (0 outer, 1 counter), free, thick, midx, midy, nx, ny,
then per master (LOCS order): k x6, spread x6 (how unevenly the edge moved), thick x6, free x6, and last
`back`: empty space beyond the far side of the stroke (-1 = open), then the
contour index, then 1 if the edge is a curve.
Usage: edges.py OUT.npz [from to]"""
import sys, math
import numpy as np
import icons_io as IO
from refine import Outline

LOCS = ["w100", "w700", "o20", "o48", "g200", "gm50"]
TOL = 4.0

def segments(P, on):
    """Expand one closed contour into (p0, ctrl or None, p2) segments, made of
    index references so the same expansion applies to every master. Implied
    on-curve points (between two handles) become ("mid", i, j); a contour made
    only of handles (a TrueType circle) works too."""
    n = len(P); nodes = []          # cyclic list of ("on", ref) / ("off", i)
    for i in range(n):
        j = (i + 1) % n
        nodes.append(("on", ("pt", i)) if on[i] else ("off", i))
        if not on[i] and not on[j]: nodes.append(("on", ("mid", i, j)))
    k0 = next(i for i, x in enumerate(nodes) if x[0] == "on")
    nodes = nodes[k0:] + nodes[:k0] + [nodes[k0]]
    out, cur, ctrl = [], nodes[0][1], None
    for kind, ref in nodes[1:]:
        if kind == "off": ctrl = ref
        else: out.append((cur, ctrl, ref)); cur, ctrl = ref, None
    return out

def at(P, ref):
    return P[ref[1]] if ref[0] == "pt" else (P[ref[1]] + P[ref[2]]) / 2

def run(names, N):
    rows = []
    for gi, name in names:
        p0, ends, on = IO.ms_points(name, "def", N)
        p0 = np.array(p0, float); on = np.array(on, bool)
        moved = {l: np.array(IO.ms_points(name, l, N)[0], float) for l in LOCS}
        out = Outline(IO.ms_contours(name, "def", N))
        outs = {l: Outline(IO.ms_contours(name, l, N)) for l in LOCS}
        s = 0
        for ci, e in enumerate(ends):
            sl = slice(s, e + 1); s = e + 1
            P0 = p0[sl]; onc = on[sl]
            if len(P0) < 3: continue
            x, y = P0[:, 0], P0[:, 1]
            role = 0 if np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y) < 0 else 1
            for a, c, b in segments(P0, onc):
                A0, B0 = at(P0, a), at(P0, b)
                v = B0 - A0; Lc = math.hypot(*v)
                if Lc < 8: continue
                n = np.array([-v[1], v[0]]) / Lc
                M0 = A0 / 4 + P0[c] / 2 + B0 / 4 if c is not None else (A0 + B0) / 2
                L = Lc if c is None else (np.linalg.norm(P0[c] - A0) + np.linalg.norm(B0 - P0[c]) + Lc) / 2
                free = out.ray(M0 + 0.5 * n, n, 2000); thick = out.ray(M0 - 0.5 * n, -n, 2000)
                back = out.ray(M0 - (thick + 0.5) * n, -n, 2000) if thick is not None else None
                # on a curve each end moves along its own normal; the middle along the chord's
                def unit_n(t):
                    l = math.hypot(*t); return np.array([-t[1], t[0]]) / l if l else n
                na = unit_n(P0[c] - A0) if c is not None else n
                nb = unit_n(B0 - P0[c]) if c is not None else n
                ks, par, th, fr = [], [], [], []
                for l in LOCS:
                    P1 = moved[l][sl]
                    A1, B1 = at(P1, a), at(P1, b)
                    M1 = A1 / 4 + P1[c] / 2 + B1 / 4 if c is not None else (A1 + B1) / 2
                    d = [(A1 - A0) @ na, (M1 - M0) @ n, (B1 - B0) @ nb]
                    k = float(np.mean(d)); ks.append(k); par.append(max(d) - min(d))  # spread: 0 = moved parallel
                    m2 = M0 + k * n
                    t2 = outs[l].ray(m2 - 0.5 * n, -n, 2000); f2 = outs[l].ray(m2 + 0.5 * n, n, 2000)
                    th.append(-1 if t2 is None else t2); fr.append(-1 if f2 is None else f2)
                rows.append([gi, L, role, -1 if free is None else free, -1 if thick is None else thick,
                             M0[0], M0[1], n[0], n[1], *ks, *par, *th, *fr, -1 if back is None else back, ci, int(c is not None)])
    return np.array(rows, float)

def unique_names(N):
    f = IO.ms_font(); cm = f.getBestCmap(); seen, names = set(), []
    for n, cp in sorted(N.items()):
        g = cm.get(cp)
        if g and g not in seen: seen.add(g); names.append(n)
    return names

if __name__ == "__main__":
    N = IO.ms_names(); names = unique_names(N)
    lo, hi = (int(sys.argv[2]), int(sys.argv[3])) if len(sys.argv) > 3 else (0, len(names))
    A = run(list(enumerate(names))[lo:hi], N)
    np.savez_compressed(sys.argv[1], edges=A, names=np.array(names), locs=np.array(LOCS))
    print(len(names), "unique glyphs;", len(A), "edges")
