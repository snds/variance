"""Variance source model (v0.2) and a reference generator.

A source is a list of parts, bottom to top, exactly as a designer would lay
them out in Figma under Variance rules:

  {"id": "ring", "kind": "stroke", "d": "<svg path of the CENTRE LINE>",
   "width": 80, "align": "center|inside|outside", "cap": "butt|round|square",
   "join": "miter|round|bevel", "role": None}
  {"id": "dot",  "kind": "solid",  "d": "<svg path of the filled shape>"}

Roles (from the layer name):
  {"cut": gap, "side": "both|left|right", "hidden": False}
        cuts every part below it, with `gap` units of clearance, then draws itself
  {"knockout": True}   removes its own shape from everything below; draws nothing

The generator here uses Skia (pathops) for geometry at one weight. It answers
"can this source reproduce the icon?". Fixed point structure across weights is
a separate job, covered in research 01 and 02.
"""
import re, math
import pathops
from fontTools.svgLib.path.parser import parse_path
from icons_io import CubicPen

CAP = {"butt": pathops.LineCap.BUTT_CAP, "round": pathops.LineCap.ROUND_CAP, "square": pathops.LineCap.SQUARE_CAP}
JOIN = {"miter": pathops.LineJoin.MITER_JOIN, "round": pathops.LineJoin.ROUND_JOIN, "bevel": pathops.LineJoin.BEVEL_JOIN}

def path_from_d(d):
    p = pathops.Path(); pen = p.getPen(); parse_path(d, pen); return p

def fill(p):
    p.convertConicsToQuads()
    q = pathops.Path(); p.draw(q.getPen()); q.fillType = pathops.FillType.WINDING
    try: q.simplify()
    except pathops.PathOpsError: q = _rounded(q)  # see _rounded
    return q

def stroke_path(d, width, cap="butt", join="miter", align="center", miter=10):
    centre = path_from_d(d)
    if align == "center":
        s = path_from_d(d); s.stroke(width, CAP[cap], JOIN[join], miter); return fill(s)
    s = path_from_d(d); s.stroke(2 * width, CAP[cap], JOIN[join], miter); s = fill(s)
    inside = fill(centre)
    op = pathops.PathOp.INTERSECTION if align == "inside" else pathops.PathOp.DIFFERENCE
    return pathops.op(s, inside, op)

def part_shape(part, width=None):
    if part["kind"] == "solid":
        s = fill(path_from_d(part["d"]))
        return grow(s, part["grow"]) if part.get("grow") else s
    w = (width or part["width"]) + part.get("extra", 0)   # extra: a dot drawn wider than the stroke
    d = offset_d(part["d"], part["offset"]) if part.get("offset") else part["d"]
    return stroke_path(d, w, part.get("cap", "butt"), part.get("join", "miter"), part.get("align", "center"))

def grow(shape, d):
    """Every edge of a filled shape moves d units (+ out, - in)."""
    s = pathops.Path(); shape.draw(s.getPen()); s.stroke(2 * abs(d), CAP["butt"], JOIN["round"], 4); s = fill(s)
    return op(shape, s, pathops.PathOp.UNION if d > 0 else pathops.PathOp.DIFFERENCE)

def offset_d(d, off, steps=32):
    """The centre-line shifted sideways by `off` units (+ = to its left).
    Used when the two sides of a stroke move by different amounts: the
    stroke's anchor (research 07). Each segment is offset along its own
    normals; where two segments meet at a corner, the two offset lines are
    met at their intersection (a mitred offset), so corners don't spike."""
    def bez(seg, tt):
        p0, c1, c2, p3 = seg; mt = 1 - tt
        return tuple(mt**3 * a + 3 * mt * mt * tt * b + 3 * mt * tt * tt * e + tt**3 * g for a, b, e, g in zip(p0, c1, c2, p3))
    def tan(seg, tt):
        e = 1e-4; a, b = bez(seg, max(0, tt - e)), bez(seg, min(1, tt + e))
        dx, dy = b[0] - a[0], b[1] - a[1]; L = math.hypot(dx, dy)
        return (dx / L, dy / L) if L > 1e-12 else None
    def inter(p, u, q, v):
        den = u[0] * v[1] - u[1] * v[0]
        if abs(den) < 1e-6: return None
        s = ((q[0] - p[0]) * v[1] - (q[1] - p[1]) * v[0]) / den
        return (p[0] + u[0] * s, p[1] + u[1] * s)
    out = []
    for c in to_contours(path_from_d(d)):
        c = [s for s in c if math.dist(s[0], s[3]) > 1e-6 or math.dist(s[0], s[1]) > 1e-6]
        if not c: continue
        closed = math.dist(c[0][0], c[-1][3]) < 1e-6
        pieces = []
        for seg in c:
            pts = []
            for i in range(steps + 1):
                tt = i / steps; tg = tan(seg, tt)
                if tg is None: continue
                p = bez(seg, tt); pts.append((p[0] - tg[1] * off, p[1] + tg[0] * off, tg))
            if len(pts) >= 2: pieces.append(pts)
        if not pieces: continue
        joined = [list(pieces[0])]
        for pc in pieces[1:] + ([pieces[0]] if closed else []):
            prev = joined[-1]; a, b = prev[-1], pc[0]
            if math.dist(a[:2], b[:2]) > 1e-3:
                x = inter(a[:2], a[2], b[:2], b[2])
                if x is not None and math.dist(x, a[:2]) < 4 * abs(off) + 1:
                    prev[-1] = (x[0], x[1], a[2]); pc = [(x[0], x[1], b[2])] + pc[1:]
            joined.append(list(pc))
        if closed:   # the first piece was appended again to close the corner; fold it back
            first = joined.pop(); joined[0][0] = first[0]
        pts = [(p[0], p[1]) for pc in joined for p in pc]
        out.append("M" + " L".join(f"{x:.3f} {y:.3f}" for x, y in pts) + (" Z" if closed else ""))
    return " ".join(out)

def _rounded(p, q=1/16):
    """Copy of a path with coordinates on a 1/16-unit grid. Skia's boolean
    engine sometimes gives up on near-coincident edges; snapping them helps."""
    r = pathops.Path(); pen = r.getPen()
    from fontTools.pens.roundingPen import RoundingPen
    p.draw(RoundingPen(pen, roundFunc=lambda v: round(v / q) * q)); r.fillType = pathops.FillType.WINDING
    try: r.simplify()
    except pathops.PathOpsError: pass
    return r

def op(a, b, kind):
    """Boolean with fallbacks: exact, then inputs snapped to 1/16, 1/4 and
    1 unit. Skia gives up on some near-coincident or self-crossing edges."""
    try: return pathops.op(a, b, kind)
    except pathops.PathOpsError: pass
    for q in (1 / 16, 1 / 4, 1):
        try: return pathops.op(_rounded(a, q), _rounded(b, q), kind)
        except pathops.PathOpsError: continue
    raise pathops.PathOpsError("operation did not succeed")

def generate(parts):
    ink = pathops.Path()
    for part in parts:
        role = part.get("role") or {}
        shape = part_shape(part)
        if role.get("knockout"):
            ink = op(ink, shape, pathops.PathOp.DIFFERENCE); continue
        if "cut" in role:
            zone = stroke_path(part["d"], part["width"] + 2 * role["cut"], part.get("cap", "butt"), part.get("join", "miter")) if part["kind"] == "stroke" \
                   else outset(shape, role["cut"])
            if role.get("side", "both") != "both":
                zone = op(zone, half_plane(part["d"], role["side"]), pathops.PathOp.INTERSECTION)
            ink = op(ink, zone, pathops.PathOp.DIFFERENCE)
            if role.get("hidden"): continue
        ink = op(ink, shape, pathops.PathOp.UNION)
    return ink

def outset(shape, d):
    s = pathops.Path(); shape.draw(s.getPen()); s.stroke(2 * d, CAP["butt"], JOIN["round"], 4); s = fill(s)
    return pathops.op(shape, s, pathops.PathOp.UNION)

def half_plane(d, side):
    """Big polygon on one side of the cutter's first-to-last chord."""
    pen = CubicPen(); parse_path(d, pen)
    if not pen.contours: return pathops.Path()
    pts = [s[0] for c in pen.contours for s in c] + [pen.contours[-1][-1][3]]
    (x0, y0), (x1, y1) = pts[0], pts[-1]
    dx, dy = x1 - x0, y1 - y0; L = math.hypot(dx, dy)
    if L < 1e-6: return pathops.Path()
    dx, dy = dx / L * 4000, dy / L * 4000
    nx, ny = (-dy, dx) if side == "left" else (dy, -dx)
    p = pathops.Path(); pen2 = p.getPen()
    a = (x0 - dx, y0 - dy); b = (x1 + dx, y1 + dy)
    pen2.moveTo(a); pen2.lineTo(b); pen2.lineTo((b[0] + nx, b[1] + ny)); pen2.lineTo((a[0] + nx, a[1] + ny)); pen2.closePath()
    return fill(p)

def to_contours(path):
    path.convertConicsToQuads()
    pen = CubicPen(); path.draw(pen); return pen.contours
