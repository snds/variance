"""Writes the SVG proof cells for research 02 as JSON: for each icon and method,
the shape at five weights plus the area where it disagrees with the true boolean."""
import json, sys
import numpy as np
import booleans as B

SHOW_W = [100, 250, 400, 550, 700]
METHODS = ["M1", "M2", "M3", "M5", "M4"]

def d_of(conts):
    out = []
    for c in conts:
        out.append("M%.1f %.1f" % c[0][0])
        for s in c: out.append("C%.1f %.1f %.1f %.1f %.1f %.1f" % (*s[1], *s[2], *s[3]))
        out.append("Z")
    return "".join(out)

def runs_of(mask):
    """Merge differing samples into horizontal runs -> compact SVG path."""
    n = len(B._xs); m = mask.reshape(n, n); parts = []
    for row in range(n):
        r = m[row]; x = 0
        while x < n:
            if r[x]:
                x0 = x
                while x < n and r[x]: x += 1
                parts.append("M%d %dh%dv%dh-%dz" % (x0*B.STEP, row*B.STEP, (x-x0)*B.STEP, B.STEP, (x-x0)*B.STEP))
            else: x += 1
    return "".join(parts)

def build():
    res = {}
    for case in "ABCD":
        ref = B.M3(case, B.stroke_width(400))
        for name in METHODS:
            if name == "M3": masters = [B.M3(case, B.stroke_width(x)) for x in B.MASTER_W]
            elif name == "M5": masters = [B.M5(case, B.stroke_width(x), ref) for x in B.MASTER_W]
            else: masters = [getattr(B, name)(case, B.stroke_width(x)) for x in B.MASTER_W]
            if name in ("M3", "M5"):
                kinds = [k for _, k in masters]; masters = [c for c, _ in masters]
                ok = len(set(kinds)) == 1 and len({tuple(len(c) for c in ms) for ms in masters}) == 1
            else:
                ok = len({B.signature(c) for c in masters}) == 1 and len({str([len(c) for c in ms]) for ms in masters}) == 1
            cells = []
            for wght in SHOW_W:
                w = B.stroke_width(wght)
                if ok: inst = B.instance(masters, wght)
                elif wght in B.MASTER_W: inst = masters[B.MASTER_W.index(wght)]
                else: cells.append(None); continue
                diff = B.ink(inst) != B.truth_mask(case, w)
                cells.append({"d": d_of(inst), "err": runs_of(diff),
                              "px2": round(float(np.count_nonzero(diff)) * B.STEP**2 / B.PX**2, 2)})
            res[f"{case}-{name}"] = {"compatible": ok, "cells": cells}
    return res

if __name__ == "__main__":
    json.dump(build(), open(sys.argv[1], "w"))
