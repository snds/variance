"""Refine rough centre lines against the exact original outline.

For each straight or circular piece of a centre line, cast rays both ways
along its normal to the original outline. Where the two hits are one stroke
width apart, their midpoint is an exact centre point. Refit the piece through
those midpoints, then rebuild the corners by intersecting neighbouring pieces,
and run free ends out to where the original's cap edge is.
"""
import math
import numpy as np
import raster as R

class Outline:
    def __init__(self, contours, steps=48):
        polys = R.flatten(contours, steps)
        A = np.vstack(polys); B = np.vstack([np.roll(p, -1, 0) for p in polys])
        self.a, self.b = A, B
    def ray(self, o, d, maxd=2000):
        """Distance to first hit from o along unit d (or None)."""
        ax, ay = self.a[:, 0] - o[0], self.a[:, 1] - o[1]
        ex, ey = self.b[:, 0] - self.a[:, 0], self.b[:, 1] - self.a[:, 1]
        den = d[0] * ey - d[1] * ex
        with np.errstate(divide="ignore", invalid="ignore"):
            t = (ax * ey - ay * ex) / den
            u = (ax * d[1] - ay * d[0]) / den
        ok = (np.abs(den) > 1e-12) & (t > 1e-6) & (u >= 0) & (u <= 1)
        if not ok.any(): return None
        t = t[ok].min(); return t if t < maxd else None

# ---- primitives: ("L", p0, p1) or ("A", centre, r, a0, a1) with a1-a0 signed sweep
def sample(prim, n=11, margin=0.18):
    ts = np.linspace(margin, 1 - margin, n)
    if prim[0] == "L":
        _, p, q = prim; d = np.subtract(q, p); L = np.hypot(*d) or 1; nrm = (-d[1] / L, d[0] / L)
        return [((p[0] + d[0] * t, p[1] + d[1] * t), nrm) for t in ts]
    _, c, r, a0, a1 = prim
    out = []
    for t in ts:
        a = a0 + (a1 - a0) * t; out.append(((c[0] + r * math.cos(a), c[1] + r * math.sin(a)), (math.cos(a), math.sin(a))))
    return out

def midpoints(prim, outline, W, tol=0.2):
    pts = []
    for p, n in sample(prim, n=15):
        f = outline.ray(p, n, 2 * W); b = outline.ray(p, (-n[0], -n[1]), 2 * W)
        if f is None or b is None: continue
        if abs((f + b) - W) > tol * W: continue
        s = (f - b) / 2
        pts.append((p[0] + n[0] * s, p[1] + n[1] * s))
    return pts

def fit_line(P):
    P = np.array(P); c = P.mean(0); u, s, vt = np.linalg.svd(P - c); d = vt[0]
    return c, d

def fit_circ(P):
    P = np.array(P); x, y = P[:, 0], P[:, 1]
    A = np.c_[2 * x, 2 * y, np.ones(len(P))]; b = x * x + y * y
    (cx, cy, k), *_ = np.linalg.lstsq(A, b, rcond=None)
    return (cx, cy), math.sqrt(max(k + cx * cx + cy * cy, 0))

def refine_prim(prim, outline, W):
    mp = midpoints(prim, outline, W)
    if prim[0] == "L":
        if len(mp) < 3: return prim, False
        c, d = fit_line(mp); p, q = prim[1], prim[2]
        proj = lambda z: (c[0] + d[0] * np.dot(np.subtract(z, c), d), c[1] + d[1] * np.dot(np.subtract(z, c), d))
        return ("L", proj(p), proj(q)), True
    if len(mp) < 4: return prim, False
    c, r = fit_circ(mp)
    return ("A", c, r, prim[3], prim[4]), True

# ---- geometry for reconnecting
def line_line(p, q, s, t):
    d1 = np.subtract(q, p); d2 = np.subtract(t, s); den = d1[0] * d2[1] - d1[1] * d2[0]
    if abs(den) < 1e-9: return None
    k = ((s[0] - p[0]) * d2[1] - (s[1] - p[1]) * d2[0]) / den
    return (p[0] + d1[0] * k, p[1] + d1[1] * k)

def line_circle(p, q, c, r, near):
    d = np.subtract(q, p); f = np.subtract(p, c)
    a = d @ d; b = 2 * f @ d; cc = f @ f - r * r; disc = b * b - 4 * a * cc
    if disc < 0:  # tangent-ish: closest point
        k = -b / (2 * a); return (p[0] + d[0] * k, p[1] + d[1] * k)
    sq = math.sqrt(disc); cands = [(-b - sq) / (2 * a), (-b + sq) / (2 * a)]
    pts = [(p[0] + d[0] * k, p[1] + d[1] * k) for k in cands]
    return min(pts, key=lambda z: math.dist(z, near))

def circle_circle(c1, r1, c2, r2, near):
    d = math.dist(c1, c2)
    if d < 1e-9 or d > r1 + r2 or d < abs(r1 - r2): return near
    a = (r1 * r1 - r2 * r2 + d * d) / (2 * d); h = math.sqrt(max(r1 * r1 - a * a, 0))
    mx = c1[0] + a * (c2[0] - c1[0]) / d; my = c1[1] + a * (c2[1] - c1[1]) / d
    p1 = (mx + h * (c2[1] - c1[1]) / d, my - h * (c2[0] - c1[0]) / d); p2 = (mx - h * (c2[1] - c1[1]) / d, my + h * (c2[0] - c1[0]) / d)
    return min((p1, p2), key=lambda z: math.dist(z, near))

def start(pr): return pr[1] if pr[0] == "L" else (pr[1][0] + pr[2] * math.cos(pr[3]), pr[1][1] + pr[2] * math.sin(pr[3]))
def end(pr): return pr[2] if pr[0] == "L" else (pr[1][0] + pr[2] * math.cos(pr[4]), pr[1][1] + pr[2] * math.sin(pr[4]))

def join_point(a, b):
    near = end(a)
    if a[0] == "L" and b[0] == "L": return line_line(a[1], a[2], b[1], b[2]) or near
    if a[0] == "L": return line_circle(a[1], a[2], b[1], b[2], near)
    if b[0] == "L": return line_circle(b[1], b[2], a[1], a[2], near)
    return circle_circle(a[1], a[2], b[1], b[2], near)

def set_end(pr, p):
    if pr[0] == "L": return ("L", pr[1], p)
    a = math.atan2(p[1] - pr[1][1], p[0] - pr[1][0]); a1 = pr[4]
    while a - a1 > math.pi: a -= 2 * math.pi
    while a1 - a > math.pi: a += 2 * math.pi
    return (pr[0], pr[1], pr[2], pr[3], a)

def set_start(pr, p):
    if pr[0] == "L": return ("L", p, pr[2])
    a = math.atan2(p[1] - pr[1][1], p[0] - pr[1][0]); a0 = pr[3]
    while a - a0 > math.pi: a -= 2 * math.pi
    while a0 - a > math.pi: a += 2 * math.pi
    return (pr[0], pr[1], pr[2], a, pr[4])

def tangent_out(pr, at_end):
    if pr[0] == "L":
        d = np.subtract(pr[2], pr[1]) if at_end else np.subtract(pr[1], pr[2])
        return d / (np.hypot(*d) or 1)
    a = pr[4] if at_end else pr[3]; sgn = 1 if pr[4] > pr[3] else -1
    t = np.array((-math.sin(a), math.cos(a))) * sgn
    return t if at_end else -t

def to_d(prims, closed):
    s = start(prims[0]); out = [f"M{s[0]:.2f} {s[1]:.2f}"]
    for pr in prims:
        e = end(pr)
        if pr[0] == "L": out.append(f"L{e[0]:.2f} {e[1]:.2f}")
        else:
            sweep = pr[4] - pr[3]
            out.append(f"A{pr[2]:.2f} {pr[2]:.2f} 0 {int(abs(sweep) > math.pi)} {int(sweep > 0)} {e[0]:.2f} {e[1]:.2f}")
    if closed: out.append("Z")
    return " ".join(out)
