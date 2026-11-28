"""Contact sheet of candidate icons with their names, for picking test cases."""
import sys, json
from PIL import Image, ImageDraw
import icons_io as io, raster as R
src, which, out, n = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
items = json.load(open(src))[:n]
cols = 10; cell = 120; rows = (len(items) + cols - 1) // cols
img = Image.new("L", (cols*cell, rows*(cell+16)), 255); d = ImageDraw.Draw(img)
for i, f in enumerate(items):
    cs = io.ms_contours(f["name"]) if which == "material" else io.carbon_contours(f["name"])
    m = R.raster(cs, 96, steps=8)
    tile = Image.fromarray(((~m) * 255).astype("uint8"))
    x, y = (i % cols)*cell, (i // cols)*(cell+16)
    img.paste(tile, (x+12, y+4)); d.text((x+2, y+102), f"{i} {f['name'][:18]}", fill=0)
img.save(out)
