// Variance app. Plain JS, no build step. Talks to `python -m variance serve`.
"use strict";

const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const STATUS = {
  blocked: "Blocked", review: "Needs review", good: "Looks good", reviewed: "Reviewed", stale: "Stale",
};
const ORDER = ["blocked", "stale", "review", "good", "reviewed"];
const MASTERS = [100, 400, 700];

const S = {
  state: null, view: "library", loc: { wght: 400, FILL: 0 }, statusFilter: null,
  queueReason: null, queueSel: 0,
  ed: { name: null, wght: 400, FILL: 0, part: null, ci: 0, si: 0, side: null, scope: "along",
        layers: { skeleton: true, ref: true, grid: true, sides: true }, fit: null, data: null },
  proof: { wght: 400, FILL: 0 }, lastImport: null, building: false, lastBuild: null,
};

async function api(path, body) {
  const r = await fetch(path, body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {});
  const j = await r.json();
  if (j && j.error) throw new Error(j.error);
  return j;
}
function toast(msg) {
  const t = $("#toast"); t.textContent = msg; t.classList.add("show");
  clearTimeout(toast._t); toast._t = setTimeout(() => t.classList.remove("show"), 2200);
}
function chip(status) { return `<span class="chip st-${status}"><span class="dot"></span>${STATUS[status]}</span>`; }
function reasonChip(code, sev) {
  const r = S.state.set.reasons[code] || code;
  return `<span class="chip ${sev === "block" ? "st-blocked" : "st-review"}">${esc(r)}</span>`;
}
function glyphSvg(d, cls = "") { return `<svg viewBox="0 0 960 960" class="${cls}" aria-hidden="true"><path d="${d}"/></svg>`; }

async function refresh() {
  S.state = await api("/api/state");
  $("#setname").textContent = S.state.set.name + " · " + (S.state.set.style === "pen" ? "Pen style" : "Anchored style");
  const q = (S.state.counts.blocked || 0) + (S.state.counts.review || 0) + (S.state.counts.stale || 0);
  $("#qcount").textContent = q || "";
}

// ---------------------------------------------------------------- routing
function route() {
  const h = (location.hash || "#library").slice(1);
  const [view, arg] = h.split(/-(.+)/);
  S.view = view || "library";
  document.querySelectorAll(".tabs a").forEach((a) => a.classList.toggle("on", a.dataset.view === (S.view === "icon" ? "queue" : S.view)));
  if (S.view === "icon") { if (S.ed.name !== arg) { S.ed.name = arg; S.ed.part = null; S.ed.side = null; S.ed.fit = null; } }
  render();
}
window.addEventListener("hashchange", route);

async function render() {
  if (!S.state) await refresh();
  const v = $("#view");
  try {
    if (S.view === "library") await renderLibrary(v);
    else if (S.view === "queue") await renderQueue(v);
    else if (S.view === "icon") await renderEditor(v);
    else if (S.view === "style") renderStyle(v);
    else if (S.view === "proof") await renderProof(v);
    else if (S.view === "export") renderExport(v);
    else if (S.view === "import") renderImport(v);
    else await renderLibrary(v);
  } catch (e) {
    v.innerHTML = `<div class="page"><div class="card bar"><b>Something went wrong.</b> <span class="muted">${esc(e.message)}</span></div></div>`;
  }
}

// ---------------------------------------------------------------- library
let glyphReq = 0;
async function renderLibrary(v) {
  const st = S.state;
  if (!st.icons.length) {
    v.innerHTML = `<div class="page"><div class="card empty">
      <h1>No icons yet</h1>
      <p class="muted">Import SVGs drawn with live strokes, from Figma, Illustrator or by hand. Outlined files work too; they import as fitted solids.</p>
      <button class="btn primary" onclick="location.hash='#import'">Import SVGs</button></div></div>`;
    return;
  }
  const counts = ORDER.filter((s) => st.counts[s]).map((s) =>
    `<button class="chip st-${s} ${S.statusFilter === s ? "on" : ""}" data-f="${s}">${STATUS[s]} ${st.counts[s]}</button>`).join("");
  v.innerHTML = `<div class="page">
    <div class="card bar">
      <h3>Show all at</h3>
      <label>wght <input type="range" id="lw" min="100" max="700" step="1" value="${S.loc.wght}"><span class="val" id="lwv">${S.loc.wght}</span></label>
      <label>FILL <input type="range" id="lf" min="0" max="1" step="0.05" value="${S.loc.FILL}" style="width:110px"><span class="val" id="lfv">${S.loc.FILL}</span></label>
      <span class="muted">${st.set.next_axes.join(" and ")} next</span>
      <span class="spacer"></span>
      <div style="display:flex;gap:6px;flex-wrap:wrap">${counts}</div>
    </div>
    <div class="grid" id="grid">${st.icons.filter((i) => !S.statusFilter || i.status === S.statusFilter).map((i) => `
      <button class="tile" data-n="${i.name}" title="${esc(i.name)} · ${STATUS[i.status]}">
        <span class="dot st-${i.status}"></span>${glyphSvg("", "g")}<span class="nm">${esc(i.name)}</span></button>`).join("")}
    </div></div>`;
  v.querySelectorAll("[data-f]").forEach((b) => b.onclick = () => { S.statusFilter = S.statusFilter === b.dataset.f ? null : b.dataset.f; renderLibrary(v); });
  v.querySelectorAll(".tile").forEach((t) => t.onclick = () => location.hash = "#icon-" + t.dataset.n);
  const upd = async () => {
    const id = ++glyphReq;
    const g = await api(`/api/glyphs?wght=${S.loc.wght}&FILL=${S.loc.FILL}`);
    if (id !== glyphReq) return;
    v.querySelectorAll(".tile").forEach((t) => { const p = t.querySelector("path"); if (p) p.setAttribute("d", g[t.dataset.n] || ""); });
  };
  let raf = 0;
  const onIn = () => {
    S.loc.wght = +$("#lw").value; S.loc.FILL = +$("#lf").value;
    $("#lwv").textContent = S.loc.wght; $("#lfv").textContent = S.loc.FILL;
    cancelAnimationFrame(raf); raf = requestAnimationFrame(upd);
  };
  $("#lw").oninput = onIn; $("#lf").oninput = onIn;
  await upd();
}

// ---------------------------------------------------------------- queue
async function renderQueue(v) {
  const st = S.state;
  const open = st.icons.filter((i) => ["blocked", "review", "stale"].includes(i.status));
  const reasons = {};
  open.forEach((i) => i.reasons.forEach((r) => reasons[r] = (reasons[r] || 0) + 1));
  const rows = open.filter((i) => !S.queueReason || i.reasons.includes(S.queueReason))
    .sort((a, b) => (b.status === "blocked") - (a.status === "blocked") || b.risk - a.risk || a.name.localeCompare(b.name));
  S.queueRows = rows;
  if (S.queueSel >= rows.length) S.queueSel = Math.max(0, rows.length - 1);
  v.innerHTML = `<div class="page">
    <div style="display:flex;align-items:baseline;gap:12px;flex-wrap:wrap"><h1>Review queue</h1>
      <span class="muted">${open.length} to review, worst first</span><span class="spacer"></span>
      <span class="kbd">J / K move · A accept · F fix</span></div>
    ${open.length ? `<div class="queue">
      <div class="card rail"><h3>Reason</h3>
        <button class="${!S.queueReason ? "on" : ""}" data-r="">All <span>${open.length}</span></button>
        ${Object.entries(reasons).sort((a, b) => b[1] - a[1]).map(([r, n]) =>
          `<button class="${S.queueReason === r ? "on" : ""}" data-r="${r}">${esc(st.set.reasons[r] || r)} <span>${n}</span></button>`).join("")}
      </div>
      <div class="rows">${rows.map((i, k) => {
        const f = i.findings.find((x) => x.severity === "block") || i.findings[0] || {};
        const loc = f.loc || { wght: 400, FILL: 0 };
        return `<div class="card row ${k === S.queueSel ? "sel" : ""}" data-n="${i.name}" data-k="${k}">
          <div><b>${esc(i.name)}</b><div class="kbd">#${k + 1} · wght ${loc.wght}${loc.FILL ? " FILL 1" : ""}</div></div>
          <div data-g="${i.name}" data-w="${loc.wght}" data-f="${loc.FILL}">${glyphSvg("")}</div>
          <div class="why"><div class="chips">${[...new Set(i.findings.map((x) => x.code + "|" + x.severity))].map((c) => reasonChip(...c.split("|"))).join("")}</div>
            <div class="muted">${esc(f.text || "")}</div></div>
          <div class="actions">${i.status !== "blocked" ? `<button class="btn" data-a="accept">Accept</button>` : ""}<button class="btn soft" data-a="fix">Fix</button></div>
        </div>`; }).join("")}</div></div>`
      : `<div class="card empty"><h1>Nothing to review</h1><p class="muted">Every icon passes its checks or has been reviewed. Proof the set, then export.</p>
         <div style="display:flex;gap:8px"><a class="btn" href="#proof">Proof</a><a class="btn primary" href="#export">Export</a></div></div>`}
  </div>`;
  v.querySelectorAll("[data-r]").forEach((b) => b.onclick = () => { S.queueReason = b.dataset.r || null; S.queueSel = 0; renderQueue(v); });
  v.querySelectorAll(".row").forEach((r) => {
    r.onclick = (e) => { S.queueSel = +r.dataset.k; v.querySelectorAll(".row").forEach((x) => x.classList.toggle("sel", x === r)); };
    r.querySelectorAll("[data-a]").forEach((b) => b.onclick = (e) => { e.stopPropagation(); queueAct(b.dataset.a, r.dataset.n); });
  });
  // glyph renders at each row's risky location
  const locs = {};
  v.querySelectorAll("[data-g]").forEach((el) => { const k = el.dataset.w + "|" + el.dataset.f; (locs[k] = locs[k] || []).push(el); });
  for (const [k, els] of Object.entries(locs)) {
    const [w, f] = k.split("|");
    const g = await api(`/api/glyphs?wght=${w}&FILL=${f}`);
    els.forEach((el) => el.querySelector("path").setAttribute("d", g[el.dataset.g] || ""));
  }
}
async function queueAct(a, name) {
  if (a === "fix") { location.hash = "#icon-" + name; return; }
  await api(`/api/icon/${name}/edit`, { action: "review", accept: true });
  toast(`Accepted ${name}`); await refresh(); render();
}
document.addEventListener("keydown", (e) => {
  if (e.target.matches("input, textarea, select")) return;
  if (S.view === "queue" && S.queueRows && S.queueRows.length) {
    if (e.key === "j") { S.queueSel = Math.min(S.queueSel + 1, S.queueRows.length - 1); renderQueue($("#view")); }
    if (e.key === "k") { S.queueSel = Math.max(S.queueSel - 1, 0); renderQueue($("#view")); }
    const cur = S.queueRows[S.queueSel];
    if (e.key === "a" && cur && cur.status !== "blocked") queueAct("accept", cur.name);
    if (e.key === "f" && cur) queueAct("fix", cur.name);
  }
  if (S.view === "icon") {
    if (e.key === "Escape") { S.ed.side = null; drawCanvas(); renderInspector(); }
    if (["1", "2", "3"].includes(e.key)) { S.ed.wght = MASTERS[+e.key - 1]; loadEditor(); }
  }
});

// ---------------------------------------------------------------- editor
async function renderEditor(v) {
  v.innerHTML = `<div class="editor">
    <div class="ed-head" id="ed-head"></div>
    <div class="card parts" id="ed-parts"></div>
    <div class="stage">
      <div class="card bar" id="ed-loc"></div>
      <div class="canvas-wrap"><svg class="canvas" id="cv" viewBox="-40 -40 1040 1040" role="img" aria-label="Icon canvas"></svg></div>
      <div class="card findings" id="ed-find"></div>
    </div>
    <div class="card inspector" id="ed-insp"></div>
  </div>`;
  await loadEditor();
}
async function loadEditor() {
  const e = S.ed;
  e.data = await api(`/api/icon/${e.name}?wght=${e.wght}&FILL=${e.FILL}`);
  if (!e.part && e.data.parts.length) {
    const f = e.data.findings.find((x) => x.part) || {};
    e.part = f.part || e.data.parts[0].id;
    if (f.ci != null) e.ci = f.ci; if (f.si != null) e.si = f.si;
  }
  renderHead(); renderParts(); renderLoc(); drawCanvas(); renderFindings(); renderInspector();
}
function renderHead() {
  const d = S.ed.data;
  $("#ed-head").innerHTML = `<a class="btn small" href="#queue">← Queue</a><h1>${esc(d.name)}</h1>${chip(d.status)}
    <span class="mono muted">${d.cp}</span><span class="spacer"></span>
    <a class="btn small" href="${d.source_url}" target="_blank" rel="noopener">Source SVG</a>
    ${d.status === "reviewed" ? `<button class="btn" id="unaccept">Reopen</button>`
      : d.status !== "blocked" ? `<button class="btn primary" id="accept">Accept</button>` : ""}`;
  const a = $("#accept"), u = $("#unaccept");
  if (a) a.onclick = async () => { await api(`/api/icon/${d.name}/edit`, { action: "review", accept: true }); toast("Accepted"); await refresh(); nextInQueue(); };
  if (u) u.onclick = async () => { await api(`/api/icon/${d.name}/edit`, { action: "review", accept: false }); await refresh(); loadEditor(); };
}
function nextInQueue() {
  const open = S.state.icons.filter((i) => ["blocked", "review", "stale"].includes(i.status) && i.name !== S.ed.name)
    .sort((a, b) => (b.status === "blocked") - (a.status === "blocked") || b.risk - a.risk);
  location.hash = open.length ? "#icon-" + open[0].name : "#queue";
}
function renderParts() {
  const d = S.ed.data;
  $("#ed-parts").innerHTML = `<h3>Parts</h3>` + d.parts.map((p) => {
    const role = Object.keys(p.role).join(" ");
    const k = p.kind === "stroke" ? `stroke · ${p.contours.some((c) => c.closed) ? "closed" : "open"} · ${p.cap}` : "solid";
    const manual = p.contours.some((c) => c.segments.some((s) => s.tier === "Manual"));
    return `<button class="${p.id === S.ed.part ? "on" : ""}" data-p="${p.id}"><span>${esc(p.id)}${manual ? ' <span class="tier Manual">manual</span>' : ""}</span>
      <span class="k">${k}${role ? " · " + esc(role) : ""}</span></button>`;
  }).join("") + `<hr class="divider"><p class="hint">Click a part, then click one of its dashed sides on the canvas to pin it.</p>`;
  $("#ed-parts").querySelectorAll("[data-p]").forEach((b) => b.onclick = () => { S.ed.part = b.dataset.p; S.ed.ci = 0; S.ed.si = 0; S.ed.side = null; renderParts(); drawCanvas(); renderInspector(); });
}
function renderLoc() {
  const e = S.ed;
  $("#ed-loc").innerHTML = `<h3>Master</h3>
    <div class="seg" role="group" aria-label="Weight">${MASTERS.map((w, i) => `<button class="${e.wght === w ? "on" : ""}" data-w="${w}" title="Key ${i + 1}">wght ${w}</button>`).join("")}</div>
    <div class="seg" role="group" aria-label="Fill">${[0, 1].map((f) => `<button class="${e.FILL === f ? "on" : ""}" data-fl="${f}">FILL ${f}</button>`).join("")}</div>
    <span class="spacer"></span>
    <div class="layers">${Object.entries({ skeleton: "Skeleton", sides: "Sides", ref: "Reference", grid: "Pixel grid" }).map(([k, n]) =>
      `<button class="chip ${e.layers[k] ? "on" : ""}" data-l="${k}" style="color:var(--muted)">${n}</button>`).join("")}</div>`;
  $("#ed-loc").querySelectorAll("[data-w]").forEach((b) => b.onclick = () => { e.wght = +b.dataset.w; e.fit = null; loadEditor(); });
  $("#ed-loc").querySelectorAll("[data-fl]").forEach((b) => b.onclick = () => { e.FILL = +b.dataset.fl; loadEditor(); });
  $("#ed-loc").querySelectorAll("[data-l]").forEach((b) => b.onclick = () => { e.layers[b.dataset.l] = !e.layers[b.dataset.l]; renderLoc(); drawCanvas(); });
}
function partOf(id) { return S.ed.data.parts.find((p) => p.id === id); }
function midOfD(d) {
  const n = d.replace(/[MLC]/g, " ").trim().split(/[\s,]+/).map(Number);
  const pts = []; for (let i = 0; i + 1 < n.length; i += 2) pts.push([n[i], n[i + 1]]);
  return pts[Math.floor(pts.length / 2)] || [0, 0];
}
function drawCanvas() {
  const e = S.ed, d = e.data, cv = $("#cv"); if (!cv || !d) return;
  let g = "";
  if (e.layers.grid) {
    g += `<g class="c-grid">`;
    for (let i = 0; i <= 24; i++) { const x = i * 40, k = i % 4 === 0 ? "key" : ""; g += `<line class="${k}" x1="${x}" y1="0" x2="${x}" y2="960"/><line class="${k}" x1="0" y1="${x}" x2="960" y2="${x}"/>`; }
    g += `</g>`;
  }
  if (e.layers.ref && d.ref) g += `<path class="c-ref" d="${d.ref.d}"/>`;
  g += `<path class="c-ink ${e.layers.ref && d.ref ? "dim" : ""}" d="${d.all_d}"/>`;
  if (e.layers.ref && d.ref) g += `<path class="c-ref-line" d="${d.ref.d}"/>`;
  if (e.fit && e.fit.after_d && e.fit.wght === e.wght) g += `<path class="c-fit" d="${e.fit.after_d}"/>`;
  if (e.layers.skeleton) {
    d.parts.forEach((p) => p.contours.forEach((c) => c.segments.forEach((s) =>
      g += `<path class="c-skel ${p.id === e.part ? "sel" : ""}" d="${s.d}" data-p="${p.id}" data-c="${c.ci}" data-s="${s.si}"/>`)));
  }
  const p = partOf(e.part);
  if (p && p.kind === "stroke" && e.layers.sides) {
    p.contours.forEach((c) => c.segments.forEach((s) => {
      ["left", "right"].forEach((side) => {
        const held = s.hold === side && s.tier === "Manual";
        const sel = e.ci === c.ci && e.si === s.si && e.side === side;
        g += `<path class="c-side ${held ? "held" : ""} ${sel ? "sel" : ""}" d="${s[side + "_d"]}"/>`;
        g += `<path class="c-hit" d="${s[side + "_d"]}" data-c="${c.ci}" data-s="${s.si}" data-side="${side}"><title>${side} side · segment ${c.ci}.${s.si}</title></path>`;
        if (held) { const m = midOfD(s[side + "_d"]); g += `<circle class="c-pin held" cx="${m[0]}" cy="${m[1]}" r="12"/>`; }
      });
    }));
  }
  cv.innerHTML = g;
  cv.querySelectorAll(".c-hit").forEach((h) => h.onclick = (ev) => {
    e.ci = +h.dataset.c; e.si = +h.dataset.s; e.side = h.dataset.side; drawCanvas(); renderInspector();
  });
  cv.querySelectorAll(".c-skel").forEach((h) => h.onclick = () => {
    if (e.part !== h.dataset.p) { e.part = h.dataset.p; e.side = null; renderParts(); }
    e.ci = +h.dataset.c; e.si = +h.dataset.s; drawCanvas(); renderInspector();
  });
}
function renderFindings() {
  const d = S.ed.data;
  $("#ed-find").innerHTML = `<h3>Findings</h3>` + (d.findings.length ? d.findings.map((f, i) =>
    `<button class="finding" data-i="${i}"><span class="dot sev-${f.severity}"></span><span>${esc(f.text)}</span>
     <span class="mono muted">${f.loc ? "wght " + f.loc.wght + (f.loc.FILL ? " FILL 1" : "") : ""}</span></button>`).join("")
    : `<p class="muted">No findings. Every check passes at every master.</p>`);
  $("#ed-find").querySelectorAll("[data-i]").forEach((b) => b.onclick = () => {
    const f = d.findings[+b.dataset.i];
    if (f.part) S.ed.part = f.part; if (f.ci != null) S.ed.ci = f.ci; if (f.si != null) S.ed.si = f.si;
    if (f.loc) { S.ed.wght = f.loc.wght; S.ed.FILL = f.loc.FILL; }
    loadEditor();
  });
}
async function edit(body, msg) {
  const r = await api(`/api/icon/${S.ed.name}/edit`, body);
  if (msg) toast(msg);
  await refresh(); await loadEditor();
  return r;
}
function renderInspector() {
  const e = S.ed, d = e.data, el = $("#ed-insp"); if (!el || !d) return;
  const p = partOf(e.part);
  let h = `<h3>Inspector · wght ${e.wght}${e.FILL ? " · FILL 1" : ""}</h3>`;
  if (!p) { el.innerHTML = h + `<p class="muted">Select a part.</p>`; return; }
  h += `<div><b>${esc(p.id)}</b> <span class="muted">${p.kind}${p.kind === "stroke" ? ` · ${p.width_here} units here (${(p.width_here / 40).toFixed(2)} px)` : ""}</span></div>`;
  if (p.kind !== "stroke") {
    h += `<p class="muted">Solids grow by half the width change (Style). Edge-by-edge moves for solids are next.</p>`;
    el.innerHTML = h + fitBlock() + matchBlock(); wireFit(); wireMatch(); return;
  }
  const c = p.contours[e.ci] || p.contours[0]; const s = c.segments[e.si] || c.segments[0];
  if (!s) { el.innerHTML = h; return; }
  const sideName = (side) => c.closed ? (side === c.counter_side ? "counter side" : "outside") : side;
  h += `<div class="hint">Segment ${c.ci}.${s.si}${c.closed ? " · closed" : " · open"}${e.side ? ` · <b>${sideName(e.side)}</b> selected` : ""}</div>
    <div class="kv">
      <span>${c.closed ? (c.counter_side === "left" ? "Left (counter)" : "Left (outside)") : "Left side"}</span><span class="v">${s.left}</span><span class="tier ${s.tier}">${s.tier}</span>
      <span>${c.closed ? (c.counter_side === "right" ? "Right (counter)" : "Right (outside)") : "Right side"}</span><span class="v">${s.right}</span><span class="tier ${s.tier}">${s.tier}</span>
    </div>
    <p class="hint">${esc(s.why)}${s.by && s.by !== "manual" ? ` · from ${esc(s.by)}` : ""}</p>
    <hr class="divider">
    <div style="display:grid;gap:8px"><h3>Which side holds</h3>
      <div class="seg" role="group" aria-label="Scope">
        <button class="${e.scope === "along" ? "on" : ""}" data-sc="along">Along wght</button>
        <button class="${e.scope === "here" ? "on" : ""}" data-sc="here">At wght ${e.wght} only</button></div>
      <div class="pins">${["left", "centre", "right"].map((sd) =>
        `<button class="btn small ${s.tier === "Manual" && s.hold === sd ? "on" : ""}" data-pin="${sd}">${sd === "centre" ? "Centred" : "Hold " + (sd === "left" ? (c.closed ? (c.counter_side === "left" ? "counter" : "outside") : "left") : (c.closed ? (c.counter_side === "right" ? "counter" : "outside") : "right"))}</button>`).join("")}</div>
      <label class="hint"><input type="checkbox" id="allsegs"> Apply to every segment of this contour</label>
      <p class="hint">A pin is intent: it carries along wght (and later GRAD). The exact amount follows the rule unless you set one.</p>
    </div>
    <hr class="divider">
    <div style="display:grid;gap:8px"><h3>Exact amount at wght ${e.wght}</h3>
      <div style="display:flex;gap:8px;align-items:center"><span class="hint">L</span><input class="num" id="amt-l" type="number" step="0.5" value="${s.left}">
        <span class="hint">R</span><input class="num" id="amt-r" type="number" step="0.5" value="${s.right}"><button class="btn small" id="amt-set">Set</button></div>
      <p class="hint">Units are 1/960 em: 40 units = 1 px at 24 px.</p>
    </div>
    ${c.ends ? `<hr class="divider"><div style="display:grid;gap:8px"><h3>Ends at wght ${e.wght}</h3>
      <div style="display:flex;gap:8px;align-items:center"><span class="hint">Start</span><input class="num" id="end-s" type="number" step="1" value="${c.ends.start}">
        <span class="hint">End</span><input class="num" id="end-e" type="number" step="1" value="${c.ends.end}"><button class="btn small" id="end-set">Set</button></div>
      <p class="hint">${esc(c.ends.why)} · <span class="tier ${c.ends.tier}">${c.ends.tier}</span>. + longer, − shorter.</p></div>` : ""}
    <div style="display:flex;gap:8px"><button class="btn small" id="reset-seg">Reset segment</button><button class="btn small" id="reset-part">Reset part</button></div>
    <hr class="divider">` + fitBlock() + matchBlock();
  el.innerHTML = h;
  el.querySelectorAll("[data-sc]").forEach((b) => b.onclick = () => { e.scope = b.dataset.sc; renderInspector(); });
  el.querySelectorAll("[data-pin]").forEach((b) => b.onclick = () => {
    const side = b.dataset.pin;
    const on = s.tier === "Manual" && s.hold === side;
    edit({ action: "pin", part: p.id, ci: c.ci, si: s.si, side: on ? null : side, scope: e.scope, wght: e.wght, all_segments: $("#allsegs").checked },
         on ? "Pin removed" : `Pinned: ${side === "centre" ? "centred" : side + " side holds"}${e.scope === "along" ? " along wght" : " at wght " + e.wght}`);
  });
  $("#amt-set").onclick = () => edit({ action: "amount", part: p.id, ci: c.ci, si: s.si, wght: e.wght, left: +$("#amt-l").value, right: +$("#amt-r").value }, "Amount set");
  if ($("#end-set")) $("#end-set").onclick = () => edit({ action: "ends", part: p.id, ci: c.ci, wght: e.wght, start: +$("#end-s").value, end: +$("#end-e").value }, "Ends set");
  $("#reset-seg").onclick = () => edit({ action: "clear", part: p.id, ci: c.ci, si: s.si }, "Segment back to the rule");
  $("#reset-part").onclick = () => edit({ action: "clear", part: p.id }, "Part back to the rule");
  wireFit(); wireMatch();
}
function fitBlock() {
  const e = S.ed, d = e.data;
  const has = d.refs.includes(e.wght);
  return `<div style="display:grid;gap:8px"><h3>Fit to a drawing</h3>
    ${d.ref ? `<div>Score at wght ${e.wght}: <span class="score">${d.ref.score == null ? "—" : Math.round(d.ref.score * 100) + "%"}</span> <span class="hint">of the drawing's edges within 0.25 px</span></div>` : ""}
    <p class="hint">${has ? "A drawing of this master is loaded (blue)." : `Draw or export this icon at wght ${e.wght} as an SVG, then load it. Variance fits its own settings to it.`}</p>
    <div style="display:flex;gap:8px;flex-wrap:wrap"><button class="btn small" id="ref-add">${has ? "Replace drawing" : "Load drawing…"}</button>
      ${has ? `<button class="btn small soft" id="fit-try">Fit</button>` : ""}</div>
    ${e.fit && e.fit.wght === e.wght ? `<div class="card" style="padding:10px;display:grid;gap:6px">
      <div>Before <span class="score">${Math.round((e.fit.before || 0) * 100)}%</span> → after <span class="score" style="color:var(--good)">${Math.round((e.fit.after || 0) * 100)}%</span></div>
      <div class="hint">${e.fit.sides} side settings, ${e.fit.ends} end settings. Green dashes show the fitted outline.</div>
      <div style="display:flex;gap:8px"><button class="btn small primary" id="fit-apply">Accept fit</button><button class="btn small" id="fit-cancel">Discard</button></div>
      <div class="hint">Accepting stores settings, not the drawing. The drawing stays as a reference for scoring.</div></div>` : ""}
  </div>`;
}
function wireFit() {
  const e = S.ed;
  const add = $("#ref-add");
  if (add) add.onclick = () => {
    const inp = $("#ref-input"); inp.value = "";
    inp.onchange = async () => {
      const f = inp.files[0]; if (!f) return;
      await api(`/api/icon/${e.name}/edit`, { action: "reference", wght: e.wght, svg: await f.text() });
      toast(`Drawing loaded for wght ${e.wght}`); await refresh(); loadEditor();
    };
    inp.click();
  };
  const t = $("#fit-try");
  if (t) t.onclick = async () => { const r = await api(`/api/icon/${e.name}/edit`, { action: "fit", wght: e.wght }); e.fit = { ...r, wght: e.wght }; drawCanvas(); renderInspector(); };
  const a = $("#fit-apply");
  if (a) a.onclick = async () => { await edit({ action: "fit", wght: e.wght, apply: true }, "Fit accepted as settings"); e.fit = null; };
  const c = $("#fit-cancel");
  if (c) c.onclick = () => { e.fit = null; drawCanvas(); renderInspector(); };
}
function matchBlock() {
  const d = S.ed.data;
  if (!d.siblings.length) return "";
  return `<hr class="divider"><div style="display:grid;gap:8px"><h3>Match sibling</h3>
    <div style="display:flex;gap:8px"><select id="sib" class="num" style="width:auto;flex:1">${d.siblings.map((s) => `<option>${esc(s)}</option>`).join("")}</select>
    <button class="btn small" id="sib-go">Copy settings</button></div>
    <p class="hint">Copies manual settings for parts with the same name.</p></div>`;
}
function wireMatch() {
  const b = $("#sib-go");
  if (b) b.onclick = async () => { const r = await edit({ action: "match", from: $("#sib").value }); toast(r.copied ? `Copied settings for ${r.copied} part(s)` : "No parts with matching names"); };
}

// ---------------------------------------------------------------- style
function renderStyle(v) {
  const st = S.state.set;
  v.innerHTML = `<div class="page">
    <h1>Style</h1><p class="muted">The set's house rule: the global tier. Changing it regenerates every icon; manual settings are kept.</p>
    <div class="styles">
      ${Object.entries(st.styles).map(([k, t]) => `<button class="card style-card ${st.style === k ? "on" : ""}" data-s="${k}">
        <h2>${k === "pen" ? "Pen" : "Anchored"}</h2><p class="muted">${esc(t.split(": ")[1])}</p>
        ${st.style === k ? '<span class="chip st-reviewed">In use</span>' : ""}</button>`).join("")}
      <div class="card style-card soon"><h2>Learn from my set</h2><p class="muted">Import a second style (a bold, a filled, a 16 px) and Variance learns the rule from the pair. Next.</p></div>
    </div>
    <div class="card" style="padding:14px;display:grid;gap:10px"><h3>Context table (semantic tier)</h3>
      <table><thead><tr><th>Context</th><th>wght 100</th><th>wght 400</th><th>wght 700</th><th>Source</th></tr></thead><tbody>
      ${st.style === "anchored" ? `
        <tr><td>Closed stroke, counter side</td><td>holds</td><td>default</td><td>holds</td><td>Context</td></tr>
        <tr><td>Closed stroke, outside</td><td>moves in</td><td>default</td><td>moves out</td><td>Context</td></tr>
        <tr><td>Lone stroke</td><td>centred</td><td>default</td><td>centred</td><td>Context</td></tr>`
      : `<tr><td>Every stroke</td><td>centred</td><td>default</td><td>centred</td><td>Style</td></tr>`}
        <tr><td>Stroke width (× drawn width)</td><td>0.34</td><td>1.00</td><td>1.66</td><td>Placeholder</td></tr>
        <tr><td>Solids</td><td colspan="3">grow by half the width change</td><td>Style</td></tr>
      </tbody></table>
      <p class="hint">Widths are placeholders, not Material's numbers. The learned anchor rule from research 06–08 plugs in here next.</p>
    </div></div>`;
  v.querySelectorAll("[data-s]").forEach((b) => b.onclick = async () => {
    if (b.dataset.s === st.style) return;
    await api("/api/style", { style: b.dataset.s }); toast("Style changed. Every icon regenerated; manual settings kept.");
    await refresh(); renderStyle(v);
  });
}

// ---------------------------------------------------------------- proof
let fontLoaded = null;
async function loadProofFont() {
  const lb = S.state.last_build; if (!lb) return false;
  if (fontLoaded === lb.sha256) return true;
  const ff = new FontFace("VarianceProof", `url(/builds/${encodeURI(lb.file)}?v=${lb.sha256.slice(0, 8)})`);
  await ff.load(); document.fonts.add(ff); fontLoaded = lb.sha256; return true;
}
async function renderProof(v) {
  const lb = S.state.last_build;
  if (!lb) {
    v.innerHTML = `<div class="page"><div class="card empty"><h1>Build the font to proof it</h1>
      <p class="muted">Proof uses the real exported font, so what you see here is what ships.</p><a class="btn primary" href="#export">Go to Export</a></div></div>`;
    return;
  }
  await loadProofFont();
  const names = Object.keys(lb.codepoints || {}).length ? Object.keys(lb.codepoints) : S.state.icons.map((i) => i.name);
  const fvs = () => `font-variation-settings: 'wght' ${S.proof.wght}, 'FILL' ${S.proof.FILL}`;
  v.innerHTML = `<div class="page">
    <div style="display:flex;align-items:baseline;gap:12px;flex-wrap:wrap"><h1>Proof</h1>
      <span class="muted">Build ${String(lb.number).padStart(4, "0")} · ${lb.icons} icons · <span class="mono">${lb.sha256.slice(0, 12)}</span></span></div>
    <div class="card bar"><h3>All at</h3>
      <label>wght <input type="range" id="pw" min="100" max="700" value="${S.proof.wght}"><span class="val" id="pwv">${S.proof.wght}</span></label>
      <label>FILL <input type="range" id="pf" min="0" max="1" step="0.05" value="${S.proof.FILL}" style="width:110px"><span class="val" id="pfv">${S.proof.FILL}</span></label>
      <button class="btn small" id="scrub">Scrub wght</button><span class="spacer"></span>
      <span class="hint">Rendered by the browser from the exported font file</span></div>
    <h3>Set</h3>
    <div class="proof-grid">${names.map((n) => `<div class="pg"><span class="glyph" style="${fvs()}">${esc(n)}</span><span class="kbd">${esc(n)}</span></div>`).join("")}</div>
    <h3>Sizes</h3>
    <div class="card waterfall">${[16, 20, 24, 32, 48].map((px) => `<div><span class="glyph" style="font-size:${px}px;${fvs()}">${names.slice(0, 8).map(esc).join(" ")}</span><span class="kbd">${px}px</span></div>`).join("")}</div>
    <h3>Light and dark grounds</h3>
    <div class="grounds"><div class="light">${names.slice(0, 10).map((n) => `<span class="glyph" style="font-size:24px;${fvs()}">${esc(n)}</span>`).join("")}</div>
      <div class="dark">${names.slice(0, 10).map((n) => `<span class="glyph" style="font-size:24px;${fvs()}">${esc(n)}</span>`).join("")}</div></div>
    <h3>Next to text</h3>
    <div class="card inline-text">Open <span class="glyph" style="${fvs()}">${esc(names[0])}</span> settings, then choose <span class="glyph" style="${fvs()}">${esc(names[1] || names[0])}</span> to continue. Typing an icon's name draws it (ligatures), as with Material Symbols.</div>
  </div>`;
  const upd = () => {
    S.proof.wght = +$("#pw").value; S.proof.FILL = +$("#pf").value; $("#pwv").textContent = S.proof.wght; $("#pfv").textContent = S.proof.FILL;
    v.querySelectorAll(".glyph").forEach((g) => g.style.fontVariationSettings = `'wght' ${S.proof.wght}, 'FILL' ${S.proof.FILL}`);
  };
  $("#pw").oninput = upd; $("#pf").oninput = upd;
  $("#scrub").onclick = () => {
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let t0 = null; const step = (t) => { if (!t0) t0 = t; const k = ((t - t0) / 2400) % 1; const w = Math.round(100 + 600 * (0.5 - 0.5 * Math.cos(k * 2 * Math.PI)));
      $("#pw").value = w; upd(); if (t - t0 < 4800 && S.view === "proof") requestAnimationFrame(step); };
    requestAnimationFrame(step);
  };
}

// ---------------------------------------------------------------- export
function renderExport(v) {
  const lb = S.lastBuild || S.state.last_build; const st = S.state;
  const blocked = st.icons.filter((i) => i.status === "blocked");
  const review = st.icons.filter((i) => i.status === "review" || i.status === "stale");
  v.innerHTML = `<div class="page">
    <h1>Export</h1>
    <div class="card bar"><div style="display:grid;gap:4px">
      <b>Variable font · wght 100–700 · FILL 0–1 · ${st.icons.length - blocked.length} icons</b>
      <span class="hint">TrueType with ligatures and Private Use code points, the six masters, and a .designspace that names them.</span></div>
      <span class="spacer"></span><button class="btn primary" id="build" ${S.building ? "disabled" : ""}>${S.building ? "Building…" : "Build font"}</button></div>
    ${blocked.length ? `<div class="card bar"><span class="chip st-blocked">${blocked.length} blocked</span><span>These icons are left out of the build: ${blocked.map((i) => `<a href="#icon-${i.name}">${esc(i.name)}</a>`).join(", ")}.</span></div>` : ""}
    ${review.length ? `<div class="card bar"><span class="chip st-review">${review.length} not reviewed</span><span>They ship as generated. <a href="#queue">Review them</a> first if you want a person to look.</span></div>` : ""}
    ${lb ? `<div class="summary">
        <div class="card stat"><span class="hint">Build</span><b>${String(lb.number).padStart(4, "0")}</b></div>
        <div class="card stat"><span class="hint">Icons</span><b>${lb.icons}</b></div>
        <div class="card stat"><span class="hint">Size</span><b>${(lb.bytes / 1024).toFixed(1)} KB</b></div>
        <div class="card stat"><span class="hint">Same as last build</span><b>${lb.same_as_last ? "Yes" : "No"}</b></div>
      </div>
      <div class="card" style="padding:14px;display:grid;gap:8px"><h3>File</h3>
        <a href="/builds/${encodeURI(lb.file)}" download>${esc(lb.file.split("/").pop())}</a>
        <div class="hash">SHA-256 ${lb.sha256}</div>
        <p class="hint">A rebuild with no source change gives the same hash. Saved under builds/${String(lb.number).padStart(4, "0")}/ in the set folder, with the masters and a .designspace.</p></div>
      <div class="card" style="padding:14px;display:grid;gap:8px"><h3>Changelog</h3>
        ${["added", "changed", "removed"].map((k) => `<div><b>${k[0].toUpperCase() + k.slice(1)}</b> <span class="muted">${(lb.changelog[k] || []).map(esc).join(", ") || "none"}</span></div>`).join("")}</div>
      ${lb.excluded && lb.excluded.length ? `<div class="card" style="padding:14px"><h3>Left out</h3><table><tbody>${lb.excluded.map((x) => `<tr><td><a href="#icon-${x.name}">${esc(x.name)}</a></td><td class="muted">${esc(x.why.join(" "))}</td></tr>`).join("")}</tbody></table></div>` : ""}`
      : `<p class="muted">No builds yet.</p>`}
  </div>`;
  $("#build").onclick = async () => {
    S.building = true; renderExport(v);
    try { const r = await api("/api/build", {}); S.lastBuild = r; toast(r.same_as_last ? "Built: same as last build" : `Built ${String(r.number).padStart(4, "0")}`); }
    catch (e) { toast(e.message); }
    S.building = false; await refresh(); S.lastBuild = null; renderExport(v);
  };
}

// ---------------------------------------------------------------- import
function renderImport(v) {
  const r = S.lastImport;
  v.innerHTML = `<div class="page"><h1>Import</h1>
    <div class="drop" id="drop"><b>Drop SVG files here</b><span class="muted">or</span><button class="btn primary" id="pick">Choose files</button>
      <p class="hint">Live strokes import exactly: the stroke's centre-line becomes the skeleton. Name layers with the grammar
      <code>name cut gap=1</code>, <code>name knockout</code>, <code>name solid</code>, <code>name open</code>. Re-importing a name merges: settings on parts that still exist are kept.</p></div>
    ${r ? `<div class="card" style="padding:14px;display:grid;gap:10px"><h3>Import report</h3>
      <div style="display:flex;gap:8px;flex-wrap:wrap">${["exact", "guesses", "fitted", "merged", "failed"].filter((k) => r.rows.some((x) => x.result === k)).map((k) =>
        `<span class="chip ${k === "failed" ? "st-blocked" : k === "exact" || k === "merged" ? "st-good" : "st-review"}">${k} ${r.rows.filter((x) => x.result === k).length}</span>`).join("")}</div>
      <table><thead><tr><th>Icon</th><th>Result</th><th>Notes</th></tr></thead><tbody>
      ${r.rows.map((x) => `<tr><td>${x.result === "failed" ? esc(x.name) : `<a href="#icon-${x.name}">${esc(x.name)}</a>`}</td><td>${x.result}</td>
        <td class="muted">${x.notes.map((n) => esc(n.text)).join("<br>") || "—"}</td></tr>`).join("")}</tbody></table>
      <div><a class="btn" href="#library">Open library</a> <a class="btn soft" href="#queue">Review queue</a></div></div>` : ""}
  </div>`;
  const drop = $("#drop");
  drop.ondragover = (e) => { e.preventDefault(); drop.classList.add("over"); };
  drop.ondragleave = () => drop.classList.remove("over");
  drop.ondrop = (e) => { e.preventDefault(); drop.classList.remove("over"); importFiles([...e.dataTransfer.files]); };
  $("#pick").onclick = () => $("#file-input").click();
}
async function importFiles(files) {
  files = files.filter((f) => /\.svg$/i.test(f.name));
  if (!files.length) { toast("No SVG files"); return; }
  const payload = await Promise.all(files.map(async (f) => ({ name: f.name, text: await f.text() })));
  S.lastImport = await api("/api/import", { files: payload });
  await refresh(); toast(`Imported ${files.length} file(s)`);
  if (location.hash !== "#import") location.hash = "#import"; else render();
}
$("#import-btn").onclick = () => { location.hash = "#import"; };
$("#file-input").onchange = (e) => importFiles([...e.target.files]);

route();
