"""Contact sheet: each glyph's default style against two other masters.
Grey = both, blue = default only, red = the other master only."""
import sys, numpy as np
from PIL import Image, ImageDraw
import extract as X, icons_io as IO

def tile(name, loc, size=180):
    a = X.mask_of(X.contours_to_path(IO.ms_contours(name)))
    b = X.mask_of(X.contours_to_path(IO.ms_contours(name, loc)))
    im = np.full(a.shape + (3,), 255, np.uint8)
    im[a & b] = (190, 190, 190); im[a & ~b] = (30, 90, 220); im[b & ~a] = (220, 40, 40)
    return Image.fromarray(im).resize((size, size), Image.LANCZOS)

def sheet(names, locs, out, size=180):
    W = len(locs) * (size + 8) + 8; H = len(names) * (size + 28) + 8
    img = Image.new("RGB", (W, H), "white"); d = ImageDraw.Draw(img)
    for r, n in enumerate(names):
        y = 8 + r * (size + 28); d.text((8, y), n, fill=(20, 20, 20))
        for c, l in enumerate(locs):
            img.paste(tile(n, l, size), (8 + c * (size + 8), y + 16)); d.text((12 + c * (size + 8), y + 18), l, fill=(90, 90, 90))
    img.save(out, optimize=True)

if __name__ == "__main__":
    sheet(sys.argv[3].split(","), sys.argv[2].split(","), sys.argv[1])
