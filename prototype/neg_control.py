"""Negative control: move one contour's start point on one master and confirm
fontTools.varLib.interpolatable catches it. Writes to build/neg/."""
import os, gen
orig = gen.outline
def shifted(icon, a):
    cs = orig(icon, a)
    if a["wght"] == 700 and len(cs) > 2:
        cs[2] = cs[2][2:] + cs[2][:2]  # same shape, start point moved by 2 segments
    return cs
gen.outline = shifted
os.makedirs("build/neg", exist_ok=True)
print(gen.build_variable("build/neg/bad.ttf"))
