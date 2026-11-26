"""Load icons from Material Symbols (variable font) and IBM Carbon (SVG) into
one shape format: a list of contours, each a list of cubic segments
((x0,y0),(x1,y1),(x2,y2),(x3,y3)), on a 960-unit, y-up grid."""
import os, re
from fontTools.ttLib import TTFont
from fontTools.pens.basePen import BasePen
from fontTools.svgLib.path import SVGPath
from fontTools.pens.transformPen import TransformPen

SRC = os.environ.get("VARIANCE_SRC", os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))
UPM = 960

class CubicPen(BasePen):
    """Records outlines as cubic segments; lines become degenerate cubics,
    quadratics are raised exactly to cubics."""
    def __init__(self, glyphSet=None):
        super().__init__(glyphSet); self.contours = []; self.cur = None; self.start = None
    def _moveTo(self, p): self.cur = []; self.start = p
    def _lineTo(self, p):
        p0 = self._getCurrentPoint()
        if p0 != p: self.cur.append((p0, _lerp(p0, p, 1/3), _lerp(p0, p, 2/3), p))
    def _curveToOne(self, c1, c2, p): self.cur.append((self._getCurrentPoint(), c1, c2, p))
    def _qCurveToOne(self, c, p):
        p0 = self._getCurrentPoint()
        self.cur.append((p0, _lerp(p0, c, 2/3), _lerp(p, c, 2/3), p))
    def _closePath(self):
        if self.cur is not None:
            p0 = self._getCurrentPoint()
            if p0 != self.start: self._lineTo(self.start)
            if self.cur: self.contours.append(self.cur)
        self.cur = None
    def _endPath(self):  # open path: keep it open
        if self.cur: self.contours.append(self.cur)
        self.cur = None

def _lerp(a, b, t): return (a[0] + (b[0]-a[0])*t, a[1] + (b[1]-a[1])*t)

# ---------- Material Symbols ----------
_ms_fonts = {}
def ms_names():
    out = {}
    for line in open(os.path.join(SRC, "ms-outlined.codepoints")):
        n, c = line.split(); out[n] = int(c, 16)
    return out

def ms_font(loc="def"):
    if loc not in _ms_fonts: _ms_fonts[loc] = TTFont(os.path.join(SRC, f"ms-{loc}.ttf"))
    return _ms_fonts[loc]

def ms_contours(name, loc="def", names=None):
    """Material glyph at a stored instance: 'def' (FILL0 wght400 GRAD0 opsz24),
    'w100', 'w700', 'fill1', 'o20', 'o48', 'g200', 'gm50'. The font's em is
    960 with the baseline at 0 and glyphs drawn 0..960, so no transform."""
    names = names or ms_names(); f = ms_font(loc)
    gname = f.getBestCmap()[names[name]]
    pen = CubicPen(f.getGlyphSet()); f.getGlyphSet()[gname].draw(pen)
    return pen.contours

def ms_points(name, loc="def", names=None):
    """Raw TrueType points (on- and off-curve) for delta analysis."""
    names = names or ms_names(); f = ms_font(loc)
    g = f["glyf"][f.getBestCmap()[names[name]]]
    c, ends, flags = g.getCoordinates(f["glyf"])
    return list(c), list(ends), [fl & 1 for fl in flags]

# ---------- IBM Carbon ----------
CARBON = os.path.join(SRC, "carbon", "package", "svg", "32")
def carbon_names():
    return sorted(f[:-4] for f in os.listdir(CARBON) if f.endswith(".svg"))

def strip_invisible(txt):
    """Carbon ships invisible helper shapes (fill="none" or opacity 0), for
    example the inner shape of a filled icon. They are not ink."""
    return re.sub(r'<(rect|path|circle|polygon|ellipse)[^>]*(fill="none"|opacity="0")[^>]*/>', "", txt)

def carbon_contours(name):
    """Carbon 32-unit artboard scaled x30 onto the 960 grid, y flipped up.
    Invisible helper rects (fill none / opacity 0) are dropped."""
    path = os.path.join(CARBON, name + ".svg")
    txt = open(path).read()
    # drop invisible helper shapes Carbon sometimes ships
    txt = strip_invisible(txt)
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".svg", delete=False) as t: t.write(txt); tmp = t.name
    pen = CubicPen()
    SVGPath(tmp, transform=(30, 0, 0, -30, 0, 960)).draw(pen)
    os.unlink(tmp)
    return pen.contours
