"""How do Material's outlines move per axis? For every on-curve point, measure
its displacement along the outward normal (away from ink), split by whether the
contour is an exterior edge or a counter (hole)."""
import sys, json, random, math
import numpy as np
import icons_io as io

def signed_area(pts):
    return sum(pts[i][0]*pts[(i+1)%len(pts)][1] - pts[(i+1)%len(pts)][0]*pts[i][1] for i in range(len(pts)))/2

def run(sample=1200, seed=1):
    N = io.ms_names(); f = io.ms_font()
    cm = f.getBestCmap(); glyphs = {}
    for n, cp in N.items(): glyphs.setdefault(cm.get(cp), n)
    names = [n for g, n in glyphs.items() if g]
    random.Random(seed).shuffle(names); names = names[:sample]
    locs = ["w100", "w700", "o20", "o48", "g200", "gm50", "fill1"]
    out = {l: {"exterior": [], "counter": []} for l in locs}
    for n in names:
        c0, ends, on = io.ms_points(n, "def", N)
        starts = [0] + [e+1 for e in ends[:-1]]
        others = {l: io.ms_points(n, l, N)[0] for l in locs}
        for s, e in zip(starts, ends):
            pts = c0[s:e+1]
            kind = "exterior" if signed_area(pts) < 0 else "counter"  # TrueType: exterior clockwise
            L = len(pts)
            for i in range(L):
                if not on[s+i]: continue
                p, a, b = pts[i], pts[i-1], pts[(i+1) % L]
                tx, ty = b[0]-a[0], b[1]-a[1]; tl = math.hypot(tx, ty)
                if tl == 0: continue
                nx, ny = -ty/tl, tx/tl   # left of travel = away from ink
                for l in locs:
                    q = others[l][s+i]
                    out[l][kind].append((q[0]-p[0])*nx + (q[1]-p[1])*ny)
    return out

if __name__ == "__main__":
    r = run()
    for l, d in r.items():
        for k, v in d.items():
            v = np.round(np.array(v)); vals, cnt = np.unique(v, return_counts=True)
            top = sorted(zip(cnt, vals), reverse=True)[:6]
            print(f"{l:6} {k:9} n={len(v):6} median={np.median(v):6.1f}  top: " + ", ".join(f"{int(x)}:{c*100/len(v):.0f}%" for c, x in top))
