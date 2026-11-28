"""Checks, findings, status and risk for one icon.

Blocking gates fail export; warnings send the icon to the review queue.
Every finding names the part, the location and, where there is one, the
control that owns it, so the editor can open on it.
"""
import math
import numpy as np
from scipy.spatial import cKDTree
from . import geom, model as M, raster as R

def _f(sev, code, text, part=None, loc=None, ci=None, si=None, control=None):
    return {"severity": sev, "code": code, "text": text, "part": part, "loc": loc, "ci": ci, "si": si, "control": control}

REASONS = {
    "compat": "Masters don't match",
    "unsupported": "Cut or knockout not built yet",
    "thin": "Stroke too thin",
    "counter": "Counter closes",
    "gap": "Gap too tight",
    "unsure": "Rule unsure",
    "score": "Low score vs reference",
    "fill-detail": "Detail lost at FILL 1",
    "stale": "Fix lost its part",
}

def findings(st, name):
    """All findings for an icon in a set `st` (project.Set)."""
    ic = st.icon(name); style = st.style; out = []
    th = st.meta.get("thresholds", {})
    min_w = th.get("min_width_px", 0.5) * 40; min_gap = th.get("min_gap_px", 0.5) * 40
    locs = M.masters()
    outs = {(l["wght"], l["FILL"]): ic.outline(l, style) for l in locs}

    # blocking: masters must share structure (true by construction; checked anyway)
    base = [len(c) for c, _ in outs[(400, 0)]]
    for k, o in outs.items():
        if [len(c) for c, _ in o] != base:
            out.append(_f("block", "compat", f"Point counts differ at wght {k[0]} FILL {k[1]}; the font can't interpolate.", loc={"wght": k[0], "FILL": k[1]}))
            break
    for p in ic.parts:
        role = p.get("role") or {}
        if "cut" in role or role.get("knockout"):
            what = "cut" if "cut" in role else "knockout"
            out.append(_f("block", "unsupported", f"`{p['id']}` is a {what}. The fixed-structure build of {what}s "
                          "(research 02) isn't in the app yet, so this icon can't export.", part=p["id"]))

    # stale: manual settings that point at parts or segments that no longer exist
    for pid, segs in (ic.settings.get("sides") or {}).items():
        if pid not in ic.sk:
            out.append(_f("warn", "stale", f"A fix was set on `{pid}`, which is no longer in the source. Re-attach or drop it.", part=pid)); continue
        for key in segs:
            ci, si = (int(x) for x in key.split("."))
            if ci >= len(ic.sk[pid]) or si >= len(ic.sk[pid][ci][0]):
                out.append(_f("warn", "stale", f"A fix on `{pid}` segment {key} no longer matches the source.", part=pid, ci=ci, si=si))

    # warnings
    for p in ic.parts:
        if p["kind"] != "stroke": continue
        for ci, (segs, closed, dot) in enumerate(ic.sk[p["id"]]):
            for si in range(len(segs)):
                l, r, why = ic.sides(p, ci, si, 100, style)
                if l + r < min_w:
                    out.append(_f("warn", "thin", f"`{p['id']}` is {(l + r) / 40:.2f} px wide at wght 100 (minimum {min_w / 40:g} px).",
                                  part=p["id"], loc={"wght": 100, "FILL": 0}, ci=ci, si=si, control="sides"))
                    break

    # counters: area of each counter at wght 700 against the default
    def counters(o):
        return {(i["part"], i["ci"]): abs(geom.signed_area(c)) * (1 if geom.signed_area(c) * geom.signed_area(o0c[(i["part"], i["ci"])]) > 0 else -1)
                for c, i in o if i["role"] == "counter"}
    o0c = {(i["part"], i["ci"]): c for c, i in outs[(400, 0)] if i["role"] == "counter"}
    a0 = {k: abs(geom.signed_area(c)) for k, c in o0c.items()}
    a7 = counters(outs[(700, 0)])
    for k, a in a7.items():
        if a0.get(k, 0) > 0 and a < 0.25 * a0[k]:
            out.append(_f("warn", "counter", f"The counter inside `{k[0]}` shrinks to {max(a, 0) / a0[k]:.0%} of its size at wght 700.",
                          part=k[0], loc={"wght": 700, "FILL": 0}, ci=k[1], control="sides"))

    # gaps between parts that are apart at the default
    def pts_by_part(o):
        d = {}
        for c, i in o:
            if i["role"] == "ink": d.setdefault(i["part"], []).extend(c)
        return {k: np.asarray(v) for k, v in d.items()}
    P0, P7 = pts_by_part(outs[(400, 0)]), pts_by_part(outs[(700, 0)])
    ids = [p["id"] for p in ic.parts if p["id"] in P0]
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            d0 = cKDTree(P0[a]).query(P0[b])[0].min()
            if d0 < 30: continue     # touching or merged at the default: a merge, not a gap
            d7 = cKDTree(P7[a]).query(P7[b])[0].min()
            if d7 < min_gap:
                out.append(_f("warn", "gap", f"`{a}` and `{b}` come within {d7 / 40:.2f} px at wght 700 (minimum {min_gap / 40:g} px).",
                              part=b, loc={"wght": 700, "FILL": 0}, control="sides"))

    # FILL: details inside a flooded counter disappear (knockout rule not built yet)
    closed_parts = [(p["id"], ci) for p in ic.parts if p["kind"] == "stroke"
                    for ci, (segs, closed, _) in enumerate(ic.sk[p["id"]]) if closed and not (p.get("role") or {}).get("open")]
    if closed_parts and len(ic.parts) > 1:
        polys = {k: o0c[k] for k in closed_parts if k in o0c}
        for p in ic.parts:
            for ci, (segs, closed, dot) in enumerate(ic.sk[p["id"]]):
                pt = segs[0][0] if segs else dot
                if pt is None: continue
                for k, poly in polys.items():
                    if k[0] != p["id"] and _inside(pt, poly):
                        out.append(_f("warn", "fill-detail", f"`{p['id']}` sits inside `{k[0]}`'s counter, so it vanishes at FILL 1. "
                                      "Mark the counter `open`, or wait for the knockout rule.", part=p["id"], loc={"wght": 400, "FILL": 1}))
                        break
                else: continue
                break

    # rule confidence (anchored only): an open stroke that meets a closed one
    if style == "anchored":
        closed_pts = [geom.bez(s, k / 6) for p in ic.parts if p["kind"] == "stroke"
                      for segs, closed, _ in ic.sk[p["id"]] if closed for s in segs for k in range(6)]
        if closed_pts:
            tree = cKDTree(np.asarray(closed_pts))
            for p in ic.parts:
                if p["kind"] != "stroke": continue
                for ci, (segs, closed, dot) in enumerate(ic.sk[p["id"]]):
                    if closed or not segs: continue
                    ends = [segs[0][0], segs[-1][3]]
                    if min(tree.query(ends)[0]) < p["width"] * 1.2:
                        out.append(_f("warn", "unsure", f"`{p['id']}` meets a closed shape. The rule keeps it centred, "
                                      "but which side should hold here is a guess.", part=p["id"], loc={"wght": 700, "FILL": 0},
                                      ci=ci, si=0, control="sides"))
                        break

    # reference scores
    for w, path in st.references(name).items():
        try:
            from . import fit as FT
            sc = FT.score(ic, style, w, R.drawing_polys(open(path).read()))
        except Exception as e:  # a bad reference file shouldn't break the icon
            out.append(_f("warn", "score", f"Reference at wght {w} couldn't be read ({e}).", loc={"wght": w, "FILL": 0})); continue
        if sc is not None and sc < st.meta.get("thresholds", {}).get("ref_score", 0.95):
            out.append(_f("warn", "score", f"{sc:.0%} of the reference's edges are within 0.25 px at wght {w}.",
                          loc={"wght": w, "FILL": 0}, control="fit"))
    return out

def _inside(p, poly):
    from .model import _inside as ins
    return ins(p, poly)

def status(st, name, fs):
    if any(f["severity"] == "block" for f in fs): return "blocked"
    rv = st.settings(name).get("review") or {}
    if any(f["code"] == "stale" for f in fs): return "stale"
    if rv.get("accepted") == st.fingerprint(name): return "reviewed"
    if any(f["severity"] == "warn" for f in fs): return "review"
    return "good"

def risk(fs):
    """Queue order: blocking first, then by how many and how serious the warnings are."""
    w = {"compat": 100, "unsupported": 90, "stale": 60, "counter": 30, "gap": 25, "thin": 20, "score": 20, "unsure": 15, "fill-detail": 8}
    return sum(w.get(f["code"], 5) for f in fs)
