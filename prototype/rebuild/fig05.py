"""Figures for research 05 (contact sheets from the pair and FILL runs).
Usage: fig05.py PAIRS.json FILL.json OUTDIR"""
import sys, os, json
import numpy as np
from scipy import ndimage as ndi
from PIL import Image, ImageDraw
import edgemove as E, fillfp as FF
from pairs import loader

def overlay(a, b, n, size=150):
    A_, B_ = E.mask(loader(a, n)), E.mask(loader(b, n))
    im = np.full(A_.shape + (3,), 255, np.uint8)
    im[A_ & B_] = (190, 190, 190); im[A_ & ~B_] = (30, 90, 220); im[B_ & ~A_] = (220, 40, 40)
    return Image.fromarray(im).resize((size, size), Image.LANCZOS)

COL = {"both": (70, 70, 70), "knockout": (130, 80, 220), "open": (60, 150, 230), "cut": (0, 160, 140),
       "bolder": (240, 150, 0), "reshape": (220, 40, 40), "outline": (205, 205, 205)}

def fill_tile(job, n, size=150):
    a, b, _ = FF.JOBS[job]
    O, F = E.mask(loader(a, n)), E.mask(loader(b, n))
    W = E.stroke_width(O); rad = max(1, int(round(0.75 * W / E.U)))
    Op = np.pad(O, rad + 2); D = ndi.distance_transform_edt(~Op) <= rad
    C = (ndi.distance_transform_edt(D) > rad)[rad + 2:-rad - 2, rad + 2:-rad - 2]
    H = O | ndi.binary_fill_holes(O) | (ndi.binary_fill_holes(C) & ~C)
    Od = ndi.binary_dilation(O, iterations=FF.TOL)
    im = np.full(O.shape + (3,), 255, np.uint8)
    im[O] = COL["outline"]; im[F & H] = COL["both"]
    miss = H & ~F
    im[miss & Od] = COL["knockout"]; im[miss & ~Od] = COL["open"]
    lab, nl = ndi.label(miss & ~Od)
    if nl:
        th = ndi.maximum(ndi.distance_transform_edt(miss & ~Od), lab, np.arange(1, nl + 1)) * 2 * E.U
        im[np.isin(lab, np.arange(1, nl + 1)[th <= W])] = COL["cut"]
    nearO = ndi.distance_transform_edt(~O) * E.U <= 0.5 * W
    im[F & ~H & nearO] = COL["bolder"]; im[F & ~H & ~nearO] = COL["reshape"]
    return Image.fromarray(im).resize((size, size), Image.LANCZOS)

def grid(rows, out, size=150):
    """rows: list of (label, [(caption, image)])"""
    cols = max(len(r[1]) for r in rows)
    Wd = cols * (size + 10) + 10; Ht = len(rows) * (size + 44) + 10
    img = Image.new("RGB", (Wd, Ht), "white"); d = ImageDraw.Draw(img)
    for i, (lab, cells) in enumerate(rows):
        y = 10 + i * (size + 44); d.text((10, y), lab, fill=(20, 20, 20))
        for j, (cap, t) in enumerate(cells):
            x = 10 + j * (size + 10); img.paste(t, (x, y + 16)); d.text((x, y + 18 + size), cap[:24], fill=(90, 90, 90))
    img.save(out, optimize=True)

if __name__ == "__main__":
    P = json.load(open(sys.argv[1])); Fj = json.load(open(sys.argv[2])); out = sys.argv[3]
    import pairs as PR
    rows = []
    for job, lab in (("phosphor:thin", "Phosphor regular vs thin"), ("phosphor:bold", "Phosphor regular vs bold"),
                     ("fluent:16", "Fluent 24 vs 16"), ("fluent:20", "Fluent 24 vs 20"), ("heroicons:solid16", "Heroicons solid 24 vs 16")):
        a, b = PR.JOBS[job][:2]
        per = P[job]["per_icon"]
        if job.startswith("phosphor:thin"): pick = [p["icon"] for p in per[len(per) // 2: len(per) // 2 + 3]] + [per[0]["icon"]]
        else: pick = [p["icon"] for p in per[:3]] + [per[len(per) // 2]["icon"]]
        rows.append((lab, [(n, overlay(a, b, n)) for n in pick]))
    grid(rows, os.path.join(out, "fig05-pairs.png"))
    rows = []
    for job in FF.JOBS:
        recs = Fj[job]["per_icon"]; cells = []
        for cls in ("flood", "knockout", "open", "cut", "bolder", "reshape"):
            c = [r for r in recs if r["class"] == cls]
            if not c: continue
            key = cls if cls != "flood" else "knockout"
            c.sort(key=lambda r: -r.get(key, 0)); r = c[min(len(c) - 1, len(c) // 4)]
            cells.append((f"{cls}: {r['icon']}", fill_tile(job, r["icon"])))
        rows.append((job, cells))
    grid(rows, os.path.join(out, "fig05-fill.png"))

def gt_sheet(items, out, size=200):
    """Answer key: outline (grey), true centre-line (blue), recovered (red)."""
    import anyset as A, extract as X, source as V, raster as R
    from PIL import ImageDraw as D
    cells = []
    for s, v, n in items:
        lines, W, cap, join = A.skeleton(s, v, n); c = A.contours(s, v, n)
        X.stroke_parts_v2 = lambda mask, outline, W_, grid, join_, prefix: X.stroke_parts_from_mask(mask, W_, grid, cap, join_, prefix)
        parts, _ = X.rebuild(c, W, grid=0, cap=cap, join=join)
        k = 2 * size / 960
        m = R.raster(c, 2 * size); im = Image.fromarray(np.where(m, 215, 255).astype(np.uint8)).convert("RGB")
        d = D.Draw(im)
        xy = lambda P: [(x * k, (960 - y) * k) for x, y in P]
        for l in lines:
            if len(l) > 1: d.line(xy(l), fill=(30, 90, 220), width=5)
        for p in parts:
            if p["kind"] != "stroke": continue
            for P in R.flatten(V.to_contours(V.path_from_d(p["d"])), 12):
                if len(P) > 1: d.line(xy(P), fill=(220, 40, 40), width=2)
        cells.append((f"{s} {n}", im.resize((size, size), Image.LANCZOS)))
    grid([("Answer key: grey = outline given to the fitter, blue = true centre-line, red = recovered", cells)], out, size)
