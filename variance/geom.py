"""Fixed-structure outline geometry.

Everything here is a pure function of the source and the numbers passed in.
The number of points it emits depends only on the source (segment kinds,
corner angles, cap style), never on the widths, so every master of an icon
has the same contours, point counts, start points and directions. That is
what lets the masters interpolate (research 01's five rules).

Coordinates are SVG's: 960 x 960 em, y down. The font build flips y once.
"""
import math
from fontTools.svgLib.path.parser import parse_path
from fontTools.pens.basePen import BasePen

CURVE_STEPS = 10        # samples per curved segment (lines use 1)
CORNER_DEG = 10         # turns sharper than this are corners
ROUND_JOIN_PTS = 5      # points inserted on the outer side of a round corner
ROUND_CAP_PTS = 9       # points around a round cap
DOT_PTS = 24            # points around a dot

# ---- Parsing -----------------------------------------------------------------

class _Pen(BasePen):
    """Collects contours as cubic segments (p0, c1, c2, p3); lines are kept as
    cubics with their handles on the line, and flagged by `is_line`."""
    def __init__(self):
        super().__init__(None); self.contours = []; self.cur = None; self.start = None; self.closed = []
    def _moveTo(self, p):
        self._flush(); self.cur = []; self.start = p; self.last = p
    def _lineTo(self, p):
        a = self.last; self.cur.append((a, _lerp(a, p, 1 / 3), _lerp(a, p, 2 / 3), p)); self.last = p
    def _curveToOne(self, c1, c2, p):
        self.cur.append((self.last, c1, c2, p)); self.last = p
    def _qCurveToOne(self, c, p):
        a = self.last
        self._curveToOne(_lerp(a, c, 2 / 3), _lerp(p, c, 2 / 3), p)
    def _closePath(self):
        if self.cur is not None and math.dist(self.last, self.start) > 1e-6:
            self._lineTo(self.start)
        self._flush(True)
    def _endPath(self):
        self._flush(False)
    def _flush(self, closed=False):
        if self.cur is not None:
            self.contours.append(self.cur); self.closed.append(closed)
        self.cur = None

def _lerp(a, b, t): return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)

def contours_of(d):
    """SVG path data -> [(segments, closed, dot_point_or_None)].
    Zero-length segments are dropped. A contour with no length left is a dot."""
    pen = _Pen(); parse_path(d, pen); pen._flush(False)
    out = []
    for segs, closed in zip(pen.contours, pen.closed):
        keep = [s for s in segs if _seg_len(s) > 1e-6]
        if keep:
            gap = math.dist(keep[0][0], keep[-1][3])
            if gap < 1.0 and len(keep) > 1:
                # ends that meet within a unit are one closed contour (an
                # export often leaves a tiny rounding gap instead of Z)
                closed = True
                a = keep[-1]; keep[-1] = (a[0], a[1], a[2], keep[0][0])
            out.append((keep, closed, None))
        elif segs:
            out.append(([], False, segs[0][0]))
        elif pen.start is not None and not segs:
            pass
    return out

def _seg_len(s): return math.dist(s[0], s[1]) + math.dist(s[1], s[2]) + math.dist(s[2], s[3])

def is_line(s):
    p, c1, c2, q = s
    L = math.dist(p, q)
    if L < 1e-9: return False
    def off(c):  # distance of a handle from the chord
        return abs((q[0] - p[0]) * (c[1] - p[1]) - (q[1] - p[1]) * (c[0] - p[0])) / L
    return off(c1) < 0.01 and off(c2) < 0.01

def bez(s, t):
    p0, c1, c2, p3 = s; mt = 1 - t
    return (mt ** 3 * p0[0] + 3 * mt * mt * t * c1[0] + 3 * mt * t * t * c2[0] + t ** 3 * p3[0],
            mt ** 3 * p0[1] + 3 * mt * mt * t * c1[1] + 3 * mt * t * t * c2[1] + t ** 3 * p3[1])

def tangent(s, t):
    """Unit tangent at t, robust at ends where a handle sits on the point."""
    for e in (1e-4, 1e-3, 1e-2, 5e-2):
        a, b = bez(s, max(0.0, t - e)), bez(s, min(1.0, t + e))
        dx, dy = b[0] - a[0], b[1] - a[1]; L = math.hypot(dx, dy)
        if L > 1e-9: return (dx / L, dy / L)
    dx, dy = s[3][0] - s[0][0], s[3][1] - s[0][1]; L = math.hypot(dx, dy) or 1.0
    return (dx / L, dy / L)

def left_of(t): return (t[1], -t[0])   # left of the direction of travel, on screen (y down)

def steps_of(s): return 1 if is_line(s) else CURVE_STEPS

def signed_area(pts):
    return 0.5 * sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1]))

def turn(t0, t1):
    """Signed turn from direction t0 to t1, radians (+ = toward the left side)."""
    cross = t0[0] * t1[1] - t0[1] * t1[0]; dot = t0[0] * t1[0] + t0[1] * t1[1]
    return -math.atan2(cross, dot)   # y down: a screen-left turn has negative cross

def contour_length(segs):
    total = 0.0
    for s in segs:
        n = 16; prev = s[0]
        for i in range(1, n + 1):
            q = bez(s, i / n); total += math.dist(prev, q); prev = q
    return total

# ---- Offsetting --------------------------------------------------------------

def _intersect(p, u, q, v):
    den = u[0] * v[1] - u[1] * v[0]
    if abs(den) < 1e-9: return None
    s = ((q[0] - p[0]) * v[1] - (q[1] - p[1]) * v[0]) / den
    return (p[0] + u[0] * s, p[1] + u[1] * s)

def offset_side(segs, closed, dist, side, join="round"):
    """One side of a stroke: the centre-line moved `dist(si)` units to the
    given side ('left' or 'right'), segment by segment.

    Structure is fixed by the source: each segment gives steps_of(seg)+1
    points; at each corner the outer side gets ROUND_JOIN_PTS extra points for
    a round join (or for a miter, the same number sitting on the miter point),
    and the inner side meets at the two offset lines' intersection. Which side
    is outer depends only on the centre-line's turn direction.
    Returns a list of points."""
    sgn = 1.0 if side == "left" else -1.0
    pieces = []
    for si, s in enumerate(segs):
        o = sgn * dist(si); n = steps_of(s); pts = []
        for i in range(n + 1):
            t = i / n; p = bez(s, t); tg = tangent(s, t); nl = left_of(tg)
            pts.append((p[0] + nl[0] * o, p[1] + nl[1] * o))
        pieces.append(pts)
    joints = list(range(len(segs) - 1)) + ([len(segs) - 1] if closed else [])
    extra = {}
    for j in joints:
        a, b = segs[j], segs[(j + 1) % len(segs)]
        t0, t1 = tangent(a, 1.0), tangent(b, 0.0)
        th = turn(t0, t1)
        if abs(th) < math.radians(CORNER_DEG): continue
        # th > 0 turns toward the left: the right side is outer.
        outer = (th < 0) == (side == "left")
        oa, ob = sgn * dist(j), sgn * dist((j + 1) % len(segs))
        pa, pb = pieces[j][-1], pieces[(j + 1) % len(segs)][0]
        v = a[3]
        if outer and join == "round":
            r = (abs(oa) + abs(ob)) / 2
            a0 = math.atan2(pa[1] - v[1], pa[0] - v[0]); a1 = math.atan2(pb[1] - v[1], pb[0] - v[0])
            if abs(oa) < 1e-9 and abs(ob) < 1e-9:
                arc = [v] * ROUND_JOIN_PTS
            else:
                da = a1 - a0
                while da > math.pi: da -= 2 * math.pi
                while da < -math.pi: da += 2 * math.pi
                arc = [(v[0] + r * math.cos(a0 + da * k / (ROUND_JOIN_PTS + 1)),
                        v[1] + r * math.sin(a0 + da * k / (ROUND_JOIN_PTS + 1))) for k in range(1, ROUND_JOIN_PTS + 1)]
            extra[j] = arc
        else:
            x = _intersect(pa, t0, pb, t1)
            lim = 4 * max(abs(oa), abs(ob)) + 1
            if x is not None and math.dist(x, v) < lim:
                pieces[j][-1] = x; pieces[(j + 1) % len(segs)][0] = x
            if outer:
                extra[j] = [pieces[j][-1]] * ROUND_JOIN_PTS
    out = []
    for i, pc in enumerate(pieces):
        out.extend(pc)
        if i in extra: out.extend(extra[i])
    if closed and (len(segs) - 1) in extra:
        # the closing corner's extra points were appended after the last
        # piece; they stay there, between the last and first pieces
        pass
    return out

def cap_points(a, b, t, cap, ext):
    """Points between side end a and side end b around an end facing t.
    Fixed count per cap style. ext = extra length past the end (units)."""
    if cap == "round":
        cx, cy = (a[0] + b[0]) / 2 + t[0] * ext, (a[1] + b[1]) / 2 + t[1] * ext
        r = math.dist(a, b) / 2
        a0 = math.atan2(a[1] - (b[1] + a[1]) / 2, a[0] - (b[0] + a[0]) / 2)
        # sweep the half turn that passes through t
        mid = (math.cos(a0 + math.pi / 2), math.sin(a0 + math.pi / 2))
        sg = 1 if mid[0] * t[0] + mid[1] * t[1] > 0 else -1
        return [(cx + r * math.cos(a0 + sg * math.pi * k / (ROUND_CAP_PTS + 1)),
                 cy + r * math.sin(a0 + sg * math.pi * k / (ROUND_CAP_PTS + 1))) for k in range(1, ROUND_CAP_PTS + 1)]
    return [(a[0] + t[0] * ext, a[1] + t[1] * ext), (b[0] + t[0] * ext, b[1] + t[1] * ext)]

def stroke_contours(segs, closed, left, right, cap="round", join="round", ends=(0.0, 0.0)):
    """Outline of one stroke contour. left(si), right(si): distances of each
    side from the centre-line. Closed -> two contours (outer, inner);
    open -> one ring. ends = (start, end) extra length (+ longer, - shorter)."""
    L = offset_side(segs, closed, left, "left", join)
    R = offset_side(segs, closed, right, "right", join)
    if closed:
        return [L, R[::-1]]
    t0 = tangent(segs[0], 0.0); t1 = tangent(segs[-1], 1.0)
    n = len(segs) - 1
    def ext(w, e):
        base = w if cap == "square" else 0.0
        return base + e
    we = (left(n) + right(n)) / 2; ws = (left(0) + right(0)) / 2
    es, ee = ends
    xe, xs = ext(we, ee), ext(ws, es)
    if cap == "round":
        xe, xs = ee, es
    # a shortened end moves the side ends back along the stroke, so the
    # outline never folds over itself
    if xe < 0:
        L[-1] = (L[-1][0] + t1[0] * xe, L[-1][1] + t1[1] * xe); R[-1] = (R[-1][0] + t1[0] * xe, R[-1][1] + t1[1] * xe); xe_cap = 0.0
    else: xe_cap = xe
    if xs < 0:
        L[0] = (L[0][0] - t0[0] * xs, L[0][1] - t0[1] * xs); R[0] = (R[0][0] - t0[0] * xs, R[0][1] - t0[1] * xs); xs_cap = 0.0
    else: xs_cap = xs
    ring = list(L) + cap_points(L[-1], R[-1], t1, cap, xe_cap) + R[::-1] + cap_points(R[0], L[0], (-t0[0], -t0[1]), cap, xs_cap)
    return [ring]

def dot_contour(c, r):
    return [(c[0] + r * math.cos(2 * math.pi * k / DOT_PTS), c[1] + r * math.sin(2 * math.pi * k / DOT_PTS)) for k in range(DOT_PTS)]

def solid_contour(segs, dist):
    """A filled contour whose segments each move `dist(si)` units outward."""
    pts = [bez(s, 0) for s in segs]
    # outward = left when the contour runs counter-clockwise on screen
    side = "right" if signed_area(pts) > 0 else "left"
    if abs(signed_area(pts)) < 1e-9: side = "left"
    return offset_side(segs, True, dist, side, "miter")

def path_d(contours, nd=1):
    """Contours of points -> SVG path data."""
    out = []
    for c in contours:
        if not c: continue
        out.append("M" + " L".join(f"{x:.{nd}f} {y:.{nd}f}" for x, y in c) + "Z")
    return "".join(out)

def seg_d(s, nd=1):
    p, c1, c2, q = s
    if is_line(s): return f"M{p[0]:.{nd}f} {p[1]:.{nd}f}L{q[0]:.{nd}f} {q[1]:.{nd}f}"
    return f"M{p[0]:.{nd}f} {p[1]:.{nd}f}C{c1[0]:.{nd}f} {c1[1]:.{nd}f} {c2[0]:.{nd}f} {c2[1]:.{nd}f} {q[0]:.{nd}f} {q[1]:.{nd}f}"
