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
    if part["kind"] == "solid": return fill(path_from_d(part["d"]))
    return stroke_path(part["d"], width or part["width"], part.get("cap", "butt"), part.get("join", "miter"), part.get("align", "center"))

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
    try: return pathops.op(a, b, kind)
    except pathops.PathOpsError:
        return pathops.op(_rounded(a), _rounded(b), kind)

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
