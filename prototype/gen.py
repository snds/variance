"""Prototype: skeleton icons -> generated masters -> variable TTF.

Every master comes from one pure function, outline(skeleton, axes). Topology
(contour count, node count, start point, direction) is fixed by the skeleton,
so masters are compatible by construction and a rebuild is byte-identical.
Units: UPM 960, 24 px grid => 40 units per px. y-up font coordinates.
"""
import math, os, sys, hashlib, io
from fontTools.misc.timeTools import timestampSinceEpoch
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.cu2qu import curves_to_quadratic
from fontTools.designspaceLib import DesignSpaceDocument, AxisDescriptor, SourceDescriptor
from fontTools import varLib

UPM = 960
# Pinned build time. Font files carry created/modified dates; leaving them
# live makes every build differ. Honour SOURCE_DATE_EPOCH, else a fixed date.
BUILD_TIME = timestampSinceEpoch(int(os.environ.get("SOURCE_DATE_EPOCH", "1764115200")))
K = 0.5522847498  # circle kappa for a 90 degree cubic arc

# ---- Icon sources: skeletons, not outlines -------------------------------
# "ring": closed path, stroke grows INSIDE so the silhouette (outer edge) holds.
# "line": open path, stroke CENTERED on the skeleton, butt caps, round joins.
ICONS = {
    "check_circle": {"cp": 0xE000, "parts": [
        {"kind": "ring", "c": (480, 480), "r": 360},
        {"kind": "line", "pts": [(300, 490), (420, 370), (660, 610)]},
    ]},
    "radio_button": {"cp": 0xE001, "parts": [
        {"kind": "ring", "c": (480, 480), "r": 360},
    ]},
}

# ---- Axis -> geometry rules (the "corrections"), all pure functions --------
def lerp(a, b, t): return a + (b - a) * t
def piecewise(x, table):
    for (x0, y0), (x1, y1) in zip(table, table[1:]):
        if x0 <= x <= x1: return lerp(y0, y1, (x - x0) / (x1 - x0))
    raise ValueError(x)

def stroke_width(a):
    w = piecewise(a["wght"], [(100, 27), (400, 80), (700, 133)])     # 0.67/2/3.33 px
    w *= piecewise(a["opsz"], [(20, 1.10), (24, 1.0), (48, 0.85)])   # optical size
    w += piecewise(a["GRAD"], [(-50, -8), (0, 0), (200, 27)])        # grade, no size change
    return w

# ---- Fixed-topology outline builders -------------------------------------
def circle(c, r, cw):
    """4 cubic segments, start at top. cw=True => clockwise in y-up coords."""
    cx, cy = c; k = K * r
    top, right, bot, left = (cx, cy + r), (cx + r, cy), (cx, cy - r), (cx - r, cy)
    segs = [ (top, (cx + k, cy + r), (cx + r, cy + k), right),
             (right, (cx + r, cy - k), (cx + k, cy - r), bot),
             (bot, (cx - k, cy - r), (cx - r, cy - k), left),
             (left, (cx - r, cy + k), (cx - k, cy + r), top) ]
    if not cw:
        segs = [(s[3], s[2], s[1], s[0]) for s in reversed(segs)]
    return segs  # list of cubic (p0, c1, c2, p3); lines are degenerate cubics

def line_seg(p, q):
    return (p, lerp2(p, q, 1/3), lerp2(p, q, 2/3), q)
def lerp2(p, q, t): return (lerp(p[0], q[0], t), lerp(p[1], q[1], t))
def add(p, v, s=1): return (p[0] + v[0]*s, p[1] + v[1]*s)
def unit_normal(p, q):
    dx, dy = q[0]-p[0], q[1]-p[1]; L = math.hypot(dx, dy)
    return (-dy/L, dx/L)  # left normal
def intersect(p1, d1, p2, d2):
    den = d1[0]*d2[1] - d1[1]*d2[0]
    t = ((p2[0]-p1[0])*d2[1] - (p2[1]-p1[1])*d2[0]) / den
    return (p1[0] + d1[0]*t, p1[1] + d1[1]*t)

def polyline3(pts, h):
    """3-point open stroke, half-width h. Outer side of the join is a round arc
    (one cubic), inner side is the miter intersection. Same node count at any h."""
    a, b, c = pts
    n0, n1 = unit_normal(a, b), unit_normal(b, c)
    turn = (b[0]-a[0])*(c[1]-b[1]) - (b[1]-a[1])*(c[0]-b[0])  # >0 = left turn
    s = -1 if turn > 0 else 1  # outer side sign
    o0a, o0b = add(a, n0, s*h), add(b, n0, s*h)
    o1b, o1c = add(b, n1, s*h), add(c, n1, s*h)
    i0a, i1c = add(a, n0, -s*h), add(c, n1, -s*h)
    inner = intersect(i0a, (b[0]-a[0], b[1]-a[1]), i1c, (b[0]-c[0], b[1]-c[1]))
    theta = math.acos(max(-1, min(1, n0[0]*n1[0] + n0[1]*n1[1])))
    k = 4/3 * math.tan(theta/4) * h
    d0 = ((b[0]-a[0]), (b[1]-a[1])); L0 = math.hypot(*d0); d0 = (d0[0]/L0, d0[1]/L0)
    d1 = ((c[0]-b[0]), (c[1]-b[1])); L1 = math.hypot(*d1); d1 = (d1[0]/L1, d1[1]/L1)
    arc = (o0b, add(o0b, d0, k), add(o1b, d1, -k), o1b)
    segs = [line_seg(o0a, o0b), arc, line_seg(o1b, o1c), line_seg(o1c, i1c),
            line_seg(i1c, inner), line_seg(inner, i0a), line_seg(i0a, o0a)]
    return segs

def signed_area(segs):
    return sum(p[0]*q[1] - q[0]*p[1] for p, _, _, q in segs) / 2

GAP = 40  # 1 px minimum clearance between a detail and the ring's inner edge

def detail_scale(icon, w):
    """Clearance correction. As the ring thickens inward, the free space inside
    shrinks, so the inner detail scales about its own centre to keep the same
    ratio of free space it has at the default weight. A pure function of w, so
    re-running it on the same input can never drift."""
    ring = next((p for p in icon["parts"] if p["kind"] == "ring"), None)
    if ring is None: return 1.0
    free = lambda w: ring["r"] - 1.5 * w - GAP
    return max(0.5, min(1.1, free(w) / free(80)))

def scale_pts(pts, s):
    cx = sum(p[0] for p in pts) / len(pts); cy = sum(p[1] for p in pts) / len(pts)
    return [(cx + (x - cx) * s, cy + (y - cy) * s) for x, y in pts]

def outline(icon, a):
    """Pure function: skeleton + axis location -> list of contours (cubics)."""
    w = stroke_width(a); contours = []
    for part in icon["parts"]:
        if part["kind"] == "ring":
            contours.append(circle(part["c"], part["r"], cw=True))
            # FILL: the counter shrinks to a point; nodes are kept, never deleted.
            r_in = lerp(part["r"] - w, 0.0, a["FILL"])
            contours.append(circle(part["c"], r_in, cw=False))
        else:
            segs = polyline3(scale_pts(part["pts"], detail_scale(icon, w)), w / 2)
            # Knockout detail: wound COUNTER-clockwise. Under the nonzero rule it
            # is ink inside the empty counter (FILL=0) and a hole in the solid
            # disc (FILL=1), with no node added, removed or reversed.
            if signed_area(segs) < 0:
                segs = [(s[3], s[2], s[1], s[0]) for s in reversed(segs)]
            contours.append(segs)
    return contours

# ---- Masters ---------------------------------------------------------------
DEFAULT = {"FILL": 0, "wght": 400, "GRAD": 0, "opsz": 24}
AXES = [("FILL", 0, 0, 1), ("wght", 100, 400, 700), ("GRAD", -50, 0, 200), ("opsz", 20, 24, 48)]
MASTERS = [dict(DEFAULT)] + [dict(DEFAULT, **{t: v}) for t, lo, d, hi in AXES for v in (lo, hi) if v != d]

def is_line(s):
    p, c1, c2, q = s
    return all(abs(c[0]-l[0]) < 1e-6 and abs(c[1]-l[1]) < 1e-6
               for c, l in ((c1, lerp2(p, q, 1/3)), (c2, lerp2(p, q, 2/3))))

def build_masters():
    """Convert cubics to quadratics *jointly across masters* (cu2qu) so every
    master gets the same number of quadratic pieces, then round to integers."""
    fonts = []
    per_master = {name: [outline(ic, m) for m in MASTERS] for name, ic in ICONS.items()}
    glyph_sets = [{} for _ in MASTERS]
    for name, outs in per_master.items():
        pens = [TTGlyphPen(None) for _ in MASTERS]
        for ci in range(len(outs[0])):
            for pen, o in zip(pens, outs):
                pen.moveTo(tuple(round(v) for v in o[ci][0][0]))
            for si in range(len(outs[0][ci])):
                segs = [o[ci][si] for o in outs]
                if all(is_line(s) for s in segs):
                    for pen, s in zip(pens, segs): pen.lineTo(tuple(round(v) for v in s[3]))
                else:
                    quads = curves_to_quadratic(segs, [1.0] * len(segs))
                    for pen, q in zip(pens, quads):
                        pen.qCurveTo(*[tuple(round(v) for v in p) for p in q[1:]])
            for pen in pens: pen.closePath()
        for gs, pen in zip(glyph_sets, pens): gs[name] = pen.glyph()
    for m, gs in zip(MASTERS, glyph_sets):
        fb = FontBuilder(UPM, isTTF=True)
        order = [".notdef"] + list(ICONS)
        fb.setupGlyphOrder(order)
        fb.setupCharacterMap({ic["cp"]: n for n, ic in ICONS.items()})
        gs[".notdef"] = TTGlyphPen(None).glyph()
        fb.setupGlyf(gs)
        fb.setupHorizontalMetrics({n: (UPM, 0) for n in order})
        fb.setupHorizontalHeader(ascent=UPM, descent=0)
        fb.setupNameTable({"familyName": "Proto Symbols", "styleName": "Regular"})
        fb.setupOS2(sTypoAscender=UPM, sTypoDescender=0, usWinAscent=UPM, usWinDescent=0)
        fb.setupPost()
        # Pin timestamps: without this, every build differs (head.created/modified).
        fb.font["head"].created = fb.font["head"].modified = BUILD_TIME
        fonts.append((m, fb.font))
    return fonts

def build_variable(path):
    ds = DesignSpaceDocument()
    for tag, lo, d, hi in AXES:
        ax = AxisDescriptor(); ax.tag = ax.name = tag
        ax.minimum, ax.default, ax.maximum = lo, d, hi; ds.addAxis(ax)
    masters = build_masters()
    for i, (loc, font) in enumerate(masters):
        s = SourceDescriptor(); s.font = font; s.location = dict(loc)
        s.name = s.filename = f"m{i}"; ds.addSource(s)
    vf, _, _ = varLib.build(ds)
    vf["head"].created = vf["head"].modified = BUILD_TIME
    buf = io.BytesIO(); vf.save(buf); data = buf.getvalue()
    open(path, "wb").write(data)
    # Masters are written beside the font so fontTools.varLib.interpolatable can check them.
    out = os.path.dirname(os.path.abspath(path))
    for i, (loc, font) in enumerate(masters): font.save(os.path.join(out, f"master{i}.ttf"))
    return hashlib.sha256(data).hexdigest(), len(data)

if __name__ == "__main__":
    os.makedirs("build", exist_ok=True)
    print(build_variable(sys.argv[1] if len(sys.argv) > 1 else "build/proto.ttf"))
