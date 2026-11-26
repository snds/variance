"""FILL fingerprints: what a set's filled style does compared with its outline.

For each icon:  O = outline style ink,  F = filled style ink,
                H = O with every counter flooded (what "just fill it" gives).
Pixels where F and H disagree (by more than 1/20 px) are sorted into:
  knockout  H has ink, F does not, and the spot was ink in O: an inner
            detail stroke turned into a gap through the fill
  open      H has ink, F does not, in one of O's counters: a counter that
            the fill left open (selective fill)
  cut       as open, but a strip no wider than a stroke: a slash's gap
            carried on through the fill
  bolder    F has ink beyond O, within half a stroke of O's ink: the
            filled style's strokes are heavier or shifted
  reshape   F has ink beyond O, further out: open shapes closed (a chevron
            becomes a triangle) or the shape redrawn
Counters opened only by a slash or badge cut (gap under 1.5 strokes) count as
counters, so "fill" floods them but keeps the cut.
Each icon gets the class that covers most of its difference:
  flood     differences under 3% of the filled ink: fill = flood the counters
  knockout / open / cut / bolder / reshape  as above
Knockout widths are compared with the outline's stroke width: a knockout as
wide as the stroke is the old stroke cut out; a thinner one is a drawn gap.
Usage: fillfp.py OUT.json [job ...]"""
import sys, json, random
import numpy as np
from scipy import ndimage as ndi
from skimage.morphology import skeletonize
from multiprocessing import Pool
import edgemove as E, anyset as A, icons_io as IO
from pairs import loader

JOBS = {
    "material": (("material", "def"), ("material", "fill1"), 300),
    "phosphor": (("phosphor", "regular"), ("phosphor", "fill"), 300),
    "tabler": (("tabler", "outline"), ("tabler", "filled"), 300),
    "remix": (("remix", "line"), ("remix", "fill"), 300),
    "heroicons": (("heroicons", "outline24"), ("heroicons", "solid24"), 300),
    "fluent": (("fluent", "24_regular"), ("fluent", "24_filled"), 300),
}
TOL = 2   # px at 480 = 4 units = 1/10 px at 24 px

def names_for(job):
    a, b, n = JOBS[job]
    pool = sorted(IO.ms_names()) if a[0] == "material" else sorted(set(A.names(*a)) & set(A.names(*b)))
    random.Random(7).shuffle(pool); return pool[:n], len(pool)

def one(args):
    job, n = args
    a, b, _ = JOBS[job]
    try:
        O = E.mask(loader(a, n)); F = E.mask(loader(b, n))
    except Exception as e:
        return n, None, repr(e)[:120]
    if not O.any() or not F.any(): return n, None, "empty"
    # flood every counter, including counters only opened by a slash or badge
    # cut: close gaps up to 1.5 strokes wide, flood, but keep the cut itself open
    W = E.stroke_width(O); rad = max(1, int(round(0.75 * W / E.U)))
    Op = np.pad(O, rad + 2)          # closing by distance transforms (fast, round)
    D = ndi.distance_transform_edt(~Op) <= rad
    C = (ndi.distance_transform_edt(D) > rad)[rad + 2:-rad - 2, rad + 2:-rad - 2]
    H = O | ndi.binary_fill_holes(O) | (ndi.binary_fill_holes(C) & ~C)
    far_from_F = ndi.distance_transform_edt(~F) > TOL
    far_from_H = ndi.distance_transform_edt(~H) > TOL
    miss = H & ~F & far_from_F
    Od = ndi.binary_dilation(O, iterations=TOL)
    knock = miss & Od; opn = miss & ~Od
    # a thin open strip through a flooded counter is a cut (a slash's gap)
    # carried through the fill, not a counter left open
    lab, nl = ndi.label(H & ~F & ~Od)
    if nl:
        th = ndi.maximum(ndi.distance_transform_edt(H & ~F & ~Od), lab, np.arange(1, nl + 1)) * 2 * E.U
        thin_ids = np.arange(1, nl + 1)[th <= 1.0 * W]
        cut = opn & np.isin(lab, thin_ids); opn = opn & ~cut
    else:
        cut = np.zeros_like(O)
    grown = F & ~H & far_from_H
    nearO = ndi.distance_transform_edt(~O) * E.U <= 0.5 * W
    fa = F.sum()
    sh = {"knockout": knock.sum() / fa, "open": opn.sum() / fa, "cut": cut.sum() / fa,
          "bolder": (grown & nearO).sum() / fa, "reshape": (grown & ~nearO).sum() / fa}
    tot = sum(sh.values())
    cls = "flood" if tot < 0.03 else max(sh, key=sh.get)
    # knockout width: 2 x distance on the gap's medial line (H minus F, full gap)
    gap = H & ~F
    wk = None
    if knock.sum() > 50:
        lab, _ = ndi.label(gap); keep = np.isin(lab, np.unique(lab[knock]))
        sk = skeletonize(keep); d = ndi.distance_transform_edt(keep)
        if sk.any(): wk = float(np.median(2 * d[sk]) * E.U)
    return n, {"icon": n, "class": cls, **{k: round(float(v), 4) for k, v in sh.items()},
               "w_outline": round(W, 1), "w_knockout": wk}, None

def analyse(job, rows):
    recs = [r for n, r, e in rows if r]
    cls = {}
    for r in recs: cls[r["class"]] = cls.get(r["class"], 0) + 1
    wk = [r["w_knockout"] / r["w_outline"] for r in recs if r["w_knockout"] and r["w_outline"]]
    return {"job": job, "icons": len(recs), "classes": {k: round(v / len(recs), 3) for k, v in sorted(cls.items())},
            "mean_share": {k: round(float(np.mean([r[k] for r in recs])), 4) for k in ("knockout", "open", "cut", "bolder", "reshape")},
            "knockout_to_stroke": round(float(np.median(wk)), 2) if wk else None,
            "knockout_ratio_q": [round(float(q), 2) for q in np.percentile(wk, [25, 75])] if wk else None,
            "w_outline": round(float(np.median([r["w_outline"] for r in recs])), 1),
            "most_reshaped": sorted(recs, key=lambda r: -r["reshape"])[:15], "per_icon": recs}

if __name__ == "__main__":
    out = sys.argv[1]; jobs = sys.argv[2:] or list(JOBS)
    try: res = json.load(open(out))
    except Exception: res = {}
    with Pool(4) as pool:
        for job in jobs:
            names, pool_n = names_for(job)
            rows = pool.map(one, [(job, n) for n in names], chunksize=4)
            r = analyse(job, rows); r["pool"] = pool_n; r["n_skipped"] = sum(1 for n, x, e in rows if e)
            res[job] = r; json.dump(res, open(out, "w"), indent=1)
            print(job, r["icons"], r["classes"], r["mean_share"], r["knockout_to_stroke"], r["knockout_ratio_q"], flush=True)
