"""Research 02: boolean shapes from stroke skeletons.

Three test icons, each needing a boolean:
  A  magnifier  : ring + handle                -> UNION
  B  slash_off  : ring, minus a gap around a slash, plus the slash -> SUBTRACT with clearance
  C  badge      : square outline, minus a gap around a dot, plus the dot -> SUBTRACT with clearance
  D  contrast   : ring + a half disc clipped to the ring's counter -> INTERSECT (clip)

Methods tried for each:
  M1 overlap    : keep parts as separate overlapping contours; let the nonzero fill merge them.
  M2 winding    : express subtraction as a reversed contour (a "negative" shape).
  M3 per-master : run a real boolean (Skia pathops) on every master separately.
  M4 skeleton   : resolve the boolean in skeleton space: trim the skeleton where the cutter
                  is and give the cut ends a cap shaped like the cutter. Point count fixed.
  M5 repair     : M3, then reorder contours and realign start points to match the default.

Each method is scored against the TRUE boolean, computed fresh at every weight:
  compatible : same contour count, point count and point types in every master
  error      : px^2 (at 24 px) where the font's result and the true boolean disagree,
               sampled every 0.1 px, at 9 weights including in-betweens
"""
import math, json, sys
import pathops
from fontTools.pens.areaPen import AreaPen

PX = 40.0  # units per px at 24 px on a 960 grid
GAP = 40.0  # 1 px clearance

def stroke_width(wght):
    if wght <= 400: return 27 + (80 - 27) * (wght - 100) / 300
    return 80 + (133 - 80) * (wght - 400) / 300

# ---------- geometry helpers (contours = lists of cubic segments) ----------
def L(p, q): return (p, (p[0]+(q[0]-p[0])/3, p[1]+(q[1]-p[1])/3), (p[0]+2*(q[0]-p[0])/3, p[1]+2*(q[1]-p[1])/3), q)
def pol(c, r, a): return (c[0] + r*math.cos(a), c[1] + r*math.sin(a))
def arc(c, r, a0, a1, n):
    """n cubics from angle a0 to a1 (radians, any direction)."""
    out = []; step = (a1 - a0) / n; k = 4/3 * math.tan(step/4) * r
    for i in range(n):
        s, e = a0 + i*step, a0 + (i+1)*step
        p, q = pol(c, r, s), pol(c, r, e)
        out.append((p, (p[0] - k*math.sin(s), p[1] + k*math.cos(s)), (q[0] + k*math.sin(e), q[1] - k*math.cos(e)), q))
    return out
def circle(c, r, ccw=True):
    return arc(c, r, math.pi/2, math.pi/2 + (2 if ccw else -2)*math.pi, 4)
def reverse(cont): return [(s[3], s[2], s[1], s[0]) for s in reversed(cont)]
def rect_along(p, q, h):
    dx, dy = q[0]-p[0], q[1]-p[1]; l = math.hypot(dx, dy); nx, ny = -dy/l*h, dx/l*h
    a, b, c, d = (p[0]+nx, p[1]+ny), (q[0]+nx, q[1]+ny), (q[0]-nx, q[1]-ny), (p[0]-nx, p[1]-ny)
    return [L(a, b), L(b, c), L(c, d), L(d, a)]  # clockwise (y-up)

def to_path(contours):
    p = pathops.Path()
    for cont in contours:
        p.moveTo(*cont[0][0])
        for s in cont: p.cubicTo(*s[1], *s[2], *s[3])
        p.close()
    return p
def signed(cont):
    pen = AreaPen(); to_path([cont]).draw(pen); return pen.value  # < 0 = clockwise (y-up)
def area(path):
    pen = AreaPen(); path.draw(pen); return abs(pen.value)
def fill(contours):
    """What a font rasterizer shows: the nonzero fill of all contours."""
    p = to_path(contours); p.fillType = pathops.FillType.WINDING; p.simplify(); return p
def op(a, b, kind):
    return pathops.op(a, b, kind)
# ---------- scoring by point sampling ----------
# Skia's boolean ops become unreliable when two shapes' edges nearly coincide,
# which is exactly the case when comparing a good construction to the truth.
# So the score samples a grid of points and tests each one with a winding number.
import numpy as np
STEP = 4.0  # sample every 4 units = 0.1 px at 24 px
_xs = np.arange(STEP/2, 960, STEP)
GX, GY = np.meshgrid(_xs, _xs)
GX, GY = GX.ravel(), GY.ravel()

def flatten(cont, n=24):
    pts = []
    for p0, c1, c2, p3 in cont:
        for i in range(n):
            t = i / n; mt = 1 - t
            pts.append((mt**3*p0[0] + 3*mt*mt*t*c1[0] + 3*mt*t*t*c2[0] + t**3*p3[0],
                        mt**3*p0[1] + 3*mt*mt*t*c1[1] + 3*mt*t*t*c2[1] + t**3*p3[1]))
    return np.array(pts)

def winding(conts):
    wn = np.zeros(GX.shape, dtype=int)
    for cont in conts:
        P = flatten(cont); Q = np.roll(P, -1, axis=0)
        for (x0, y0), (x1, y1) in zip(P, Q):
            up = (y0 <= GY) & (y1 > GY); down = (y0 > GY) & (y1 <= GY)
            cross = (x1 - x0) * (GY - y0) - (GX - x0) * (y1 - y0)
            wn += (up & (cross > 0)).astype(int) - (down & (cross < 0)).astype(int)
    return wn

def ink(conts):
    """What a font rasterizer shows: nonzero fill of all contours."""
    return winding(conts) != 0

def err_px2(mask_a, mask_b):
    return float(np.count_nonzero(mask_a != mask_b)) * STEP * STEP / (PX * PX)

# ---------- the icons: parts as functions of stroke width w ----------
def ring_band(c, r, w):  # closed stroke, inside-aligned
    return [circle(c, r, ccw=False), circle(c, r - w, ccw=True)]

# A magnifier
A_C, A_R, A_DIR, A_END = (400, 560), 240, -math.pi/4, (800, 160)
def A_handle(w):  # centred open stroke from the ring's mid-band to the end
    return rect_along(pol(A_C, A_R - w/2, A_DIR), A_END, w/2)
def A_true(w): return op(fill(ring_band(A_C, A_R, w)), fill([A_handle(w)]), pathops.PathOp.UNION)

# B slash_off
B_C, B_R, B_P, B_Q = (480, 480), 360, (160, 800), (800, 160)
def B_true(w):
    ring = fill(ring_band(B_C, B_R, w))
    gap = fill([rect_along(B_P, B_Q, w/2 + GAP)])
    return op(op(ring, gap, pathops.PathOp.DIFFERENCE), fill([rect_along(B_P, B_Q, w/2)]), pathops.PathOp.UNION)

# C badge (square outline with a notched dot at the top-right corner)
C_LO, C_HI, C_DOT = 120, 840, (780, 780)
def C_dot_r(w): return 120 + 0.25 * (w - 80)  # solid part gains a quarter of the stroke change
def C_square(w):
    o = [L((C_LO, C_HI), (C_HI, C_HI)), L((C_HI, C_HI), (C_HI, C_LO)), L((C_HI, C_LO), (C_LO, C_LO)), L((C_LO, C_LO), (C_LO, C_HI))]
    a, b = C_LO + w, C_HI - w
    i = [L((a, b), (a, a)), L((a, a), (b, a)), L((b, a), (b, b)), L((b, b), (a, b))]
    return [o, i]
def C_true(w):
    sq = fill(C_square(w))
    notch = fill([circle(C_DOT, C_dot_r(w) + GAP)])
    return op(op(sq, notch, pathops.PathOp.DIFFERENCE), fill([circle(C_DOT, C_dot_r(w))]), pathops.PathOp.UNION)

# D contrast (ring + left half disc that fills the ring's counter)
D_C, D_R = (480, 480), 360
def D_true(w):
    ring = fill(ring_band(D_C, D_R, w))
    half = fill([[*arc(D_C, D_R, math.pi/2, 3*math.pi/2, 2), L(pol(D_C, D_R, 3*math.pi/2), pol(D_C, D_R, math.pi/2))]])
    return op(ring, half, pathops.PathOp.UNION)

# ---------- methods: each returns contours for a given w ----------
def M1(case, w):
    if case == "A": return ring_band(A_C, A_R, w) + [A_handle(w)]
    if case == "B": return ring_band(B_C, B_R, w) + [rect_along(B_P, B_Q, w/2)]  # gap can't be expressed
    if case == "C": return C_square(w) + [circle(C_DOT, C_dot_r(w), ccw=False)]    # gap can't be expressed
    if case == "D":  # half disc overlaps into the band; radius tracks the band's middle
        r = D_R - w/2
        return ring_band(D_C, D_R, w) + [reverse([*arc(D_C, r, math.pi/2, 3*math.pi/2, 2), L(pol(D_C, r, 3*math.pi/2), pol(D_C, r, math.pi/2))])]

def M2(case, w):
    if case == "A": return M1("A", w)
    if case == "B": return ring_band(B_C, B_R, w) + [reverse(rect_along(B_P, B_Q, w/2 + GAP)), rect_along(B_P, B_Q, w/2)]
    if case == "C": return C_square(w) + [reverse(circle(C_DOT, C_dot_r(w) + GAP, ccw=False)), circle(C_DOT, C_dot_r(w), ccw=False)]
    if case == "D": return M1("D", w)

def M3(case, w):
    """Real boolean per master (Skia pathops). Returns cubic contours plus the
    original segment kinds, so we can tell whether masters line up."""
    path = {"A": A_true, "B": B_true, "C": C_true, "D": D_true}[case](w)
    path.convertConicsToQuads()
    conts, kinds, cur, ck, last = [], [], [], [], None
    for verb, pts in path:
        name = verb.name
        if name == "MOVE": cur, ck, last = [], [], pts[0]
        elif name == "LINE": cur.append(L(last, pts[0])); ck.append("L"); last = pts[0]
        elif name == "QUAD":
            c, q = pts; p = last
            cur.append((p, (p[0]+2/3*(c[0]-p[0]), p[1]+2/3*(c[1]-p[1])), (q[0]+2/3*(c[0]-q[0]), q[1]+2/3*(c[1]-q[1])), q)); ck.append("Q"); last = q
        elif name == "CUBIC": cur.append((last, *pts)); ck.append("C"); last = pts[-1]
        elif name == "CLOSE":
            if cur and cur[-1][3] != cur[0][0]: cur.append(L(cur[-1][3], cur[0][0])); ck.append("L")
            conts.append(cur); kinds.append(tuple(ck))
    return conts, tuple(kinds)

def M5(case, w, ref=None):
    """Per-master boolean, then automatic repair: reorder contours to match the
    default master by centroid, and rotate each start point to the one nearest
    the default's. This is what a 'fix it after the fact' pipeline would do."""
    conts, kinds = M3(case, w)
    if ref is None: return conts, kinds
    ref_conts, _ = ref
    cen = lambda c: (sum(s[0][0] for s in c)/len(c), sum(s[0][1] for s in c)/len(c))
    order = []
    for rc in ref_conts:
        rcx = cen(rc)
        best = min((i for i in range(len(conts)) if i not in order), key=lambda i: math.dist(cen(conts[i]), rcx), default=None)
        if best is not None: order.append(best)
    conts = [conts[i] for i in order] + [c for i, c in enumerate(conts) if i not in order]
    out = []
    for c, rc in zip(conts, ref_conts):
        k = min(range(len(c)), key=lambda i: math.dist(c[i][0], rc[0][0]))
        out.append(c[k:] + c[:k])
    out += conts[len(out):]
    sig = tuple(tuple("C" for _ in c) for c in out)
    return out, sig

def circle_line_x(c, r, y):  # x values where circle meets horizontal line y
    d = r*r - (y - c[1])**2; s = math.sqrt(d); return c[0] - s, c[0] + s
def ang(c, p): return math.atan2(p[1]-c[1], p[0]-c[0])
def arc_between(c, r, p, q, n, keep):
    """Arc from p to q on circle (c, r), going whichever way passes through the
    region keep(point) says is right. Topology is decided by the source, never
    by which way happens to be shorter at a given weight."""
    a0, a1 = ang(c, p), ang(c, q)
    for sweep in ((a1 - a0) % (2*math.pi), (a1 - a0) % (2*math.pi) - 2*math.pi):
        if keep(pol(c, r, a0 + sweep/2)): return arc(c, r, a0, a0 + sweep, n)
    raise ValueError("no arc passes the keep test")

def M4(case, w):
    if case == "A":
        # Trim the handle at the ring's outer edge; its start cap follows the circle.
        d = (math.cos(A_DIR), math.sin(A_DIR)); h = w/2
        n = (-d[1], d[0])
        # points where the handle's two long edges meet the outer circle
        def hit(sign):
            # solve |c + t d + sign h n - c| = R for t>0 (off = sign*h along n)
            t = math.sqrt(A_R*A_R - h*h)
            return (A_C[0] + d[0]*t + sign*h*n[0], A_C[1] + d[1]*t + sign*h*n[1])
        p_plus, p_minus = hit(1), hit(-1)
        e_plus = (A_END[0] + h*n[0], A_END[1] + h*n[1]); e_minus = (A_END[0] - h*n[0], A_END[1] - h*n[1])
        a_minus, a_plus = ang(A_C, p_minus), ang(A_C, p_plus)
        # one contour: outer circle the long way round from p_plus to p_minus, then out along the handle
        outer = arc(A_C, A_R, a_plus, a_minus + 2*math.pi, 4)
        cont = outer + [L(p_minus, e_minus), L(e_minus, e_plus), L(e_plus, p_plus)]
        return [reverse(cont), circle(A_C, A_R - w, ccw=True)]
    if case == "B":
        # Ring band minus a strip of half-width d around the slash = two crescent pieces.
        d = w/2 + GAP; out = []
        u = (B_Q[0]-B_P[0], B_Q[1]-B_P[1]); l = math.hypot(*u); u = (u[0]/l, u[1]/l); n = (-u[1], u[0])
        base = math.atan2(u[1], u[0])
        for s in (1, -1):
            # in the slash's frame, the cut line is y' = s*d; circle radius R meets it at x' = +/- sqrt(R^2 - d^2)
            def pt(R, sgn):
                x = sgn * math.sqrt(R*R - d*d); y = s*d
                return (B_C[0] + x*u[0] + y*n[0], B_C[1] + x*u[1] + y*n[1])
            Po1, Po2, Pi1, Pi2 = pt(B_R, 1), pt(B_R, -1), pt(B_R - w, 1), pt(B_R - w, -1)
            side = lambda pt: ((pt[0]-B_C[0])*n[0] + (pt[1]-B_C[1])*n[1]) * s > d
            cont = (arc_between(B_C, B_R, Po1, Po2, 2, side) + [L(Po2, Pi2)]
                    + arc_between(B_C, B_R - w, Pi2, Pi1, 2, side) + [L(Pi1, Po1)])
            out.append(cont if signed(cont) < 0 else reverse(cont))  # clockwise
        return out + [rect_along(B_P, B_Q, w/2)]
    if case == "C":
        R = C_dot_r(w) + GAP; a, b = C_LO + w, C_HI - w
        in_sq = lambda pt: pt[0] <= C_HI and pt[1] <= C_HI  # the arc runs through the square's band
        # outer square meets the notch circle at T_out (top edge) and R_out (right edge); inner at T_in, R_in
        t_out = (circle_line_x(C_DOT, R, C_HI)[0], C_HI)
        r_out = (C_HI, circle_line_x((C_DOT[1], C_DOT[0]), R, C_HI)[0])
        t_in = (circle_line_x(C_DOT, R, b)[0], b)
        r_in = (b, circle_line_x((C_DOT[1], C_DOT[0]), R, b)[0])
        cont = ([L(t_out, (C_LO, C_HI)), L((C_LO, C_HI), (C_LO, C_LO)), L((C_LO, C_LO), (C_HI, C_LO)), L((C_HI, C_LO), r_out)]
                + arc_between(C_DOT, R, r_out, r_in, 1, in_sq)
                + [L(r_in, (b, a)), L((b, a), (a, a)), L((a, a), (a, b)), L((a, b), t_in)]
                + arc_between(C_DOT, R, t_in, t_out, 1, in_sq))
        return [cont if signed(cont) < 0 else reverse(cont), circle(C_DOT, C_dot_r(w), ccw=False)]
    if case == "D":
        # Clip resolved in skeleton space: the half disc's arc IS the ring's inner edge.
        r = D_R - w
        half = [*arc(D_C, r, math.pi/2, 3*math.pi/2, 2), L(pol(D_C, r, 3*math.pi/2), pol(D_C, r, math.pi/2))]
        return ring_band(D_C, D_R, w) + [reverse(half)]  # reversed so it fills the counter (nonzero)

# ---------- evaluation ----------
MASTER_W = [100, 400, 700]
TEST_W = [100, 175, 250, 325, 400, 475, 550, 625, 700]

def signature(conts):
    """Structure that must match across masters: per contour, the list of segment kinds."""
    sig = []
    for c in conts:
        sig.append(tuple(s[0] if isinstance(s[0], str) else "C" for s in c))
    return tuple(sig)

def lerp_conts(a, b, t):
    return [[tuple(tuple(pa[i] + (pb[i]-pa[i])*t for i in range(2)) for pa, pb in zip(sa, sb)) for sa, sb in zip(ca, cb)] for ca, cb in zip(a, b)]

def instance(masters, wght):
    if wght <= 400: return lerp_conts(masters[0], masters[1], (wght-100)/300)
    return lerp_conts(masters[1], masters[2], (wght-400)/300)

TRUE = {"A": A_true, "B": B_true, "C": C_true, "D": D_true}

def truth_mask(case, w):
    """The intended boolean, evaluated exactly per sample point (no curve booleans)."""
    if case == "A": return ink(ring_band(A_C, A_R, w)) | ink([A_handle(w)])
    if case == "B": return (ink(ring_band(B_C, B_R, w)) & ~ink([rect_along(B_P, B_Q, w/2 + GAP)])) | ink([rect_along(B_P, B_Q, w/2)])
    if case == "C": return (ink(C_square(w)) & ~ink([circle(C_DOT, C_dot_r(w) + GAP)])) | ink([circle(C_DOT, C_dot_r(w))])
    if case == "D":
        half = [*arc(D_C, D_R, math.pi/2, 3*math.pi/2, 2), L(pol(D_C, D_R, 3*math.pi/2), pol(D_C, D_R, math.pi/2))]
        return ink(ring_band(D_C, D_R, w)) | ink([half])

def evaluate():
    results = {}
    for case in "ABCD":
        for name, m in (("M1", M1), ("M2", M2), ("M3", M3), ("M5", M5), ("M4", M4)):
            if name == "M5":
                ref = M3(case, stroke_width(400))
                masters = [M5(case, stroke_width(x), ref) for x in MASTER_W]
            else:
                masters = [m(case, stroke_width(x)) for x in MASTER_W]
            if name in ("M3", "M5"):
                kinds = [k for _, k in masters]; masters = [c for c, _ in masters]
                compatible = len(set(kinds)) == 1 and len({tuple(len(c) for c in ms) for ms in masters}) == 1
                counts = [[len(c) for c in ms] for ms in masters]
                errs = []
                for wght in TEST_W:
                    # Incompatible masters can't be interpolated at all; score the nearest master
                    inst = instance(masters, wght) if compatible else masters[min(range(3), key=lambda i: abs(MASTER_W[i]-wght))]
                    errs.append(round(err_px2(ink(inst), truth_mask(case, stroke_width(wght))), 2))
                results[(case, name)] = {"compatible": compatible, "counts": counts, "errors": errs}
                continue
            sigs = [signature(c) for c in masters]
            counts = [[len(c) for c in ms] for ms in masters]
            compatible = len(set(sigs)) == 1 and len(set(map(str, counts))) == 1
            errs = []
            for wght in TEST_W:
                inst = instance(masters, wght) if compatible else masters[1]
                errs.append(round(err_px2(ink(inst), truth_mask(case, stroke_width(wght))), 2))
            results[(case, name)] = {"compatible": compatible, "counts": counts, "errors": errs}
    return results

if __name__ == "__main__":
    r = evaluate()
    for (case, name), v in r.items():
        e = [x for x in v["errors"] if x is not None]
        print(case, name, "compatible" if v["compatible"] else "INCOMPATIBLE", "points/contour", v["counts"],
              "max err px^2", max(e) if e else "-")
