"""Side-by-side proof image: original | source skeleton | generated | difference."""
import numpy as np
from PIL import Image, ImageDraw
import raster as R, source as V, extract as X
from fontTools.svgLib.path.parser import parse_path
from icons_io import CubicPen

def proof(orig_contours, parts, out, res=300):
    om = R.raster(orig_contours, res, 12)
    gm = R.raster(V.to_contours(V.generate(parts)), res, 12)
    W = res
    img = Image.new("RGB", (W * 4 + 30, W + 20), "white"); d = ImageDraw.Draw(img)
    def put(mask, x, color=(0, 0, 0)):
        a = np.full((res, res, 3), 255, np.uint8); a[mask] = color; img.paste(Image.fromarray(a), (x, 0))
    put(om, 0)
    # skeleton view: light original + centre lines
    a = np.full((res, res, 3), 255, np.uint8); a[om] = (215, 222, 235); img.paste(Image.fromarray(a), (W + 10, 0))
    s = res / 960
    for p in parts:
        pen = CubicPen(); parse_path(p["d"], pen)
        role = p.get("role") or {}
        if p.get("patch"):  # patches: orange (adds ink) or purple (removes ink)
            col = (235, 140, 0) if p["patch"]["op"] == "add" else (150, 60, 200)
        else:
            col = (200, 30, 30) if "cut" in role else (30, 120, 60) if role.get("knockout") else (40, 70, 200) if p["kind"] == "stroke" else (90, 90, 90)
        for c in pen.contours:
            pts = []
            for seg in c:
                for t in np.linspace(0, 1, 8):
                    mt = 1 - t; x = sum(w * q[0] for w, q in zip((mt**3, 3*mt*mt*t, 3*mt*t*t, t**3), seg)); y = sum(w * q[1] for w, q in zip((mt**3, 3*mt*mt*t, 3*mt*t*t, t**3), seg))
                    pts.append((W + 10 + x * s, (960 - y) * s))
            if len(pts) > 1: d.line(pts, fill=col, width=2)
    put(gm, 2 * W + 20)
    a = np.full((res, res, 3), 255, np.uint8); a[om & gm] = (200, 200, 200); a[om & ~gm] = (30, 90, 220); a[gm & ~om] = (220, 40, 40)
    img.paste(Image.fromarray(a), (3 * W + 30, 0))
    img.save(out)
