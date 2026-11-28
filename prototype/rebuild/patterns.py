"""Which corrections does Google apply to each shape between Material's masters?

Every Material master has the same points in the same order, so each point's
movement from the default style to another master can be measured directly.
For each contour and each master, the movement is fitted with nested models,
simplest first, and the simplest one that explains every point within
tolerance is kept:

  static   nothing moves
  offset   every edge moves the same distance along its normal (k)
  shift    offset, plus the whole contour slides (tx, ty)
  scale    shift, plus the contour grows or shrinks about its centre (s)
  redraw   none of the above: points move independently (hand-drawn change)

Corners use the offset direction of a mitred outline (n1 + n2) / (1 + n1.n2),
so a pure offset is exact at corners too. Only on-curve points are fitted;
off-curve handles follow their curves.
Writes one JSON record per glyph. Usage: patterns.py OUT.json"""
import sys, json, math
import numpy as np
import icons_io as IO

LOCS = ["w100", "w700", "o20", "o48", "g200", "gm50"]
TOL = 4.0     # units; 40 units = 1 px at 24 px, so 0.1 px
MODELS = ["static", "offset", "shift", "scale"]

def contours(pts, ends):
    starts = [0] + [e + 1 for e in ends[:-1]]
    return list(zip(starts, ends))

def area(P):
    x, y = P[:, 0], P[:, 1]
    return 0.5 * float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y))

def miter_dirs(P):
    """Offset direction at each point of a closed polygon, pointing away from
    ink (TrueType outers run clockwise, so 'left of travel' is outside)."""
    a = P - np.roll(P, 1, 0); b = np.roll(P, -1, 0) - P
    def nrm(v):
        L = np.linalg.norm(v, axis=1, keepdims=True); L[L == 0] = 1
        v = v / L; return np.stack([-v[:, 1], v[:, 0]], 1)
    n1, n2 = nrm(a), nrm(b)
    dot = np.sum(n1 * n2, 1, keepdims=True)
    m = (n1 + n2) / np.maximum(1 + dot, 0.15)   # cap very sharp spikes
    return m

def fit(P, D, M):
    """Least squares for each nested model. Returns {model: (params, residual max)}."""
    c = P.mean(0); out = {}
    out["static"] = ({}, float(np.abs(D).max()))
    cols = {"offset": [M], "shift": [M, np.tile([1, 0], (len(P), 1)), np.tile([0, 1], (len(P), 1))]}
    cols["scale"] = cols["shift"] + [P - c]
    names = {"offset": ["k"], "shift": ["k", "tx", "ty"], "scale": ["k", "tx", "ty", "s"]}
    y = D.reshape(-1)
    for m in ("offset", "shift", "scale"):
        A = np.stack([c_.reshape(-1) for c_ in cols[m]], 1)
        x, *_ = np.linalg.lstsq(A, y, rcond=None)
        r = np.abs(y - A @ x).reshape(-1, 2)
        out[m] = (dict(zip(names[m], [round(float(v), 3) for v in x])), float(np.linalg.norm(r, axis=1).max()))
    return out

def glyph(name, N):
    p0, ends, on = IO.ms_points(name, "def", N)
    p0 = np.array(p0, float); on = np.array(on, bool)
    others = {l: np.array(IO.ms_points(name, l, N)[0], float) for l in LOCS}
    rec = {"name": name, "contours": []}
    for s, e in contours(p0, ends):
        idx = np.arange(s, e + 1)[on[s:e + 1]]
        if len(idx) < 3: continue
        P = p0[idx]; ar = area(P)
        role = "outer" if ar < 0 else "counter"
        M = miter_dirs(P if ar < 0 else P)  # direction already follows winding
        crec = {"role": role, "points": int(len(idx)), "area": abs(ar), "locs": {}}
        for l in LOCS:
            D = others[l][idx] - P
            f = fit(P, D, M)
            best = next((m for m in MODELS if f[m][1] <= TOL), "redraw")
            keep = best if best != "redraw" else "scale"
            crec["locs"][l] = {"model": best, "params": f[keep][0], "resid": round(f[keep][1], 2),
                               "move": round(float(np.linalg.norm(D, axis=1).max()), 2)}
        rec["contours"].append(crec)
    return rec

if __name__ == "__main__":
    N = IO.ms_names(); f = IO.ms_font(); cm = f.getBestCmap()
    seen, names = set(), []
    for n, cp in sorted(N.items()):
        g = cm.get(cp)
        if g and g not in seen: seen.add(g); names.append(n)
    if len(sys.argv) > 2: names = names[:int(sys.argv[2])]
    out = []
    for i, n in enumerate(names):
        try: out.append(glyph(n, N))
        except Exception as ex: print("FAIL", n, ex, file=sys.stderr)
    json.dump(out, open(sys.argv[1], "w"))
    print(len(out), "glyphs")
