"""Rank icons by how hard they are to build from skeletons.
Signals (from a 192 px raster of the default style):
  contours  : number of outline contours
  holes     : enclosed counters (background pieces that don't touch the edge)
  parts     : separate ink pieces
  gaps      : area of thin clearance gaps (what overlaid shapes with cut-outs leave)
  solids    : share of ink thicker than 1.6 strokes (filled shapes mixed with strokes)
  knockouts : (Material) counters that survive at FILL 1, i.e. details cut out of a solid
"""
import sys, json
import numpy as np
from scipy import ndimage as ndi
from skimage.morphology import disk, binary_closing
import icons_io as io, raster as R

RES = 192; U = 960 / RES  # units per raster px

def features(contours, stroke_units):
    m = R.raster(contours, RES, steps=8)
    bg_lab, nbg = ndi.label(~m)
    edge = set(np.unique(np.concatenate([bg_lab[0], bg_lab[-1], bg_lab[:, 0], bg_lab[:, -1]])))
    holes = len([i for i in range(1, nbg + 1) if i not in edge])
    _, parts = ndi.label(m)
    r = max(1, round(1.4 * 40 / U))  # close gaps up to ~1.4 px at 24 px
    gaps = np.count_nonzero(binary_closing(m, disk(r)) & ~m) * (U / 40) ** 2
    dist = ndi.distance_transform_edt(m) * U
    thick = np.count_nonzero(dist > 0.8 * stroke_units) / max(1, np.count_nonzero(m))
    return m, dict(contours=len(contours), holes=holes, parts=parts, gaps=round(gaps, 2), solids=round(thick, 3))

def score(f):
    return f["contours"] + 2 * f["holes"] + 1.5 * f["parts"] + 0.6 * f["gaps"] + 12 * f["solids"] + 3 * f.get("knockouts", 0)

def run_material():
    names = io.ms_names(); seen = {}; out = []
    for n, cp in names.items():
        g = io.ms_font().getBestCmap().get(cp)
        if g is None or g in seen: continue
        seen[g] = n
        try:
            m, f = features(io.ms_contours(n, "def", names), 80)
            m1 = R.raster(io.ms_contours(n, "fill1", names), RES, steps=8)
            lab, k = ndi.label(~m1)
            edge = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]])))
            f["knockouts"] = len([i for i in range(1, k + 1) if i not in edge])
        except Exception as e:
            print("skip", n, e, file=sys.stderr); continue
        f["name"] = n; f["score"] = round(score(f), 2); out.append(f)
    return out

def run_carbon():
    out = []
    for n in io.carbon_names():
        try: _, f = features(io.carbon_contours(n), 60)
        except Exception as e: print("skip", n, e, file=sys.stderr); continue
        f["name"] = n; f["score"] = round(score(f), 2); out.append(f)
    return out

if __name__ == "__main__":
    which = sys.argv[1]
    res = run_material() if which == "material" else run_carbon()
    res.sort(key=lambda f: -f["score"])
    json.dump(res, open(sys.argv[2], "w"))
    print(len(res)); [print(f) for f in res[:40]]
