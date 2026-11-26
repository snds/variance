"""Run the pixel edge-move analysis (edgemove.py) on pairs of icon styles.

Each job compares a base style A with a target style B for a sample of icons:
  material def -> w100/w700/o20/o48 (checks the method against research 04's
  exact edge results), phosphor regular -> thin/light/bold, fluent 24 ->
  16/20/28/32/48, heroicons solid24 -> solid20/16.

Pass 1 measures every icon's boundary pixels (in parallel). Pass 2 learns
the pair's own rule (usual move per context) and labels every pixel with a
tier. Also scores two outside rules on the same pixels: an even outline
offset, and Material's context rule rescaled to this pair's width change.
Usage: pairs.py OUT.json [job ...]"""
import sys, json, random
import numpy as np
from multiprocessing import Pool
import edgemove as E, anyset as A, icons_io as IO

MAT = json.load(open(__file__.replace("pairs.py", "material-rules.json")))

def loader(spec, n):
    s, v = spec
    if s == "material": return IO.ms_contours(n, v)
    return A.contours(s, v, n)

# job: (A spec, B spec, stroke width of A in units, Material master to compare, sample)
JOBS = {}
for loc in ("w100", "w700", "o20", "o48"):
    JOBS[f"material:{loc}"] = (("material", "def"), ("material", loc), 80, loc, 300)
for w, ml in (("thin", "w100"), ("light", "w100"), ("bold", "w700")):
    JOBS[f"phosphor:{w}"] = (("phosphor", "regular"), ("phosphor", w), 60, ml, 300)
for s in (16, 20, 28, 32, 48):
    JOBS[f"fluent:{s}"] = (("fluent", "24_regular"), ("fluent", f"{s}_regular"), 60, "o20" if s < 24 else "o48", 300)
for s in (20, 16):
    JOBS[f"heroicons:solid{s}"] = (("heroicons", "solid24"), ("heroicons", f"solid{s}"), 60, "o20", 300)

def names_for(job):
    a, b, W, ml, n = JOBS[job]
    if a[0] == "material":
        pool = sorted(IO.ms_names())
    else:
        pool = sorted(set(A.names(*a)) & set(A.names(*b)))
    random.Random(7).shuffle(pool)
    return pool[:n], len(pool)

def one(args):
    job, n = args
    a, b, W, ml, _ = JOBS[job]
    try:
        r = E.pair_features(loader(a, n), loader(b, n), W)
    except Exception as e:
        return n, None, repr(e)[:120]
    if r is None: return n, None, "empty"
    F, k, kf, wa, wb = r
    keep = {x: F[x] for x in ("r", "c", "nr", "nc", "ctx", "comp")}
    return n, (keep, k, kf, wa, wb), None

def analyse(job, rows):
    a, b, W, ml, _ = JOBS[job]
    names = [n for n, r, e in rows if r]
    data = [r for n, r, e in rows if r]
    ctx = np.concatenate([d[0]["ctx"] for d in data]); k = np.concatenate([d[1] for d in data])
    kf = np.concatenate([d[2] for d in data])
    stroke = ~np.isin(ctx, ["solid", "thin"])
    dW = float(np.median((k + kf)[stroke]))
    own = E.own_rule(ctx, k)
    # Material's rule for the matching master, rescaled to this pair's width change
    m = MAT[ml]; sc = dW / m["width_change"] if m["width_change"] else 1.0
    mat = {c: v * sc for c, v in m["move"].items()}
    tiers = {t: 0 for t in E.TIERS}; per = []; cover = {"offset": 0, "material": 0, "own": 0}; N = 0
    ladder = {"rule": 0, "resize": 0, "anchor": 0, "width": 0}
    for n, d in zip(names, data):
        F, kk, kkf, wa, wb = d
        lab, pred = E.label(F, kk, kkf, own, dW)
        for t in E.TIERS: tiers[t] += int((lab == t).sum())
        N += len(kk)
        cover["offset"] += int((np.abs(kk - dW / 2) <= E.NEAR).sum())
        cover["material"] += int((np.abs(kk - np.array([mat.get(c, dW / 2) for c in F["ctx"]])) <= E.NEAR).sum())
        cover["own"] += int((lab == "rule").sum())
        sh = {t: float((lab == t).mean()) for t in E.TIERS}
        cum = 0
        for t in ("rule", "resize", "anchor", "width"):
            cum += sh[t]
            if cum >= 0.95: ladder[t] += 1
        per.append({"icon": n, **{t: round(v, 4) for t, v in sh.items()}, "w_a": round(wa, 1), "w_b": round(wb, 1)})
    per.sort(key=lambda x: -x["reshape"])
    # move by context, top contexts by share
    cnt = {c: int((ctx == c).sum()) for c in own}
    top = sorted(cnt, key=lambda c: -cnt[c])[:12]
    return {"job": job, "icons": len(names), "pixels": N, "width_change": round(dW, 1),
            "width_a": round(float(np.median([d[3] for d in data])), 1), "width_b": round(float(np.median([d[4] for d in data])), 1),
            "tiers": {t: round(v / N, 4) for t, v in tiers.items()},
            "cover": {x: round(v / N, 4) for x, v in cover.items()},
            "ladder_95": {t: v for t, v in ladder.items()},
            "own_rule": {c: own[c] for c in top}, "context_share": {c: round(cnt[c] / len(ctx), 4) for c in top},
            "material_rule": {c: round(mat.get(c, dW / 2), 1) for c in top},
            "most_reshaped": per[:25], "per_icon": per}

if __name__ == "__main__":
    out = sys.argv[1]; jobs = sys.argv[2:] or list(JOBS)
    try: res = json.load(open(out))
    except Exception: res = {}
    with Pool(4) as pool:
        for job in jobs:
            names, pool_n = names_for(job)
            rows = pool.map(one, [(job, n) for n in names], chunksize=4)
            errs = [(n, e) for n, r, e in rows if e]
            r = analyse(job, rows); r["pool"] = pool_n; r["skipped"] = errs[:20]; r["n_skipped"] = len(errs)
            res[job] = r
            json.dump(res, open(out, "w"), indent=1)
            print(job, r["icons"], "dW", r["width_change"], r["tiers"], r["cover"], r["ladder_95"], flush=True)
