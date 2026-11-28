"""A set on disk: a plain folder in open formats (docs/design/app-flows.md,
"On-disk format"). Readable without Variance, diffable in git.

  set.json                      axes, style, names and code points
  icons/<name>/source.svg       the skeleton, live strokes (opens in any editor)
  icons/<name>/settings.json    manual settings (component tier) and review state
  icons/<name>/refs/<name>@wght=<w>.svg   reference drawings
  icons/<name>/import/<file>    the file as imported (history only)
  builds/<n>/                   font files, build.json (hash, changelog)

JSON is written pretty, with sorted keys, so an unchanged save writes the
same bytes.
"""
import os, json, re, hashlib
from . import source as S, model as M

PUA_START = 0xE000

def dump(obj):
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"

def write_if_changed(path, text):
    data = text.encode() if isinstance(text, str) else text
    if os.path.exists(path) and open(path, "rb").read() == data:
        return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "wb") as f: f.write(data)
    os.replace(tmp, path)
    return True

def slug(name):
    n = re.sub(r"\.svg$", "", os.path.basename(name), flags=re.I).lower()
    n = re.sub(r"[^a-z0-9_]+", "_", n).strip("_")
    return n or "icon"

class Set:
    def __init__(self, root):
        self.root = os.path.abspath(root)
        self.meta = json.load(open(self._p("set.json"))) if os.path.exists(self._p("set.json")) else None
        self._icons = {}

    def _p(self, *a): return os.path.join(self.root, *a)

    @classmethod
    def create(cls, root, name="My icons", style="anchored"):
        os.makedirs(os.path.join(root, "icons"), exist_ok=True)
        s = cls(root)
        if s.meta is None:
            s.meta = {"name": name, "style": style, "grid": {"em": 960, "px": 24},
                      "axes": {"wght": {"min": 100, "default": 400, "max": 700},
                               "FILL": {"min": 0, "default": 0, "max": 1}},
                      "next_axes": ["opsz", "GRAD"], "codepoints": {}, "family": name,
                      "thresholds": {"min_width_px": 0.5, "min_gap_px": 0.5, "ref_score": 0.95}}
            s.save_meta()
        return s

    def save_meta(self):
        write_if_changed(self._p("set.json"), dump(self.meta))

    @property
    def style(self): return self.meta.get("style", "anchored")

    def names(self):
        d = self._p("icons")
        if not os.path.isdir(d): return []
        return sorted(n for n in os.listdir(d) if os.path.exists(self._p("icons", n, "source.svg")))

    # ---- icons -----------------------------------------------------------------
    def icon(self, name):
        src = self._p("icons", name, "source.svg")
        stamp = (os.path.getmtime(src), os.path.getmtime(self._p("icons", name, "settings.json"))
                 if os.path.exists(self._p("icons", name, "settings.json")) else 0)
        hit = self._icons.get(name)
        if hit and hit[0] == stamp: return hit[1]
        parts = S.read_source(open(src).read())
        ic = M.Icon(name, parts, self.settings(name))
        self._icons[name] = (stamp, ic)
        return ic

    def settings(self, name):
        p = self._p("icons", name, "settings.json")
        return json.load(open(p)) if os.path.exists(p) else {}

    def save_settings(self, name, st):
        write_if_changed(self._p("icons", name, "settings.json"), dump(st))
        self._icons.pop(name, None)

    def source_text(self, name):
        return open(self._p("icons", name, "source.svg")).read()

    def fingerprint(self, name):
        """What a review accepted: the source and the settings, minus review state."""
        st = dict(self.settings(name)); st.pop("review", None)
        h = hashlib.sha256(self.source_text(name).encode() + dump(st).encode() + self.style.encode())
        return h.hexdigest()[:16]

    def add_icon(self, filename, text):
        """Import one SVG. Returns a report row. Re-importing an existing
        name is a merge: settings on parts that still exist are kept."""
        name = slug(filename)
        try:
            parts, notes = S.read_svg(text)
        except S.ImportError_ as e:
            return {"name": name, "file": filename, "result": "failed", "notes": [{"kind": "error", "text": str(e)}]}
        existed = os.path.exists(self._p("icons", name, "source.svg"))
        write_if_changed(self._p("icons", name, "import", os.path.basename(filename)), text)
        write_if_changed(self._p("icons", name, "source.svg"), S.write_svg(parts))
        if name not in self.meta["codepoints"]:
            used = set(self.meta["codepoints"].values())
            cp = PUA_START
            while cp in used: cp += 1
            self.meta["codepoints"][name] = cp
            self.save_meta()
        self._icons.pop(name, None)
        kind = "fitted" if any(n["kind"] == "outlined" for n in notes) else ("guesses" if any(n["kind"] == "guess" for n in notes) else "exact")
        return {"name": name, "file": filename, "result": "merged" if existed else kind, "notes": notes,
                "parts": len(parts)}

    def references(self, name):
        d = self._p("icons", name, "refs"); out = {}
        if os.path.isdir(d):
            for f in sorted(os.listdir(d)):
                m = re.search(r"@wght=(\d+)\.svg$", f)
                if m: out[int(m.group(1))] = os.path.join(d, f)
        return out

    def add_reference(self, name, wght, text):
        write_if_changed(self._p("icons", name, "refs", f"{name}@wght={int(wght)}.svg"), text)

    def builds_dir(self): return self._p("builds")
