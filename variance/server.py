"""`variance serve`: the app, as a local web page over the same core the CLI uses.

Standard library only. Everything the app changes is written straight to the
set folder (open formats, see project.py), so the folder is always the truth
and git can track it.
"""
import os, json, re, threading, webbrowser, mimetypes, urllib.parse, copy
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from . import geom, model as M, checks as C, fontbuild as F, fit as FT, raster as R, project as P

APP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app")
LOCK = threading.Lock()

def _loc(q):
    w = float(q.get("wght", ["400"])[0]); f = float(q.get("FILL", ["0"])[0])
    return {"wght": max(100, min(700, w)), "FILL": max(0, min(1, f))}

def _summary(st, n):
    fs = C.findings(st, n)
    return {"name": n, "status": C.status(st, n, fs), "risk": C.risk(fs),
            "reasons": sorted({f["code"] for f in fs}), "findings": fs,
            "cp": f"U+{st.meta['codepoints'].get(n, 0):04X}"}

def state(st):
    icons = [_summary(st, n) for n in st.names()]
    counts = {}
    for i in icons: counts[i["status"]] = counts.get(i["status"], 0) + 1
    lb = F.last(st)
    if lb: lb = {k: v for k, v in lb.items() if k != "glyphs"}
    return {"set": {"name": st.meta.get("name"), "style": st.style, "styles": M.STYLES, "axes": st.meta["axes"],
                    "next_axes": st.meta.get("next_axes", []), "root": st.root, "reasons": C.REASONS,
                    "thresholds": st.meta.get("thresholds", {})},
            "counts": counts, "icons": icons, "last_build": lb}

def glyphs(st, loc):
    out = {}
    for n in st.names():
        try: out[n] = geom.path_d([c for c, _ in M.at(st.icon(n), loc, st.style)])
        except Exception as e: out[n] = ""
    return out

def _side_d(segs, ci, si, dist, side):
    s = segs[si]; n = 1 if geom.is_line(s) else 12; sg = 1 if side == "left" else -1; pts = []
    for k in range(n + 1):
        t = k / n; p = geom.bez(s, t); nl = geom.left_of(geom.tangent(s, t))
        pts.append((p[0] + nl[0] * sg * dist, p[1] + nl[1] * sg * dist))
    return "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts)

def icon_detail(st, n, loc):
    ic = st.icon(n); style = st.style; w = loc["wght"]
    s = _summary(st, n)
    parts = []
    for p in ic.parts:
        cs = []
        for ci, (segs, closed, dot) in enumerate(ic.sk[p["id"]]):
            segrows = []
            for si, sg in enumerate(segs):
                if p["kind"] == "stroke":
                    l, r, why = ic.sides(p, ci, si, w, style)
                    ent = (ic.settings.get("sides", {}).get(p["id"], {}) or {}).get(f"{ci}.{si}", {})
                    segrows.append({"si": si, "d": geom.seg_d(sg), "left": round(l, 1), "right": round(r, 1), "tier": why["tier"],
                                    "why": why["why"], "hold": why.get("hold"), "by": why.get("by"),
                                    "left_d": _side_d(segs, ci, si, l, "left"), "right_d": _side_d(segs, ci, si, r, "right"),
                                    "pinned": ent.get("hold", {}), "amounts": sorted(ent.get("amount", {}).keys())})
                else:
                    segrows.append({"si": si, "d": geom.seg_d(sg)})
            row = {"ci": ci, "closed": closed, "segments": segrows, "dot": dot}
            if closed and p["kind"] == "stroke": row["counter_side"] = ic.counter_side(p["id"], ci)
            if not closed and p["kind"] == "stroke" and segs:
                (e, why) = ic.ends(p, ci, w); row["ends"] = {"start": e[0], "end": e[1], "tier": why["tier"], "why": why["why"]}
            cs.append(row)
        parts.append({"id": p["id"], "kind": p["kind"], "role": p.get("role") or {}, "width": p.get("width"),
                      "cap": p.get("cap"), "join": p.get("join"), "contours": cs,
                      "width_here": round(ic.width(p, w), 1) if p["kind"] == "stroke" else None})
    o = M.at(ic, loc, style)
    outline = [{"d": geom.path_d([c]), "role": i["role"], "part": i["part"]} for c, i in o]
    refs = st.references(n); ref = None
    if int(w) in refs:
        polys = R.drawing_polys(open(refs[int(w)]).read())
        ref = {"wght": int(w), "d": geom.path_d(polys), "score": FT.score(ic, style, w, polys, loc["FILL"])}
    others = [x for x in st.names() if x != n]
    return dict(s, loc=loc, parts=parts, outline=outline, all_d=geom.path_d([c for c, _ in o]),
                refs=sorted(refs), ref=ref, siblings=others, source_url=f"/api/source/{n}")

# ---- edits ------------------------------------------------------------------------

def _seg(settings, part, ci, si):
    return settings.setdefault("sides", {}).setdefault(part, {}).setdefault(f"{ci}.{si}", {})

def _prune(settings):
    sd = settings.get("sides", {})
    for pid in list(sd):
        for k in list(sd[pid]):
            e = sd[pid][k]
            for f in ("hold", "amount"):
                if f in e and not e[f]: e.pop(f)
            if not e.get("hold") and not e.get("amount"): sd[pid].pop(k)
        if not sd[pid]: sd.pop(pid)
    if "sides" in settings and not settings["sides"]: settings.pop("sides")
    en = settings.get("ends", {})
    for pid in list(en):
        for k in list(en[pid]):
            if not en[pid][k]: en[pid].pop(k)
        if not en[pid]: en.pop(pid)
    if "ends" in settings and not settings["ends"]: settings.pop("ends")
    return settings

def edit(st, n, body):
    act = body["action"]; s = st.settings(n)
    if act == "pin":       # intent: which side holds; scope along wght or at one weight
        e = _seg(s, body["part"], body["ci"], body["si"]); h = e.setdefault("hold", {})
        key = "*" if body.get("scope", "along") == "along" else M.wkey(body["wght"])
        if body.get("side"):
            h[key] = body["side"]; e["by"] = body.get("by", "manual")
            if key == "*":      # an along-axis pin replaces the per-weight ones
                for k in [k for k in h if k != "*"]: h.pop(k)
        else: h.pop(key, None)
        if body.get("all_segments"):
            ic = st.icon(n); segs = ic.sk[body["part"]][body["ci"]][0]
            for si in range(len(segs)):
                e2 = _seg(s, body["part"], body["ci"], si); e2["hold"] = copy.deepcopy(e["hold"]); e2["by"] = e.get("by", "manual")
    elif act == "amount":  # amount: exact distances at one weight
        e = _seg(s, body["part"], body["ci"], body["si"])
        e.setdefault("amount", {})[M.wkey(body["wght"])] = [float(body["left"]), float(body["right"])]; e["by"] = "manual"
    elif act == "clear":
        sd = s.get("sides", {}).get(body["part"], {})
        if "si" in body and body["si"] is not None: sd.pop(f"{body['ci']}.{body['si']}", None)
        else:
            for k in [k for k in sd if body.get("ci") is None or k.startswith(f"{body['ci']}.")]: sd.pop(k)
        if body.get("ci") is not None and "si" not in body:
            s.get("ends", {}).get(body["part"], {}).pop(str(body["ci"]), None)
    elif act == "ends":
        en = s.setdefault("ends", {}).setdefault(body["part"], {}).setdefault(str(body["ci"]), {})
        en[M.wkey(body["wght"])] = [float(body["start"]), float(body["end"])]
    elif act == "review":
        if body.get("accept"):
            s.pop("review", None); st.save_settings(n, _prune(s))
            s = st.settings(n); s["review"] = {"accepted": st.fingerprint(n)}
        else: s.pop("review", None)
    elif act == "match":   # copy settings from a sibling onto parts that match by name
        src = st.settings(body["from"]); ic = st.icon(n); copied = 0
        for key in ("sides", "ends"):
            for pid, v in (src.get(key) or {}).items():
                if pid in ic.sk:
                    s.setdefault(key, {})[pid] = copy.deepcopy(v); copied += 1
        st.save_settings(n, _prune(s)); return {"copied": copied}
    elif act == "reference":
        st.add_reference(n, body["wght"], body["svg"]); return {"ok": True}
    elif act == "fit":
        ic = st.icon(n); refs = st.references(n); w = int(body["wght"])
        if w not in refs: return {"error": f"No reference drawing at wght {w}. Add one first."}
        polys = R.drawing_polys(open(refs[w]).read())
        before = FT.score(ic, st.style, w, polys)
        sides, ends = FT.fit(ic, st.style, w, polys)
        trial = FT.apply(copy.deepcopy(ic.settings), sides, ends, w)
        ic2 = M.Icon(n, ic.parts, trial)
        after = FT.score(ic2, st.style, w, polys)
        res = {"before": before, "after": after, "sides": sum(len(v) for v in sides.values()),
               "ends": sum(len(v) for v in ends.values()),
               "after_d": geom.path_d([c for c, _ in ic2.outline({"wght": w, "FILL": 0}, st.style)])}
        if body.get("apply"):
            st.save_settings(n, _prune(trial)); res["applied"] = True
        return res
    else:
        return {"error": f"Unknown action {act}"}
    st.save_settings(n, _prune(s))
    return {"ok": True}

# ---- HTTP -------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    st = None
    def log_message(self, *a): pass

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else (json.dumps(body) if ctype == "application/json" else body).encode()
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(data)

    def _file(self, path):
        if not os.path.isfile(path): return self._send(404, {"error": "not found"})
        ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
        if path.endswith(".ttf"): ctype = "font/ttf"
        self._send(200, open(path, "rb").read(), ctype)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path); q = urllib.parse.parse_qs(u.query); p = u.path
        try:
            if p in ("/", "/index.html"): return self._file(os.path.join(APP_DIR, "index.html"))
            if p.startswith("/app/"):
                f = os.path.normpath(os.path.join(APP_DIR, p[5:]))
                if not f.startswith(APP_DIR): return self._send(403, {"error": "no"})
                return self._file(f)
            if p == "/api/state": return self._send(200, state(self.st))
            if p == "/api/glyphs": return self._send(200, glyphs(self.st, _loc(q)))
            m = re.match(r"^/api/icon/([a-z0-9_]+)$", p)
            if m: return self._send(200, icon_detail(self.st, m.group(1), _loc(q)))
            m = re.match(r"^/api/source/([a-z0-9_]+)$", p)
            if m: return self._send(200, self.st.source_text(m.group(1)), "image/svg+xml")
            if p.startswith("/builds/"):
                f = os.path.normpath(os.path.join(self.st.builds_dir(), urllib.parse.unquote(p[8:])))
                if not f.startswith(self.st.builds_dir()): return self._send(403, {"error": "no"})
                return self._file(f)
            return self._send(404, {"error": "not found"})
        except Exception as e:
            return self._send(500, {"error": f"{type(e).__name__}: {e}"})

    def do_POST(self):
        u = urllib.parse.urlparse(self.path); p = u.path
        n = int(self.headers.get("Content-Length", 0)); body = json.loads(self.rfile.read(n) or b"{}")
        try:
            with LOCK:
                if p == "/api/import":
                    rows = [self.st.add_icon(f["name"], f["text"]) for f in body.get("files", [])]
                    return self._send(200, {"rows": rows})
                if p == "/api/style":
                    if body.get("style") not in M.STYLES: return self._send(400, {"error": "unknown style"})
                    self.st.meta["style"] = body["style"]; self.st.save_meta(); self.st._icons.clear()
                    return self._send(200, {"ok": True})
                if p == "/api/build":
                    s = F.build(self.st); s.pop("glyphs", None); return self._send(200, s)
                m = re.match(r"^/api/icon/([a-z0-9_]+)/edit$", p)
                if m: return self._send(200, edit(self.st, m.group(1), body))
            return self._send(404, {"error": "not found"})
        except Exception as e:
            import traceback; traceback.print_exc()
            return self._send(500, {"error": f"{type(e).__name__}: {e}"})

def serve(st, port=8960, open_browser=True):
    Handler.st = st
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"Variance is running at {url}  (set: {st.root})\nPress Ctrl+C to stop.")
    if open_browser and not os.environ.get("VARIANCE_NO_BROWSER"):
        try: webbrowser.open(url)
        except Exception: pass
    try: httpd.serve_forever()
    except KeyboardInterrupt: pass
