"""Carbon draws some icons again at 16 px instead of shrinking the 32 px one.
Those pairs are Carbon's own record of optical-size corrections. Both are put
on the same 960 grid (Carbon's 16 px stroke is 1/16 of the icon, the same share
as 2/32), so any difference is a redraw, not a scale change.
For each pair: how much ink differs, and whether parts, holes or gaps changed.
Usage: carbon16.py OUT.json SHEET.png"""
import sys, os, re, json, tempfile, math
import numpy as np
from scipy import ndimage as ndi
from PIL import Image, ImageDraw
from fontTools.svgLib.path import SVGPath
import icons_io as IO, extract as X

def contours(path, size):
    txt = open(path).read()
    txt = IO.strip_invisible(txt)
    with tempfile.NamedTemporaryFile("w", suffix=".svg", delete=False) as t: t.write(txt); tmp = t.name
    pen = IO.CubicPen(); f = 960 / size
    SVGPath(tmp, transform=(f, 0, 0, -f, 0, 960)).draw(pen); os.unlink(tmp)
    return pen.contours

def feats(m):
    _, parts = ndi.label(m); _, holes = ndi.label(~m); return parts, holes - 1

def classify(a, b, W=60):
    """Per part of the 32 px drawing: did the 16 px drawing keep it, shift it
    as a whole, or reshape it? Parts are matched by overlap; a shift is the
    centroid offset; what still differs after shifting is reshaping."""
    la, na = ndi.label(a); lb, nb = ndi.label(b); out = []
    for i in range(1, na + 1):
        pa = la == i
        ov = np.bincount(lb[pa], minlength=nb + 1); ov[0] = 0
        j = int(ov.argmax())
        if j == 0: out.append(("dropped", float(pa.sum()))); continue
        pb = lb == j
        ca = np.array(ndi.center_of_mass(pa)); cb = np.array(ndi.center_of_mass(pb))
        dy, dx = np.round(cb - ca).astype(int)
        moved = np.roll(np.roll(pa, dy, 0), dx, 1)
        before = float((pa != pb).sum()); after = float((moved != pb).sum())
        shift = math.hypot(dx, dy)
        kind = "same" if before < 0.05 * pa.sum() else "shift" if after < 0.35 * before else "reshape"
        out.append((kind, before, round(shift / 40, 2)))
    return out

if __name__ == "__main__":
    base = os.path.join(IO.SRC, "carbon", "package", "svg")
    names = sorted(f[:-4] for f in os.listdir(os.path.join(base, "16")) if f.endswith(".svg"))
    names = [n for n in names if os.path.exists(os.path.join(base, "32", n + ".svg"))]
    rows, tiles = [], []
    skipped = []
    for n in names:
        try:
            contours(os.path.join(base, "16", n + ".svg"), 16); contours(os.path.join(base, "32", n + ".svg"), 32)
        except NotImplementedError:   # SVG transforms fontTools can't read (rotate, etc.)
            skipped.append(n); continue
        a = X.mask_of(X.contours_to_path(contours(os.path.join(base, "32", n + ".svg"), 32)))
        b = X.mask_of(X.contours_to_path(contours(os.path.join(base, "16", n + ".svg"), 16)))
        d = a != b; core = ndi.binary_erosion(d, iterations=6)   # differences thicker than 0.3 px at 24 px
        pa, ha = feats(a); pb, hb = feats(b)
        # pixel snapping: share of 16 px coordinates on whole or half pixels
        txt = open(os.path.join(base, "16", n + ".svg")).read()
        nums = [float(x) for x in re.findall(r"-?\d*\.?\d+", re.sub(r'viewBox="[^"]*"', "", txt))]
        snap16 = np.mean([abs(v * 2 - round(v * 2)) < 1e-6 for v in nums]) if nums else 0
        txt32 = open(os.path.join(base, "32", n + ".svg")).read()
        nums32 = [float(x) / 2 for x in re.findall(r"-?\d*\.?\d+", re.sub(r'viewBox="[^"]*"', "", txt32))]
        snap32 = np.mean([abs(v * 2 - round(v * 2)) < 1e-6 for v in nums32]) if nums32 else 0
        parts_kind = classify(a, b)
        rows.append({"parts_kind": [p[0] for p in parts_kind], "shift_px": [p[2] for p in parts_kind if p[0] == "shift"], "name": n, "diff_px2": round(float(d.sum()) / 1600, 2), "core_px2": round(float(core.sum()) / 1600, 2),
                     "ink_px2": round(float(a.sum()) / 1600, 1), "parts": [pa, pb], "holes": [ha, hb],
                     "snap16": round(float(snap16), 2), "snap32_at16": round(float(snap32), 2)})
        im = np.full(a.shape + (3,), 255, np.uint8); im[a & b] = (190, 190, 190); im[a & ~b] = (30, 90, 220); im[b & ~a] = (220, 40, 40)
        tiles.append((n, Image.fromarray(im).resize((150, 150), Image.LANCZOS)))
    rows.sort(key=lambda r: -r["core_px2"])
    json.dump(rows, open(sys.argv[1], "w"), indent=1)
    cols = 8; W = cols * 160 + 10; H = ((len(tiles) + cols - 1) // cols) * 172 + 10
    img = Image.new("RGB", (W, H), "white"); dr = ImageDraw.Draw(img)
    order = {r["name"]: i for i, r in enumerate(rows)}
    for i, (n, t) in enumerate(sorted(tiles, key=lambda x: order[x[0]])):
        x = 10 + (i % cols) * 160; y = 10 + (i // cols) * 172
        img.paste(t, (x, y + 14)); dr.text((x, y), n[:24], fill=(30, 30, 30))
    img.save(sys.argv[2], optimize=True)
    for r in rows: print(r)
    print("skipped", skipped)
