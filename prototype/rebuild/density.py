"""How much ink surrounds each edge (research 09).

The learned anchor rule (research 06) sees the space in front of and behind
an edge, but not whether the edge sits in a mostly filled shape. In filled
icons with knocked-out details (a filled square with white arrows), Google
moves edges differently, and the rule missed them. This adds three columns
to the edge table: the share of ink in the glyph's box, and the share of ink
in a disc of radius 60 and 160 units around the edge (at the default).
Usage: density.py EDGES.npz OUT.npz   (EDGES from orient.py)"""
import sys
import numpy as np
from multiprocessing import Pool
from scipy.signal import fftconvolve
import icons_io as IO, edgemove as E

def disc(r):
    y, x = np.mgrid[-r:r + 1, -r:r + 1]; return (x * x + y * y <= r * r).astype(float)

def dens(args):
    name, rows = args
    ink = E.mask(IO.ms_contours(name)).astype(float)
    ys, xs = np.nonzero(ink)
    box = ink[ys.min():ys.max() + 1, xs.min():xs.max() + 1].mean() if len(ys) else 0.0
    c = np.clip((rows[:, 5] / E.U).astype(int), 0, ink.shape[1] - 1)
    r = np.clip(((960 - rows[:, 6]) / E.U).astype(int), 0, ink.shape[0] - 1)
    out = [np.full(len(rows), box)]
    for rad in (60, 160):
        k = disc(int(rad / E.U)); m = fftconvolve(ink, k / k.sum(), mode="same")
        out.append(m[r, c])
    return np.stack(out, 1)

def main(src, dst):
    Z = np.load(src); A = Z["edges"]; names = [str(x) for x in Z["names"]]
    g = A[:, 0].astype(int); order = np.argsort(g, kind="stable")
    groups = np.split(order, np.flatnonzero(np.diff(g[order])) + 1)
    with Pool() as pool: res = pool.map(dens, [(names[g[ix[0]]], A[ix]) for ix in groups], chunksize=20)
    D = np.zeros((len(A), 3))
    for ix, d in zip(groups, res): D[ix] = d
    np.savez_compressed(dst, edges=A, names=Z["names"], locs=Z["locs"], out=Z["out"], dens=D)

if __name__ == "__main__":
    main(*sys.argv[1:3])
