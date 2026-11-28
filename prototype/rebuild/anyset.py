"""Load icons from any SVG icon set onto Variance's 960-unit, y-up grid.

One loader for stroke sets (Lucide, Tabler outline, Heroicons outline) and
filled sets (Phosphor, Fluent, Heroicons solid, Remix, Tabler filled).
Every shape element is read with its inherited fill, stroke and fill-rule:
  - filled shapes become ink under their own fill-rule (nonzero or evenodd)
  - stroked shapes are outlined with the file's width, caps and joins
  - helper shapes with no fill and no stroke (Tabler's frame, Carbon's
    inner rects) draw nothing, so they are dropped
Files with transforms or clip paths are skipped (rare; listed by the caller).

For stroke sets `skeleton()` also returns the true centre-lines, which is the
ground truth the fitter has to recover."""
import os, re, glob
import xml.etree.ElementTree as ET
import pathops
from fontTools.svgLib.path import parse_path
from fontTools.svgLib.path.shapes import PathBuilder
from fontTools.pens.transformPen import TransformPen
import icons_io as IO

SETS_DIR = os.path.join(IO.SRC, "sets")
P = lambda *a: os.path.join(SETS_DIR, *a)

# set -> variant -> (folder, filename pattern with {n}, viewBox size)
SETS = {
    "lucide":   {"stroke": (P("lucide-static", "package", "icons"), "{n}.svg", 24)},
    "tabler":   {"outline": (P("_tabler_icons", "package", "icons", "outline"), "{n}.svg", 24),
                 "filled": (P("_tabler_icons", "package", "icons", "filled"), "{n}.svg", 24)},
    "phosphor": {w: (P("_phosphor-icons_core", "package", "assets", w), "{n}" + ("" if w == "regular" else "-" + w) + ".svg", 256)
                 for w in ("thin", "light", "regular", "bold", "fill")},
    "fluent":   {f"{s}_{k}": (P("_fluentui_svg-icons", "package", "icons"), "{n}_" + f"{s}_{k}.svg", s)
                 for s in (16, 20, 24, 28, 32, 48) for k in ("regular", "filled")},
    "heroicons": {"outline24": (P("heroicons", "package", "24", "outline"), "{n}.svg", 24),
                  "solid24": (P("heroicons", "package", "24", "solid"), "{n}.svg", 24),
                  "solid20": (P("heroicons", "package", "20", "solid"), "{n}.svg", 20),
                  "solid16": (P("heroicons", "package", "16", "solid"), "{n}.svg", 16)},
    "remix":    {"line": (P("remixicon", "package", "icons", "*"), "{n}-line.svg", 24),
                 "fill": (P("remixicon", "package", "icons", "*"), "{n}-fill.svg", 24)},
}
LICENSES = {"lucide": "ISC", "tabler": "MIT", "phosphor": "MIT", "fluent": "MIT", "heroicons": "MIT", "remix": "Apache-2.0"}

class Skip(Exception): pass

def _file(s, v, n):
    folder, pat, _ = SETS[s][v]
    hits = glob.glob(os.path.join(folder, pat.format(n=n)))
    if not hits: raise FileNotFoundError(f"{s}/{v}/{n}")
    return hits[0]

def names(s, v):
    folder, pat, _ = SETS[s][v]
    pre, post = pat.split("{n}")
    out = set()
    for f in glob.glob(os.path.join(folder, pat.replace("{n}", "*"))):
        b = os.path.basename(f)
        if b.startswith(pre) and b.endswith(post):
            out.add(b[len(pre):len(b) - len(post)])
    if s == "phosphor" and v == "regular":   # regular files have no suffix; drop other weights' files
        out = {n for n in out if not re.search(r"-(thin|light|bold|fill|duotone)$", n)}
    return sorted(out)

def common(s, *variants):
    """Names present in every listed variant."""
    sets = [set(names(s, v)) for v in variants]
    return sorted(set.intersection(*sets))

def _strip_ns(root):
    for el in root.iter():
        if "}" in el.tag: el.tag = el.tag.split("}", 1)[1]
    return root

INHERIT = ("fill", "stroke", "stroke-width", "fill-rule", "stroke-linecap", "stroke-linejoin", "opacity")
SHAPES = {"path", "rect", "circle", "ellipse", "line", "polyline", "polygon"}

def _style(el, parent):
    st = dict(parent)
    for k in INHERIT:
        if k in el.attrib: st[k] = el.attrib[k]
    for decl in el.attrib.get("style", "").split(";"):
        if ":" in decl:
            k, v = (x.strip() for x in decl.split(":", 1))
            if k in INHERIT: st[k] = v
    return st

def _elements(svg_text):
    """Yield (d strings, style) for every drawn shape, with inherited style."""
    root = _strip_ns(ET.fromstring(svg_text))
    base = {"fill": "#000", "stroke": "none", "stroke-width": "1", "fill-rule": "nonzero",
            "stroke-linecap": "butt", "stroke-linejoin": "miter", "opacity": "1"}
    def walk(el, st):
        if el.tag in ("defs", "clipPath", "mask", "title", "desc", "style"): return
        if "transform" in el.attrib or "clip-path" in el.attrib or "mask" in el.attrib: raise Skip("transform/clip")
        st = _style(el, st)
        if el.tag in SHAPES:
            pb = PathBuilder(); pb.add_path_from_element(el)
            yield pb.paths, st
        for ch in el: yield from walk(ch, st)
    yield from walk(root, _style(root, base))

def _draw(ds, scale, close=False):
    p = pathops.Path(); pen = TransformPen(p.getPen(), (scale, 0, 0, -scale, 0, IO.UPM))
    for d in ds: parse_path(d, pen)
    return p

CAP = {"butt": pathops.LineCap.BUTT_CAP, "round": pathops.LineCap.ROUND_CAP, "square": pathops.LineCap.SQUARE_CAP}
JOIN = {"miter": pathops.LineJoin.MITER_JOIN, "round": pathops.LineJoin.ROUND_JOIN, "bevel": pathops.LineJoin.BEVEL_JOIN}

def _union(parts):
    out = pathops.Path()
    for q in parts: out = pathops.op(out, q, pathops.PathOp.UNION)
    return out

def load(s, v, n):
    """The icon's ink as one nonzero pathops Path on the 960 grid."""
    scale = IO.UPM / SETS[s][v][2]
    txt = open(_file(s, v, n)).read()
    inks = []
    for ds, st in _elements(txt):
        if st["opacity"] in ("0", "0.0"): continue
        if st["fill"] != "none":
            p = _draw(ds, scale)
            p.fillType = pathops.FillType.EVEN_ODD if st["fill-rule"] == "evenodd" else pathops.FillType.WINDING
            p.simplify(); inks.append(p)
        w = float(re.sub("[a-z]+", "", st["stroke-width"]) or 1)
        if st["stroke"] != "none" and w > 0:
            p = _draw(ds, scale)
            p.stroke(w * scale, CAP[st["stroke-linecap"]], JOIN[st["stroke-linejoin"]], 4)
            p.convertConicsToQuads(); p.simplify(); inks.append(p)
    return _union(inks)

def contours(s, v, n):
    import source as V
    return V.to_contours(load(s, v, n))

def skeleton(s, v, n):
    """True centre-lines of a stroke icon: (list of polylines on the 960 grid,
    stroke width in units, cap, join). Filled helper dots are returned as
    polylines too (their outline), flagged in `filled`."""
    scale = IO.UPM / SETS[s][v][2]
    txt = open(_file(s, v, n)).read()
    lines, width, cap, join = [], None, None, None
    for ds, st in _elements(txt):
        if st["stroke"] == "none": continue
        width = float(st["stroke-width"]) * scale; cap = st["stroke-linecap"]; join = st["stroke-linejoin"]
        p = _draw(ds, scale)
        import source as V
        for c in V.to_contours(p):
            import raster as R
            for poly in R.flatten([c], 12): lines.append(poly)
    return lines, width, cap, join
