"""Sources: reading any SVG into parts, and the source SVG Variance keeps.

A source is a list of parts, bottom to top. Each part is one layer:
  {"id": "shackle", "kind": "stroke", "d": "<centre-line>", "width": 80,
   "cap": "round", "join": "round", "role": {}}
  {"id": "dot", "kind": "solid", "d": "<filled shape>", "role": {}}

Layer-name grammar (research 02), read from the element's id:
  "<name> [solid] [knockout] [cut gap=<px>] [hidden] [open]"

The source file Variance writes is a plain SVG (960 x 960, y down) with live
strokes, so it opens in any editor and reads the same back.
"""
import math, re
import xml.etree.ElementTree as ET
from fontTools.svgLib.path.shapes import PathBuilder
from fontTools.svgLib.path.parser import parse_path
from fontTools.pens.transformPen import TransformPen
from . import geom

EM = 960

class ImportError_(Exception):
    pass

INHERIT = ("fill", "stroke", "stroke-width", "fill-rule", "stroke-linecap", "stroke-linejoin", "opacity", "display")
SHAPES = {"path", "rect", "circle", "ellipse", "line", "polyline", "polygon"}

def _strip(root):
    for el in root.iter():
        if isinstance(el.tag, str) and "}" in el.tag: el.tag = el.tag.split("}", 1)[1]
    return root

def _style(el, parent):
    st = dict(parent)
    for k in INHERIT:
        if k in el.attrib: st[k] = el.attrib[k].strip()
    for decl in el.attrib.get("style", "").split(";"):
        if ":" in decl:
            k, v = (x.strip() for x in decl.split(":", 1))
            if k in INHERIT: st[k] = v
    return st

def _num(v, default=0.0):
    m = re.match(r"\s*(-?[\d.]+(?:e-?\d+)?)", str(v))
    return float(m.group(1)) if m else default

def parse_role(name):
    """'slash cut gap=1 hidden' -> ('slash', {'cut': 40.0, 'hidden': True})."""
    words = (name or "").split()
    if not words: return "", {}
    role = {}
    for w in words[1:]:
        if w in ("solid", "knockout", "hidden", "open"): role[w] = True
        elif w == "cut": role["cut"] = role.get("cut", 0.0)
        elif w.startswith("gap="): role["cut"] = _num(w[4:]) * EM / 24
        elif w.startswith("side="): role["side"] = w[5:]
    return words[0], role

def role_words(role):
    out = []
    if role.get("solid"): out.append("solid")
    if role.get("knockout"): out.append("knockout")
    if "cut" in role:
        out.append("cut"); out.append(f"gap={role['cut'] * 24 / EM:g}")
    if role.get("side"): out.append(f"side={role['side']}")
    if role.get("hidden"): out.append("hidden")
    if role.get("open"): out.append("open")
    return out

def _xform(d, sx, sy, tx, ty):
    """Path data scaled and moved onto the 960 grid; arcs become cubics."""
    pen = geom._Pen(); tp = TransformPen(pen, (sx, 0, 0, sy, tx, ty))
    parse_path(d, tp); pen._flush(False)
    out = []
    for segs, closed in zip(pen.contours, pen.closed):
        if not segs:
            continue
        p = segs[0][0]; s = [f"M{p[0]:.2f} {p[1]:.2f}"]
        for seg in segs:
            if geom.is_line(seg): s.append(f"L{seg[3][0]:.2f} {seg[3][1]:.2f}")
            else: s.append("C" + " ".join(f"{q[0]:.2f} {q[1]:.2f}" for q in seg[1:]))
        if closed: s.append("Z")
        out.append("".join(s))
    # a lone moveto (a dot drawn as "M x y z" or a zero-length line) has no
    # segments; keep it as a zero-length line so the dot survives
    if not out:
        m = re.findall(r"[Mm]\s*(-?[\d.]+)[ ,]+(-?[\d.]+)", d)
        if m:
            x, y = float(m[0][0]) * sx + tx, float(m[0][1]) * sy + ty
            out.append(f"M{x:.2f} {y:.2f}L{x:.2f} {y:.2f}")
    return "".join(out)

def read_svg(text, name_hint="icon"):
    """Any SVG -> (parts, notes). Strokes stay strokes (their centre-line is
    the skeleton); filled shapes become solids. Notes are guesses and
    problems, in design terms, for the import report."""
    try:
        root = _strip(ET.fromstring(text))
    except ET.ParseError as e:
        raise ImportError_(f"Not a readable SVG ({e}).")
    vb = [float(v) for v in re.split(r"[ ,]+", root.attrib.get("viewBox", "").strip()) if v] or \
         [0, 0, _num(root.attrib.get("width", 24), 24), _num(root.attrib.get("height", 24), 24)]
    if len(vb) != 4 or vb[2] <= 0:
        raise ImportError_("The SVG has no usable viewBox or size.")
    s = EM / max(vb[2], vb[3])
    base = {"fill": "#000", "stroke": "none", "stroke-width": "1", "fill-rule": "nonzero",
            "stroke-linecap": "butt", "stroke-linejoin": "miter", "opacity": "1", "display": "inline"}
    parts, notes, seen = [], [], {}
    counter = [0]

    def walk(el, st):
        if not isinstance(el.tag, str) or el.tag in ("defs", "clipPath", "mask", "title", "desc", "style", "metadata"):
            return
        if "transform" in el.attrib and el.tag != "svg":
            raise ImportError_("Uses a transform. Flatten transforms on export (Figma: Outline is not needed; "
                               "Illustrator: Expand Appearance off, Transform Each applied).")
        if "clip-path" in el.attrib or "mask" in el.attrib:
            raise ImportError_("Uses a clip path or mask. Variance needs the cut as a layer named 'cut gap=…' instead.")
        st = _style(el, st)
        if st.get("display") == "none" or st.get("opacity") in ("0", "0.0"):
            return
        if el.tag in SHAPES:
            pb = PathBuilder(); pb.add_path_from_element(el)
            d = " ".join(pb.paths)
            if not d.strip(): return
            d = _xform(d, s, s, -vb[0] * s, -vb[1] * s)
            if not d: return
            raw = el.attrib.get("id", "")
            nm, role = parse_role(raw.replace("_", " ") if " " not in raw and re.search(r"_(cut|knockout|solid|hidden)", raw) else raw)
            if not nm:
                counter[0] += 1; nm = f"{el.tag}{counter[0]}"
            nm = re.sub(r"[^A-Za-z0-9_.-]", "-", nm)
            if nm in seen:
                seen[nm] += 1; nm = f"{nm}-{seen[nm]}"
            else: seen[nm] = 1
            w = _num(st.get("stroke-width", 1), 1) * s
            stroked = st.get("stroke", "none") not in ("none", "transparent") and w > 0
            filled = st.get("fill", "none") not in ("none", "transparent")
            if stroked and not role.get("solid"):
                if filled:
                    notes.append({"kind": "guess", "part": nm,
                                  "text": f"`{nm}` has both a fill and a stroke. Kept the stroke; the fill is ignored."})
                cap = st.get("stroke-linecap", "butt"); join = st.get("stroke-linejoin", "miter")
                if join == "miter":
                    notes.append({"kind": "lint", "part": nm,
                                  "text": f"`{nm}` uses mitre joins. Sharp corners can spike at heavy weights; round joins are safer."})
                parts.append({"id": nm, "kind": "stroke", "d": d, "width": round(w, 2),
                              "cap": cap if cap in ("butt", "round", "square") else "butt",
                              "join": join if join in ("miter", "round", "bevel") else "miter", "role": role})
            elif filled or role.get("solid") or role.get("knockout"):
                if st.get("fill-rule") == "evenodd":
                    notes.append({"kind": "guess", "part": nm,
                                  "text": f"`{nm}` uses the even-odd fill rule. Read as nonzero; check its holes."})
                parts.append({"id": nm, "kind": "solid", "d": d, "role": role})
        for ch in el:
            walk(ch, st)

    walk(root, _style(root, base))
    if not parts:
        raise ImportError_("No drawn shapes found.")
    if all(p["kind"] == "solid" for p in parts):
        notes.append({"kind": "outlined",
                      "text": "Every shape is filled, so this looks like outlined art. Imported as solids: weights will "
                              "grow evenly. Re-export with live strokes for full control."})
    return parts, notes

def write_svg(parts):
    """The source as a plain SVG: one layer per part, strokes live, roles in
    the layer name."""
    rows = []
    for p in parts:
        name = " ".join([p["id"]] + role_words(p.get("role") or {}))
        if p["kind"] == "stroke":
            rows.append(f'  <path id="{name}" d="{p["d"]}" fill="none" stroke="#000" stroke-width="{p["width"]:g}" '
                        f'stroke-linecap="{p["cap"]}" stroke-linejoin="{p["join"]}"/>')
        else:
            fill = "#d33" if (p.get("role") or {}).get("knockout") else "#000"
            rows.append(f'  <path id="{name}" d="{p["d"]}" fill="{fill}"/>')
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 960" width="960" height="960">\n'
            + "\n".join(rows) + "\n</svg>\n")

def read_source(text):
    """Read a source SVG Variance wrote (or one a designer edited)."""
    parts, _ = read_svg(text)
    return parts

def skeleton(part):
    """Parsed centre-line: [(segments, closed, dot_point)]."""
    return geom.contours_of(part["d"])
