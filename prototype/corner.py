# How far does the font (which adds independent per-axis deltas) drift from
# what the generator would draw directly at an axis corner?
import gen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from fontTools.pens.recordingPen import RecordingPen
from fontTools.cu2qu import curves_to_quadratic
vf = TTFont("build/proto.ttf")
for loc in [dict(wght=700, opsz=20, GRAD=200, FILL=0), dict(wght=700, opsz=20, GRAD=0, FILL=0),
            dict(wght=100, opsz=48, GRAD=-50, FILL=0), dict(wght=700, opsz=24, GRAD=0, FILL=1)]:
    inst = instantiateVariableFont(TTFont("build/proto.ttf"), dict(loc))
    g = inst["glyf"]["check_circle"]; coords, _, _ = g.getCoordinates(inst["glyf"])
    # direct: rebuild a single master at this location with the same pipeline
    gen.MASTERS = [dict(gen.DEFAULT), dict(loc)]
    fonts = gen.build_masters(); d = fonts[1][1]["glyf"]["check_circle"]
    dc, _, _ = d.getCoordinates(fonts[1][1]["glyf"])
    if len(dc) != len(coords): print(loc, "point count differs", len(dc), len(coords)); continue
    dev = max(max(abs(a[0]-b[0]), abs(a[1]-b[1])) for a, b in zip(coords, dc))
    print(loc, "max drift", dev, "units =", round(dev/40, 2), "px at 24px")
