"""Rebuild every picked icon as a Variance source and check it.

For each icon:
  1. Fit strokes, solids, knockouts and cut rules (extract.rebuild).
  2. Close the remaining gap with patches (residual.close_gap).
  3. Check the default style against the original.
  4. Material only: regenerate at weights 100 and 700 by changing only the
     stroke width, and compare with Google's own instances. Compare also with
     the naive approach: grow or shrink the default outline evenly.
Writes one JSON record per icon plus a proof image and a layered source SVG.
Usage: batch.py OUTDIR [material|carbon] [name ...]"""
import sys, os, json, time
import pathops
import extract as X, icons_io as IO, source as V, residual as RS, view

X.stroke_parts_v2 = lambda mask, outline, W, grid, join, prefix: X.stroke_parts_from_mask(mask, W, grid, "square", join, prefix)
W_OF = {"material": 80, "carbon": 60}
MS_WEIGHTS = {"w100": 28, "w700": 126}   # measured stroke widths in Google's font

def layer_name(p):
    r = p.get("role") or {}; bits = [p["id"]]
    if p.get("patch"): bits.append("patch " + p["patch"]["type"])
    if r.get("knockout"): bits.append("knockout")
    if "cut" in r:
        bits.append(f"cut gap={r['cut']/40:g}")
        if r.get("side", "both") != "both": bits.append(f"side={r['side']}")
        if r.get("hidden"): bits.append("hidden")
    if p["kind"] == "solid" and not r.get("knockout"): bits.append("solid")
    return " ".join(bits)

def source_svg(parts):
    """The source as a designer would hold it: one layer per part, strokes
    un-outlined, roles in the layer name. y flipped back to SVG's y-down."""
    rows = []
    for p in parts:
        attrs = f'id="{layer_name(p)}" d="{p["d"]}"'
        if p["kind"] == "stroke":
            attrs += f' fill="none" stroke="#000" stroke-width="{p["width"]}" stroke-linecap="{p["cap"]}" stroke-linejoin="{p["join"]}"'
        else:
            attrs += ' fill="#000"' if not (p.get("role") or {}).get("knockout") else ' fill="#f00"'
        rows.append(f"  <path {attrs}/>")
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 960">\n <g transform="matrix(1 0 0 -1 0 960)">\n'
            + "\n".join(rows) + "\n </g>\n</svg>\n")

def at_width(parts, W):
    """Same source, new stroke width. Sliver patches are fitting tolerance
    for the default style only, so they are left out."""
    out = []
    for p in parts:
        if p.get("patch") and p["patch"]["type"] == "sliver": continue
        q = dict(p)
        if q["kind"] == "stroke": q["width"] = W
        out.append(q)
    return out

def exterior(ink, b):
    """Move only the outside edge of the silhouette by b units (counters stay).
    Used for the "edge" recipe: strokes change by the counter-edge move on
    each side, then the silhouette moves the rest. It knows nothing of cuts,
    so it can close a cut gap; that's part of what the test shows."""
    if not b: return ink
    outer = X.contours_to_path([o for o, _ in X.components(ink)])
    ring = pathops.Path(); outer.draw(ring.getPen()); ring.stroke(2 * abs(b), V.CAP["butt"], V.JOIN["round"], 4); ring = V.fill(ring)
    if b > 0: return pathops.op(ink, pathops.op(ring, outer, pathops.PathOp.DIFFERENCE), pathops.PathOp.UNION)
    return pathops.op(ink, pathops.op(ring, outer, pathops.PathOp.INTERSECTION), pathops.PathOp.DIFFERENCE)

# Recipes for Material's weights, from edge_stats: (counter edge move, exterior edge move)
EDGE = {"w100": (0, -52), "w700": (12, 34)}  # (counter edge, outside edge), units

def naive(orig_path, d):
    s = pathops.Path(); orig_path.draw(s.getPen()); s.stroke(2 * abs(d), V.CAP["butt"], V.JOIN["miter"], 4); s = V.fill(s)
    return pathops.op(orig_path, s, pathops.PathOp.UNION if d > 0 else pathops.PathOp.DIFFERENCE)

def run(setname, name, outdir):
    t = time.time()
    c = IO.ms_contours(name) if setname == "material" else IO.carbon_contours(name)
    W = W_OF[setname]
    parts, fitted = X.rebuild(c, W, grid=0)
    full, patches = RS.close_gap(parts, c, W)
    orig = X.contours_to_path(c); om = X.mask_of(orig)
    final = X.score(V.generate(full), om)
    ink = RS.area(orig) / 1600
    rec = {"set": setname, "name": name, "ink_px2": round(ink, 1),
           "fit_px2": round(fitted[0], 2), "fit_core": fitted[1],
           "final_px2": round(final[0], 2), "final_core": final[1],
           "strokes": sum(p["kind"] == "stroke" for p in parts),
           "solids": sum(p["kind"] == "solid" and not (p.get("role") or {}).get("knockout") for p in parts),
           "knockouts": sum(bool((p.get("role") or {}).get("knockout")) for p in parts),
           "cuts": [dict(p["role"], id=p["id"]) for p in parts if "cut" in (p.get("role") or {})],
           "patch_px2": round(sum(p["area"] for p in patches) / 1600, 2),
           "detail_px2": round(sum(p["area"] for p in patches if p["type"] == "detail") / 1600, 2),
           "detail_patches": sum(p["type"] == "detail" for p in patches),
           "patch_pieces": len(patches)}
    # share of the icon's ink not owned by patches (patches are fixed shapes; rules scale)
    patch_area = sum(p["patch"]["area"] for p in full if p.get("patch")) / 1600
    rec["patch_px2"] = round(patch_area, 2)
    rec["rule_share"] = round(1 - min(patch_area, ink) / ink, 3)
    if setname == "material":
        rec["weights"] = {}
        for loc, Wl in MS_WEIGHTS.items():
            gm = X.mask_of(X.contours_to_path(IO.ms_contours(name, loc)))
            try: ours = X.score(V.generate(at_width(full, Wl)), gm)
            except pathops.PathOpsError: ours = (None, None)
            cm, em = EDGE[loc]
            try: edge = X.score(exterior(V.generate(at_width(full, W + 2 * cm)), em - cm), gm)
            except pathops.PathOpsError: edge = (None, None)
            try: nv = X.score(naive(orig, (Wl - W) / 2), gm)
            except pathops.PathOpsError: nv = (None, None)
            rec["weights"][loc] = {"variance_px2": ours[0], "variance_core": ours[1], "naive_px2": nv[0], "naive_core": nv[1], "edge_px2": edge[0], "edge_core": edge[1]}
            view.proof(IO.ms_contours(name, loc), at_width(full, Wl), os.path.join(outdir, f"{setname}-{name}-{loc}.png"))
    rec["secs"] = round(time.time() - t, 1)
    view.proof(c, full, os.path.join(outdir, f"{setname}-{name}.png"))
    with open(os.path.join(outdir, f"{setname}-{name}.svg"), "w") as f: f.write(source_svg(full))
    with open(os.path.join(outdir, f"{setname}-{name}.json"), "w") as f: json.dump(rec, f, indent=1)
    return rec

if __name__ == "__main__":
    outdir = sys.argv[1]; os.makedirs(outdir, exist_ok=True)
    picks = json.load(open(os.path.join(os.path.dirname(__file__), "picks.json")))
    sets = [sys.argv[2]] if len(sys.argv) > 2 else ["material", "carbon"]
    for s in sets:
        names = sys.argv[3:] or picks[s]
        for n in names:
            if os.path.exists(os.path.join(outdir, f"{s}-{n}.json")): continue
            try: r = run(s, n, outdir); print(s, n, r["fit_px2"], r["final_px2"], r["final_core"], r["rule_share"], r.get("weights"), r["secs"], flush=True)
            except Exception as e:
                import traceback; traceback.print_exc(); print("FAIL", s, n, repr(e), flush=True)
