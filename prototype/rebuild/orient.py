"""Point every edge's normal out of the ink (research 08).

Research 04's edge table takes each edge's normal from its contour's
direction. Material's fonts keep overlapping contours, and they don't all run
the same way, so on some edges that normal points into the ink and a + move
means the ink shrinks there. On those edges "free" and "thick" are swapped
too (the rays start on the wrong side), and so is the outer/counter role.

This writes a corrected table with the same columns, every normal pointing
out of the ink, plus `out` (+1 kept, -1 flipped). On flipped edges: normal
and moves negate, free and thick swap (default and per master), role flips,
and `back` is measured again from the correct side.
Usage: orient.py EDGES.npz OUT.npz"""
import sys
import numpy as np
from multiprocessing import Pool
import icons_io as IO, edgemove as E
from refine import Outline

def side(args):
    name, rows = args
    ink = E.mask(IO.ms_contours(name))
    q = rows[:, 5:7] - 6 * rows[:, 7:9]                   # a little behind the edge
    c = np.clip((q[:, 0] / E.U).astype(int), 0, ink.shape[1] - 1)
    r = np.clip(((960 - q[:, 1]) / E.U).astype(int), 0, ink.shape[0] - 1)
    out = np.where(ink[r, c], 1.0, -1.0)
    B = rows.copy(); f = out < 0
    if f.any():
        ol = Outline(IO.ms_contours(name)); F = B[f]
        F[:, 2] = 1 - F[:, 2]; F[:, 3], F[:, 4] = rows[f, 4], rows[f, 3]
        F[:, 7:9] *= -1; F[:, 9:15] *= -1
        F[:, 21:27], F[:, 27:33] = rows[f, 27:33], rows[f, 21:27]
        for i in range(len(F)):
            th = F[i, 4]
            if th < 0: F[i, 33] = -1; continue
            m = F[i, 5:7]; n = F[i, 7:9]
            b = ol.ray(m - (th + 0.5) * n, -n, 2000); F[i, 33] = -1 if b is None else b
        B[f] = F
    return out, B

def main(src, dst):
    Z = np.load(src); A = Z["edges"]; names = [str(x) for x in Z["names"]]
    g = A[:, 0].astype(int); order = np.argsort(g, kind="stable"); gs = g[order]
    cuts = np.flatnonzero(np.diff(gs)) + 1; groups = np.split(order, cuts)
    jobs = [(names[g[ix[0]]], A[ix]) for ix in groups]
    with Pool() as pool: res = pool.map(side, jobs, chunksize=20)
    out = np.ones(len(A)); A = A.copy()
    for ix, (o, B) in zip(groups, res): out[ix] = o; A[ix] = B
    print("edges flipped:", round(float((out < 0).mean()), 4), "of edge length:", round(float(A[out < 0, 1].sum() / A[:, 1].sum()), 4))
    np.savez_compressed(dst, edges=A, names=Z["names"], locs=Z["locs"], out=out)

if __name__ == "__main__":
    main(*sys.argv[1:3])
