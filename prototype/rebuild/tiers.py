"""Group fingerprint labels into fix tiers, by what it costs to reach 100%:
  auto     rule or within 0.25 px: the pipeline does it
  resize   the whole glyph, or one whole part, scales or shifts: a few numbers per master
  anchor   a stroke keeps its standard width change but a different side moves:
           one anchor setting per stroke, set once in the source
  width    a stroke changes width more or less than standard (crowding)
  redraw   an edge tilts or bends: the shape itself changed, needs a hand-drawn override
Usage: tiers.py FP.json OUT.json"""
import sys, json
import numpy as np

TIERS = {"auto": ["rule", "near"], "resize": ["resize", "part"], "anchor": ["moved", "held"],
         "width": ["thinned", "thickened"], "redraw": ["tilt"]}
LOCS = ["w100", "w700", "o20", "o48", "g200", "gm50"]

def tiers_of(fp):
    return {t: sum(fp.get(x, 0) for x in xs) for t, xs in TIERS.items()}

def kmeans(X, k, seed=0, it=50):
    rng = np.random.default_rng(seed); C = X[rng.choice(len(X), k, replace=False)]
    for _ in range(it):
        d = ((X[:, None, :] - C[None]) ** 2).sum(-1); lab = d.argmin(1)
        C2 = np.array([X[lab == j].mean(0) if (lab == j).any() else C[j] for j in range(k)])
        if np.allclose(C2, C): break
        C = C2
    return lab, C

if __name__ == "__main__":
    R = json.load(open(sys.argv[1])); out = {"glyphs": []}
    X = []
    for g in R["glyphs"]:
        t = {l: tiers_of(g["fp"][l]) for l in LOCS}
        worst_redraw = max(t[l]["redraw"] for l in LOCS)
        out["glyphs"].append({"name": g["name"], "tiers": t, "redraw_max": round(worst_redraw, 3),
                              "redraw_masters": [l for l in LOCS if t[l]["redraw"] >= 0.10],
                              "auto_mean": round(float(np.mean([t[l]["auto"] for l in LOCS])), 3)})
        X.append([t[l][k] for l in LOCS for k in TIERS])
    X = np.array(X)
    lab, C = kmeans(X, 8)
    for g, l in zip(out["glyphs"], lab): g["family"] = int(l)
    out["families"] = []
    for j in range(8):
        c = C[j].reshape(len(LOCS), len(TIERS))
        members = [g["name"] for g in out["glyphs"] if g["family"] == j]
        out["families"].append({"id": j, "size": len(members),
                                "profile": {l: {k: round(float(c[i][n]), 3) for n, k in enumerate(TIERS)} for i, l in enumerate(LOCS)},
                                "examples": members[:12]})
    G = out["glyphs"]
    out["summary"] = {
        "glyphs": len(G),
        "all_auto_90": sum(g["auto_mean"] >= 0.9 for g in G),
        "needs_redraw_any": sum(bool(g["redraw_masters"]) for g in G),
        "redraw_by_master": {l: sum(l in g["redraw_masters"] for g in G) for l in LOCS},
        "tier_share": {l: {k: round(float(np.mean([g["tiers"][l][k] for g in G])), 3) for k in TIERS} for l in LOCS},
        "after_anchor_resize": sum(min(g["tiers"][l]["auto"] + g["tiers"][l]["resize"] + g["tiers"][l]["anchor"] for l in LOCS) >= 0.95 for g in G),
    }
    json.dump(out, open(sys.argv[2], "w"))
    print(json.dumps(out["summary"], indent=1))
    for f in out["families"]:
        p = f["profile"]
        print(f["id"], f["size"], {l: max(p[l], key=p[l].get) + f" {max(p[l].values()):.2f}" for l in LOCS}, "redraw w100/w700/o20:", p["w100"]["redraw"], p["w700"]["redraw"], p["o20"]["redraw"], f["examples"][:6])
