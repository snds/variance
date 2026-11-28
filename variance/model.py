"""From source + settings to masters, with every value's tier.

Token tiers for geometry (docs/design/app-flows.md):
  Style    the set's rule ("pen" or "anchored")           global
  Context  what the rule does for this kind of edge        semantic
  Manual   a designer's setting on one part                component
A lower tier wins. Every resolved value carries the tier it came from.

Widths here are PLACEHOLDERS, not Material's values (Material's internal
numbers are not public): a stroke drawn at width W0 is 0.34 W0 at wght 100
and 1.66 W0 at wght 700.
"""
import math
from . import geom, source as S

AXES = {"wght": (100, 400, 700), "FILL": (0, 1)}
DEFAULT = {"wght": 400, "FILL": 0}
WIDTH_FACTOR = [(100, 0.34), (400, 1.0), (700, 1.66)]   # placeholder
MIN_WIDTH = 20          # 0.5 px at 24 px
MIN_GAP = 20            # 0.5 px
STYLES = {
    "pen": "Pen: every stroke widens and thins about its centre-line.",
    "anchored": "Anchored: counters hold still and outside edges move; lone strokes stay centred.",
}

def piecewise(x, table):
    if x <= table[0][0]: return table[0][1]
    for (x0, y0), (x1, y1) in zip(table, table[1:]):
        if x0 <= x <= x1: return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return table[-1][1]

def wkey(w): return str(int(round(w)))

class Icon:
    """One icon: its parts, parsed skeletons and settings."""
    def __init__(self, name, parts, settings=None):
        self.name = name; self.parts = parts; self.settings = settings or {}
        self.sk = {p["id"]: S.skeleton(p) for p in parts}
        self._counter = {}

    # ---- which side of a closed contour is its counter
    def counter_side(self, pid, ci):
        key = (pid, ci)
        if key not in self._counter:
            segs, closed, _ = self.sk[pid][ci]
            poly = [geom.bez(s, k / 8) for s in segs for k in range(8)]
            s0 = segs[0]; m = geom.bez(s0, 0.5); nl = geom.left_of(geom.tangent(s0, 0.5))
            probe = (m[0] + nl[0] * 2, m[1] + nl[1] * 2)
            self._counter[key] = "left" if _inside(probe, poly) else "right"
        return self._counter[key]

    def width(self, part, w):
        return part["width"] * piecewise(w, WIDTH_FACTOR)

    # ---- resolution -----------------------------------------------------------
    def sides(self, part, ci, si, w, style):
        """(left, right, {"left": tier, "right": tier, "why": text}) for one segment."""
        W = self.width(part, w); W0 = part["width"]
        segs, closed, _ = self.sk[part["id"]][ci]
        ent = self.settings.get("sides", {}).get(part["id"], {}).get(f"{ci}.{si}")
        if ent:
            amt = ent.get("amount", {}).get(wkey(w))
            if amt is not None:
                return amt[0], amt[1], {"tier": "Manual", "why": f"Set by hand at wght {wkey(w)}", "by": ent.get("by", "manual")}
            hold = ent.get("hold", {})
            h = hold.get(wkey(w)) or hold.get("*")
            if h:
                return (*_held(h, W, W0), {"tier": "Manual", "why": f"Pinned: {h} side holds" + ("" if hold.get("*") == h else f" at wght {wkey(w)}"),
                                           "by": ent.get("by", "manual"), "hold": h})
        if style == "anchored" and closed and not part.get("role", {}).get("open"):
            c = self.counter_side(part["id"], ci)
            l, r = _held(c, W, W0)
            return l, r, {"tier": "Context", "why": "Closed stroke: the counter side holds", "hold": c}
        if style == "anchored":
            return W / 2, W / 2, {"tier": "Context", "why": "Lone stroke: centred"}
        return W / 2, W / 2, {"tier": "Style", "why": "Pen: centred"}

    def ends(self, part, ci, w):
        e = self.settings.get("ends", {}).get(part["id"], {}).get(str(ci), {}).get(wkey(w))
        if e is not None: return tuple(e), {"tier": "Manual", "why": f"End moved at wght {wkey(w)}"}
        return (0.0, 0.0), {"tier": "Style", "why": "Ends follow the width"}

    # ---- outlines ---------------------------------------------------------------
    def outline(self, loc, style):
        """[(contour points, info)] at a location. info: part, ci, role
        ('ink' | 'counter' | 'knockout'). Ink runs one way, counters and
        knockouts the other. Which contours to reverse is decided once, at the
        default location, and applied everywhere, so direction comes from the
        source, never from one master's geometry."""
        if getattr(self, "_flip_style", None) != style:
            base = self._raw(DEFAULT, style)
            self._flip = [(geom.signed_area(c) < 0) != (info["role"] != "ink") for c, info in base]
            self._flip_style = style
        raw = self._raw(loc, style)
        return [((c[::-1] if f else c), info) for (c, info), f in zip(raw, self._flip)]

    def _raw(self, loc, style):
        w = loc.get("wght", 400); fill = loc.get("FILL", 0)
        out = []
        for part in self.parts:
            role = part.get("role") or {}
            for ci, (segs, closed, dot) in enumerate(self.sk[part["id"]]):
                info = {"part": part["id"], "ci": ci, "role": "ink"}
                if part["kind"] == "stroke":
                    W = self.width(part, w)
                    if dot is not None or not segs:
                        out.append((geom.dot_contour(dot or (0, 0), W / 2), info)); continue
                    sd = [self.sides(part, ci, si, w, style) for si in range(len(segs))]
                    cs = geom.stroke_contours(segs, closed, lambda si: sd[si][0], lambda si: sd[si][1],
                                              part.get("cap", "butt"), part.get("join", "round"), self.ends(part, ci, w)[0])
                    if closed:
                        outer, inner = (cs[0], cs[1]) if self.counter_side(part["id"], ci) == "right" else (cs[1], cs[0])
                        if fill and not role.get("open"):
                            inner = _collapse(inner, fill)
                        out.append((outer, info)); out.append((inner, dict(info, role="counter")))
                    else:
                        out.append((cs[0], info))
                else:
                    if not segs: continue
                    g = (80.0 * piecewise(w, WIDTH_FACTOR) - 80.0) / 2      # solids grow by half the width change
                    out.append((geom.solid_contour(segs, lambda si: g), dict(info, role="knockout" if role.get("knockout") else "ink")))
        return out

def _held(side, W, W0):
    """Distances (left, right) when `side` holds still at its default place."""
    if side == "centre": return W / 2, W / 2
    if side == "left": return W0 / 2, W - W0 / 2
    return W - W0 / 2, W0 / 2

def _collapse(pts, t):
    cx = sum(p[0] for p in pts) / len(pts); cy = sum(p[1] for p in pts) / len(pts)
    return [(p[0] + (cx - p[0]) * t, p[1] + (cy - p[1]) * t) for p in pts]

def _inside(p, poly):
    x, y = p; ins = False; n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]; x1, y1 = poly[(i + 1) % n]
        if (y0 > y) != (y1 > y):
            xi = x0 + (y - y0) * (x1 - x0) / (y1 - y0)
            if xi > x: ins = not ins
    return ins

def masters():
    """Master locations: every corner of the enabled axes, default first."""
    locs = [dict(DEFAULT)]
    for w in AXES["wght"]:
        for f in AXES["FILL"]:
            l = {"wght": w, "FILL": f}
            if l != DEFAULT: locs.append(l)
    return locs


def _mix(a, b, t):
    return [([(p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t) for p, q in zip(ca, cb)], ia) for (ca, ia), (cb, _) in zip(a, b)]

def at(icon, loc, style):
    """The outline the font will draw at any location: masters are built at
    the corners and everything between is interpolated, exactly as the
    variable font does it (masters share structure, so this is a plain mix)."""
    w = min(700, max(100, loc.get("wght", 400))); f = min(1, max(0, loc.get("FILL", 0)))
    ws = AXES["wght"]
    if w <= ws[1]: w0, w1 = ws[0], ws[1]
    else: w0, w1 = ws[1], ws[2]
    tw = (w - w0) / (w1 - w0)
    def corner(wv, fv): return icon.outline({"wght": wv, "FILL": fv}, style)
    if f in (0, 1) and w in ws: return corner(w, f)
    lo = _mix(corner(w0, 0), corner(w1, 0), tw)
    if f == 0: return lo
    hi = _mix(corner(w0, 1), corner(w1, 1), tw)
    return _mix(lo, hi, f)
