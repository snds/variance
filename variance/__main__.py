"""Command line: python -m variance <command> <set folder> [...]

  new     <dir> [name]        start a set
  import  <dir> <svg ...>     import SVG files (or folders of them)
  check   <dir>               findings per icon
  build   <dir>               export the variable font
  serve   <dir> [port]        open the app in the browser
"""
import sys, os, json
from . import project as P, checks as C, fontbuild as F

def _svgs(paths):
    for p in paths:
        if os.path.isdir(p):
            for f in sorted(os.listdir(p)):
                if f.lower().endswith(".svg"): yield os.path.join(p, f)
        else: yield p

def main(argv):
    if len(argv) < 2: print(__doc__); return 1
    cmd, root = argv[0], argv[1]
    if cmd == "new":
        P.Set.create(root, argv[2] if len(argv) > 2 else "My icons"); print("Created", root); return 0
    st = P.Set(root)
    if st.meta is None: print(f"No set at {root}. Run: python -m variance new {root}"); return 1
    if cmd == "import":
        for f in _svgs(argv[2:]):
            r = st.add_icon(os.path.basename(f), open(f).read())
            print(f"{r['result']:8} {r['name']}" + "".join(f"\n         - {n['text']}" for n in r["notes"]))
        return 0
    if cmd == "check":
        for n in st.names():
            fs = C.findings(st, n); print(f"{C.status(st, n, fs):9} {n}" + "".join(f"\n          {f['severity']}: {f['text']}" for f in fs))
        return 0
    if cmd == "build":
        s = F.build(st); s.pop("glyphs", None); s.pop("codepoints", None); print(json.dumps(s, indent=1)); return 0 if s.get("ok") else 1
    if cmd == "serve":
        from . import server
        server.serve(st, int(argv[2]) if len(argv) > 2 else 8960); return 0
    print(__doc__); return 1

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
