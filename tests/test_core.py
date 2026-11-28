"""Core checks for the app's engine. Run: .venv/bin/python -m unittest discover -s tests"""
import os, sys, json, shutil, tempfile, unittest, glob
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from variance import project as P, model as M, fontbuild as F, fit as FT, raster as R, checks as C, server as SV
from fontTools.ttLib import TTFont

EX = os.path.join(ROOT, "examples", "lucide")

class Core(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.st = P.Set.create(os.path.join(cls.tmp, "set"), "Test Icons")
        for f in sorted(glob.glob(os.path.join(EX, "*.svg"))):
            r = cls.st.add_icon(os.path.basename(f), open(f).read())
            assert r["result"] != "failed", r

    @classmethod
    def tearDownClass(cls): shutil.rmtree(cls.tmp)

    def test_masters_share_structure(self):
        """Research 01's rule: same contours and point counts at every master, both styles."""
        for style in M.STYLES:
            for n in self.st.names():
                ic = self.st.icon(n)
                counts = {tuple(len(c) for c, _ in ic.outline(l, style)) for l in M.masters()}
                self.assertEqual(len(counts), 1, f"{n} ({style})")

    def test_pins_keep_structure(self):
        st = self.st; n = "lock"
        SV.edit(st, n, {"action": "pin", "part": "path2", "ci": 0, "si": 0, "side": "left", "scope": "along", "wght": 700})
        ic = st.icon(n)
        counts = {tuple(len(c) for c, _ in ic.outline(l, st.style)) for l in M.masters()}
        self.assertEqual(len(counts), 1)
        l, r, why = ic.sides(ic.parts[1], 0, 0, 700, st.style)
        self.assertEqual(why["tier"], "Manual")
        self.assertAlmostEqual(l, ic.parts[1]["width"] / 2)
        SV.edit(st, n, {"action": "clear", "part": "path2"})
        self.assertEqual(st.icon(n).sides(ic.parts[1], 0, 0, 700, st.style)[2]["tier"], "Context")

    def test_build_is_reproducible(self):
        a = F.build(self.st); b = F.build(self.st)
        self.assertTrue(a["ok"]); self.assertEqual(a["sha256"], b["sha256"]); self.assertTrue(b["same_as_last"])
        f = TTFont(os.path.join(self.st.builds_dir(), a["file"]))
        self.assertEqual(sorted(x.axisTag for x in f["fvar"].axes), ["FILL", "wght"])
        self.assertIn("lock", f.getGlyphOrder())

    def test_fit_to_a_drawing(self):
        st = self.st; ref = open(os.path.join(ROOT, "examples", "lock@wght=700.svg")).read()
        st.add_reference("lock", 700, ref)
        polys = R.drawing_polys(ref); ic = st.icon("lock")
        before = FT.score(ic, st.style, 700, polys)
        r = SV.edit(st, "lock", {"action": "fit", "wght": 700, "apply": True})
        self.assertGreater(r["after"], before + 0.3)
        self.assertGreater(r["after"], 0.95)
        SV.edit(st, "lock", {"action": "clear", "part": "path2"}); SV.edit(st, "lock", {"action": "clear", "part": "rect1"})

    def test_reimport_keeps_settings_and_flags_stale(self):
        st = self.st
        SV.edit(st, "check", {"action": "pin", "part": "path1", "ci": 0, "si": 1, "side": "right", "scope": "along", "wght": 700})
        st.add_icon("check.svg", open(os.path.join(EX, "check.svg")).read())     # same file: merge keeps the pin
        self.assertIn("path1", st.settings("check").get("sides", {}))
        # a source with a different structure: the fix no longer has its segment
        st.add_icon("check.svg", '<svg viewBox="0 0 24 24"><path d="M4 12h16" stroke="#000" stroke-width="2" fill="none"/></svg>')
        fs = C.findings(st, "check")
        self.assertEqual(C.status(st, "check", fs), "stale")
        st.add_icon("check.svg", open(os.path.join(EX, "check.svg")).read())

    def test_open_format_on_disk(self):
        root = self.st.root
        self.assertTrue(os.path.exists(os.path.join(root, "set.json")))
        src = open(os.path.join(root, "icons", "lock", "source.svg")).read()
        self.assertIn('stroke-linecap="round"', src)           # live strokes, not outlines
        before = open(os.path.join(root, "set.json"), "rb").read()
        self.st.save_meta()
        self.assertEqual(before, open(os.path.join(root, "set.json"), "rb").read())

if __name__ == "__main__":
    unittest.main()
