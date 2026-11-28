"""Export: masters -> variable TTF, reproducibly.

Every master comes from the source by a pure function (model.Icon.outline),
coordinates are rounded once at the end, and timestamps are pinned, so a
rebuild with no source change gives the same SHA-256 (repo rule).
"""
import os, io, json, hashlib, time
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib.tables._g_l_y_f import Glyph, GlyphCoordinates
from fontTools.ttLib.tables import ttProgram
from fontTools.misc.timeTools import timestampSinceEpoch
from fontTools.designspaceLib import DesignSpaceDocument, AxisDescriptor, SourceDescriptor
from fontTools import varLib
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from . import model as M, checks as C, project as P

UPM = 960
BUILD_TIME = timestampSinceEpoch(int(os.environ.get("SOURCE_DATE_EPOCH", "1764115200")))
LIGA_CHARS = "abcdefghijklmnopqrstuvwxyz0123456789_"

def _glyph(contours):
    """A TrueType glyph built point for point. (TTGlyphPen drops a closing
    point that lands on the first one, which can happen at one master and
    not another after rounding; that would break interpolation.)"""
    g = Glyph(); coords, ends = [], []
    for c in contours:
        coords.extend((round(x), round(UPM - y)) for x, y in c); ends.append(len(coords) - 1)
    g.numberOfContours = len(ends)
    g.coordinates = GlyphCoordinates(coords); g.flags = bytearray([1] * len(coords))
    g.endPtsOfContours = ends; g.program = ttProgram.Program(); g.program.fromBytecode(b"")
    return g

def _cname(ch): return "lig." + ({"_": "underscore"}.get(ch, ch))   # letter glyphs for ligatures; never clash with icon names

def _master(family, names, cps, glyphs):
    fb = FontBuilder(UPM, isTTF=True)
    letters = [_cname(c) for c in LIGA_CHARS]
    order = [".notdef", "space"] + letters + names
    fb.setupGlyphOrder(order)
    cmap = {cps[n]: n for n in names}; cmap[0x20] = "space"
    cmap.update({ord(c): _cname(c) for c in LIGA_CHARS})
    fb.setupCharacterMap(cmap)
    empty = TTGlyphPen(None).glyph()
    gs = {".notdef": empty, "space": empty}; gs.update({g: TTGlyphPen(None).glyph() for g in letters}); gs.update(glyphs)
    fb.setupGlyf(gs)
    fb.setupHorizontalMetrics({g: (UPM if g in glyphs else (UPM // 4 if g == "space" else 0), 0) for g in order})
    fb.setupHorizontalHeader(ascent=UPM, descent=0)
    fb.setupNameTable({"familyName": family, "styleName": "Regular"})
    fb.setupOS2(sTypoAscender=UPM, sTypoDescender=0, usWinAscent=UPM, usWinDescent=0)
    fb.setupPost()
    # ligatures: typing an icon's name draws it, as with Material Symbols
    rules = []
    for n in sorted(names, key=len, reverse=True):
        seq = [_cname(c) for c in n if c in LIGA_CHARS]
        if len(seq) == len(n) and seq: rules.append(f"  sub {' '.join(seq)} by {n};")
    if rules:
        addOpenTypeFeaturesFromString(fb.font, "feature liga {\n" + "\n".join(rules) + "\n} liga;\n")
    fb.font["head"].created = fb.font["head"].modified = BUILD_TIME
    return fb.font

def build(st, exclude_blocked=True):
    """Build the set's variable font. Returns a summary dict."""
    names, excluded, glyph_hash = [], [], {}
    locs = M.masters()
    per = {}
    for n in st.names():
        fs = C.findings(st, n)
        if exclude_blocked and C.status(st, n, fs) == "blocked":
            excluded.append({"name": n, "why": [f["text"] for f in fs if f["severity"] == "block"]}); continue
        ic = st.icon(n)
        outs = [[c for c, _ in ic.outline(l, st.style)] for l in locs]
        if not outs[0]: excluded.append({"name": n, "why": ["Nothing to draw."]}); continue
        names.append(n); per[n] = [_glyph(o) for o in outs]
        glyph_hash[n] = hashlib.sha256(json.dumps([[[(round(x), round(y)) for x, y in c] for c in o] for o in outs]).encode()).hexdigest()[:16]
    if not names:
        return {"ok": False, "error": "No icons can export yet.", "excluded": excluded}
    fam = st.meta.get("family") or st.meta.get("name", "Variance Icons")
    cps = st.meta["codepoints"]
    ds = DesignSpaceDocument()
    for tag, rng in (("wght", (100, 400, 700)), ("FILL", (0, 0, 1))):
        ax = AxisDescriptor(); ax.tag = ax.name = tag; ax.minimum, ax.default, ax.maximum = rng; ds.addAxis(ax)
    masters = []
    for i, l in enumerate(locs):
        f = _master(fam, names, cps, {n: per[n][i] for n in names})
        s = SourceDescriptor(); s.font = f; s.location = dict(l); s.name = s.filename = f"master-wght{l['wght']}-fill{l['FILL']}.ttf"
        ds.addSource(s); masters.append((s.filename, f))
    vf, _, _ = varLib.build(ds)
    vf["head"].created = vf["head"].modified = BUILD_TIME
    buf = io.BytesIO(); vf.save(buf); data = buf.getvalue()
    sha = hashlib.sha256(data).hexdigest()

    # changelog against the last build
    bdir = st.builds_dir(); os.makedirs(bdir, exist_ok=True)
    prev = _last(bdir)
    old = prev["glyphs"] if prev else {}
    log = {"added": sorted(set(names) - set(old)), "removed": sorted(set(old) - set(names)),
           "changed": sorted(n for n in names if n in old and old[n] != glyph_hash[n])}
    same = bool(prev) and prev["sha256"] == sha
    num = prev["number"] if same else (prev["number"] + 1 if prev else 1)
    out = os.path.join(bdir, f"{num:04d}")
    os.makedirs(out, exist_ok=True)
    fname = _fname(fam) + "[FILL,wght].ttf"
    open(os.path.join(out, fname), "wb").write(data)
    # open interop: the masters plus a designspace that names them
    mdir = os.path.join(out, "masters"); os.makedirs(mdir, exist_ok=True)
    for fn, f in masters:
        f.save(os.path.join(mdir, fn));
    for s in ds.sources: s.path = os.path.join(mdir, s.filename); s.font = None
    ds.write(os.path.join(mdir, _fname(fam) + ".designspace"))
    summary = {"number": num, "sha256": sha, "bytes": len(data), "file": f"{num:04d}/{fname}", "icons": len(names),
               "masters": [dict(l) for l in locs], "excluded": excluded, "changelog": log, "same_as_last": same,
               "glyphs": glyph_hash, "codepoints": {n: f"U+{cps[n]:04X}" for n in names}, "family": fam}
    P.write_if_changed(os.path.join(out, "build.json"), P.dump(summary))
    summary["ok"] = True
    return summary

def _fname(fam): return "".join(ch for ch in fam if ch.isalnum()) or "VarianceIcons"

def _last(bdir):
    best = None
    for d in sorted(os.listdir(bdir)) if os.path.isdir(bdir) else []:
        p = os.path.join(bdir, d, "build.json")
        if os.path.exists(p): best = json.load(open(p))
    return best

def last(st): return _last(st.builds_dir())
