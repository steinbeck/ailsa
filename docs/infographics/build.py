"""Assemble the AILSA infographic deck (8x 16:9 slides) with inline structures."""
import json, math

with open("structures.json") as f:
    S = json.load(f)

# ---- CASE1-9 worked examples (ground truth from .planning/CASE-DATASET-IDENTITIES.md) ----
CASES = [
    ("CASE1", "P9 / S51",   "solved",   "Benzene ring emerged from constraints — 0 ring-BONDs; Rank 1, exact InChIKey"),
    ("CASE2", "P42 / S1328", "solved",  "Purine alkaloid; two C=O + three N-CH₃ pin the xanthine core"),
    ("CASE3", "pulegone set","solved",  "α,β-unsat. ketone; ¹³C rules out the formula-twin thujone"),
    ("CASE4", "P42 / S1312", "partial", "Correct azulene scaffold — exact substitution regiochemistry not yet reachable"),
    ("CASE5", "P42 / S1302", "solved",  "C₂-symmetric; single C=O rules out asymmetric indirubin"),
    ("CASE6", "citronellol set","solved","Acyclic monoterpenoid; olefinic pair + CH₂OH rule out menthol"),
    ("CASE7", "P124 / S1266","solved",  "Tetracyclic lupin alkaloid; independently re-validated on a clean host"),
    ("CASE8", "P42",         "solved",  "Allyl-phenol; terminal =CH₂ rules out isoeugenol"),
    ("CASE9", "P9 / S53 (D202)","solved","First-ever full solve (2026-06-11); benzoate ester, MAE 1.17"),
]

STATUS = {
    "solved":  ("Solved",  "ok"),
    "partial": ("Partial", "warn"),
    "open":    ("Open",    "off"),
}

def sub(formula):
    out = []
    for ch in formula:
        out.append(f"<sub>{ch}</sub>" if ch.isdigit() else ch)
    return "".join(out)

cards = []
for cid, nmrxiv, st, note in CASES:
    meta = S[cid]
    label, tone = STATUS[st]
    cards.append(f"""
      <figure class="mol">
        <div class="mol-art">{meta['svg']}</div>
        <figcaption>
          <div class="mol-head">
            <span class="mol-id">{cid}</span>
            <span class="pill pill-{tone}">{label}</span>
          </div>
          <h3 class="mol-name">{meta['name']}</h3>
          <div class="mol-meta">
            <span class="formula">{sub(meta['formula'])}</span>
            <span class="nmrxiv">nmrxiv {nmrxiv}</span>
          </div>
          <p class="mol-note">{note}</p>
        </figcaption>
      </figure>""")
STRUCTURE_CARDS = "\n".join(cards)

# ---- recurring 13C spectrum motif (hand-placed peaks; reversed ppm axis) ----
peaks = [(205,0.55),(160,0.7),(148,0.5),(143,0.85),(131,0.6),(124,0.45),
         (121,0.5),(114,0.65),(111,0.4),(61,0.9),(56,0.55),(40,0.75),
         (34,0.6),(29,0.8),(25,0.5),(22,1.0),(18,0.6),(14,0.7)]
def spectrum_svg(w=1000, h=90, stroke="var(--accent)"):
    x0, x1 = 8, w-8
    base = h-20
    def X(ppm): return x1 - (ppm/210.0)*(x1-x0)   # 210 ppm at left, 0 at right
    lines = [f'<line x1="{x0}" y1="{base}" x2="{x1}" y2="{base}" stroke="var(--rule)" stroke-width="1"/>']
    for ppm, inten in peaks:
        x = X(ppm); y = base-(inten*(base-8))
        lines.append(f'<line x1="{x:.1f}" y1="{base}" x2="{x:.1f}" y2="{y:.1f}" stroke="{stroke}" stroke-width="1.6"/>')
    for ppm in (200,150,100,50,0):
        x = X(ppm)
        lines.append(f'<line x1="{x:.1f}" y1="{base}" x2="{x:.1f}" y2="{base+4}" stroke="var(--rule)" stroke-width="1"/>')
        lines.append(f'<text x="{x:.1f}" y="{base+16}" class="ppm-tick">{ppm}</text>')
    return f'<svg viewBox="0 0 {w} {h}" class="spectrum" role="img" aria-label="Schematic ¹³C NMR spectrum">{"".join(lines)}</svg>'

SPECTRUM = spectrum_svg()

# ---- folder icons for the input-layout illustration (slide 3) ----
_folder = ('<svg viewBox="0 0 30 22" aria-hidden="true"><path class="fill" '
           'd="M3 5.5h7l2 2h13a1.5 1.5 0 0 1 1.5 1.5v9.5a1.5 1.5 0 0 1-1.5 1.5H3'
           'a1.5 1.5 0 0 1-1.5-1.5V7a1.5 1.5 0 0 1 1.5-1.5z"/></svg>')
FOLDERS = "\n          ".join(
    f'<div class="fold">{_folder}<span>{i}</span></div>' for i in range(1, 8))

HTML = f"""<title>AILSA — AI + LSD + Agents · CASE from NMR</title>
<style>
:root {{
  --bg:#f5f7f9; --bg2:#eaeef2; --ink:#141b24; --muted:#5a6b7a; --faint:#8496a4;
  --paper:#fbfbf8; --rule:#c7d2da; --line:#dbe3e9;
  --accent:#0f97a6; --accent2:#e0a24e; --ok:#2f9e63; --warn:#d68a2a; --off:#8a97a2;
  --card:#ffffff; --shadow:0 1px 2px rgba(20,30,45,.05),0 8px 24px rgba(20,30,45,.06);
  --serif:Georgia,'Iowan Old Style','Times New Roman',serif;
  --sans:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;
  --mono:ui-monospace,'SF Mono',Menlo,'Cascadia Code',monospace;
}}
@media (prefers-color-scheme:dark) {{
  :root {{
    --bg:#0e151d; --bg2:#131d27; --ink:#e8eef3; --muted:#9fb0bd; --faint:#6c7d8a;
    --paper:#f6f5f0; --rule:#31414e; --line:#243139;
    --accent:#2fc0d0; --accent2:#e9b366; --ok:#54c088; --warn:#e0a24e; --off:#6c7d8a;
    --card:#151f29; --shadow:0 1px 2px rgba(0,0,0,.3),0 10px 30px rgba(0,0,0,.35);
  }}
}}
:root[data-theme="light"] {{
  --bg:#f5f7f9; --bg2:#eaeef2; --ink:#141b24; --muted:#5a6b7a; --faint:#8496a4;
  --paper:#fbfbf8; --rule:#c7d2da; --line:#dbe3e9;
  --accent:#0f97a6; --accent2:#e0a24e; --ok:#2f9e63; --warn:#d68a2a; --off:#8a97a2;
  --card:#ffffff; --shadow:0 1px 2px rgba(20,30,45,.05),0 8px 24px rgba(20,30,45,.06);
}}
:root[data-theme="dark"] {{
  --bg:#0e151d; --bg2:#131d27; --ink:#e8eef3; --muted:#9fb0bd; --faint:#6c7d8a;
  --paper:#f6f5f0; --rule:#31414e; --line:#243139;
  --accent:#2fc0d0; --accent2:#e9b366; --ok:#54c088; --warn:#e0a24e; --off:#6c7d8a;
  --card:#151f29; --shadow:0 1px 2px rgba(0,0,0,.3),0 10px 30px rgba(0,0,0,.35);
}}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink); font-family:var(--sans);
  -webkit-font-smoothing:antialiased; line-height:1.5; }}
.deck {{ max-width:1180px; margin:0 auto; padding:40px 24px 72px; display:flex;
  flex-direction:column; gap:40px; }}
.slide {{ position:relative; aspect-ratio:16/9; background:var(--card); border:1px solid var(--line);
  border-radius:14px; box-shadow:var(--shadow); padding:clamp(24px,3.4vw,48px);
  display:flex; flex-direction:column; }}
.eyebrow {{ display:flex; align-items:center; gap:12px; font-family:var(--mono);
  font-size:12px; letter-spacing:.14em; text-transform:uppercase; color:var(--accent); }}
.eyebrow .n {{ color:var(--faint); }}
.eyebrow .bar {{ flex:0 0 26px; height:2px; background:var(--accent); border-radius:2px; }}
h1 {{ font-family:var(--serif); font-weight:700; letter-spacing:-.01em; line-height:1.04;
  text-wrap:balance; margin:0; }}
h2 {{ font-family:var(--serif); font-weight:700; letter-spacing:-.01em; line-height:1.06;
  text-wrap:balance; margin:0; font-size:clamp(26px,3.1vw,40px); }}
.lede {{ color:var(--muted); font-size:clamp(15px,1.5vw,19px); max-width:62ch; margin:0; }}
.foot {{ margin-top:auto; padding-top:16px; border-top:1px solid var(--line);
  display:flex; align-items:center; justify-content:space-between;
  font-family:var(--mono); font-size:11.5px; color:var(--faint); letter-spacing:.04em; }}
.foot .brand {{ color:var(--muted); }}
.foot .brand b {{ color:var(--accent); font-weight:600; }}
.spectrum {{ width:100%; height:auto; display:block; }}
.ppm-tick {{ font-family:var(--mono); font-size:9px; fill:var(--faint); text-anchor:middle; }}
.pill {{ font-family:var(--mono); font-size:10.5px; font-weight:600; letter-spacing:.04em;
  padding:2px 8px; border-radius:999px; border:1px solid; white-space:nowrap; }}
.pill-ok {{ color:var(--ok); border-color:color-mix(in srgb,var(--ok) 40%,transparent);
  background:color-mix(in srgb,var(--ok) 12%,transparent); }}
.pill-warn {{ color:var(--warn); border-color:color-mix(in srgb,var(--warn) 45%,transparent);
  background:color-mix(in srgb,var(--warn) 14%,transparent); }}
.pill-off {{ color:var(--off); border-color:color-mix(in srgb,var(--off) 40%,transparent); }}

/* ---- Slide 1: title ---- */
.s-title {{ justify-content:center; }}
.s-title h1 {{ font-size:clamp(38px,6vw,74px); }}
.s-title .kicker {{ font-family:var(--mono); font-size:13px; letter-spacing:.16em;
  text-transform:uppercase; color:var(--accent); margin-bottom:20px; }}
.s-title .expansion {{ font-family:var(--mono); font-size:14px; letter-spacing:.1em;
  color:var(--muted); margin:6px 0 0; }}
.s-title .lede {{ margin-top:20px; font-size:clamp(16px,1.7vw,21px); }}
.title-hero {{ margin:26px 0 8px; }}
.chips {{ display:flex; flex-wrap:wrap; gap:8px; margin-top:24px; }}
.chip {{ font-family:var(--mono); font-size:12px; color:var(--muted); border:1px solid var(--line);
  border-radius:999px; padding:5px 12px; background:var(--bg2); }}
.chip b {{ color:var(--ink); font-weight:600; }}

/* ---- generic content grid ---- */
.body {{ margin-top:22px; flex:1; min-height:0; }}
.two {{ display:grid; grid-template-columns:1fr 1fr; gap:22px; }}

/* ---- pipeline ---- */
.flow {{ display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-top:24px; }}
.step {{ background:var(--bg2); border:1px solid var(--line); border-radius:10px;
  padding:14px 14px 16px; position:relative; display:flex; flex-direction:column; gap:6px; }}
.step .sn {{ font-family:var(--mono); font-size:11px; color:var(--accent); letter-spacing:.08em; }}
.step h4 {{ margin:0; font-size:15px; font-family:var(--serif); font-weight:700; }}
.step p {{ margin:0; font-size:12.5px; color:var(--muted); line-height:1.4; }}
.step .tool {{ font-family:var(--mono); font-size:10.5px; color:var(--accent2); margin-top:2px; }}
.steps2 {{ display:grid; grid-template-columns:1fr 1fr; gap:9px; }}
.steps2 .step {{ padding:10px 12px 12px; gap:4px; }}

/* ---- input layout illustration (slide 3) ---- */
.inputbar {{ margin-top:16px; background:var(--bg2); border:1px solid var(--line);
  border-radius:10px; padding:12px 16px 13px; display:flex; flex-direction:column; gap:9px; }}
.input-label {{ font-family:var(--mono); font-size:11px; letter-spacing:.05em; color:var(--muted); }}
.input-label .tag {{ color:var(--accent); font-weight:600; }}
.input-row {{ display:flex; align-items:center; gap:14px; flex-wrap:wrap; }}
.folders {{ display:flex; gap:9px; align-items:flex-end; }}
.fold {{ display:flex; flex-direction:column; align-items:center; gap:3px; }}
.fold svg {{ width:30px; height:24px; display:block; }}
.fold .fill {{ fill:var(--accent); }}
.fold .tab {{ fill:color-mix(in srgb,var(--accent) 78%,#000 6%); }}
.fold span {{ font-family:var(--mono); font-size:10px; color:var(--muted); }}
.input-plus {{ font-family:var(--mono); font-size:15px; color:var(--faint); }}
.file {{ display:flex; align-items:center; gap:7px; background:var(--card); border:1px solid var(--line);
  border-radius:7px; padding:6px 11px 6px 8px; }}
.file svg {{ width:17px; height:21px; display:block; }}
.file .fbody {{ fill:var(--paper); stroke:var(--rule); stroke-width:1; }}
.file span {{ font-family:var(--mono); font-size:11.5px; color:var(--ink); }}
.input-note {{ font-family:var(--mono); font-size:10px; color:var(--faint); letter-spacing:.02em; }}
.input-note b {{ color:var(--muted); font-weight:600; }}

/* ---- agent team ---- */
.team {{ display:grid; grid-template-columns:1fr 1fr; gap:14px; margin-top:20px; }}
.orch {{ grid-column:1 / -1; background:linear-gradient(180deg,var(--bg2),transparent);
  border:1px solid var(--line); border-left:3px solid var(--accent); border-radius:10px; padding:14px 16px;
  display:flex; gap:16px; align-items:baseline; flex-wrap:wrap; }}
.agent {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:13px 15px;
  display:flex; flex-direction:column; gap:4px; }}
.agent .role {{ font-family:var(--mono); font-size:11px; color:var(--accent); letter-spacing:.05em; }}
.agent h4 {{ margin:0; font-size:15px; font-family:var(--serif); font-weight:700; }}
.agent p {{ margin:0; font-size:12.5px; color:var(--muted); line-height:1.42; }}
.agent-name {{ font-family:var(--mono); font-size:12px; color:var(--ink); font-weight:600; }}
.coord {{ margin-top:14px; font-size:12.5px; color:var(--muted); background:var(--bg2);
  border:1px solid var(--line); border-radius:8px; padding:10px 14px; }}
.coord b {{ color:var(--accent); }}
.channels {{ display:flex; flex-direction:column; gap:8px; margin-top:12px; }}
.channel-chip {{ font-size:12px; color:var(--muted); background:var(--card);
  border:1px solid var(--line); border-left:3px solid var(--accent2); border-radius:8px;
  padding:9px 13px; line-height:1.4; }}
.channel-chip b {{ color:var(--ink); font-family:var(--mono); font-weight:600; font-size:11.5px; }}

/* ---- test set grid ---- */
.grid9 {{ display:grid; grid-template-columns:repeat(3,1fr); gap:14px; margin-top:20px; flex:1; }}
.mol {{ margin:0; display:grid; grid-template-columns:96px 1fr; gap:12px; align-items:center;
  background:var(--card); border:1px solid var(--line); border-radius:10px; padding:10px 12px; }}
.mol-art {{ background:var(--paper); border:1px solid var(--line); border-radius:8px; padding:2px;
  aspect-ratio:1/.78; display:flex; align-items:center; justify-content:center; }}
.mol-art svg {{ width:100%; height:100%; }}
.mol-head {{ display:flex; align-items:center; gap:8px; }}
.mol-id {{ font-family:var(--mono); font-size:11px; font-weight:700; color:var(--accent);
  letter-spacing:.04em; }}
.mol-name {{ margin:2px 0 3px; font-family:var(--serif); font-size:14.5px; font-weight:700;
  line-height:1.12; }}
.mol-meta {{ display:flex; gap:10px; flex-wrap:wrap; font-family:var(--mono); font-size:10.5px; }}
.formula {{ color:var(--ink); font-weight:600; }}
.formula sub {{ font-size:.72em; }}
.nmrxiv {{ color:var(--faint); }}
.mol-note {{ margin:5px 0 0; font-size:10.8px; color:var(--muted); line-height:1.34; }}

/* ---- numbers ---- */
.stats {{ display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin-top:22px; }}
.stat {{ background:var(--bg2); border:1px solid var(--line); border-radius:10px; padding:16px 16px 14px;
  display:flex; flex-direction:column; gap:3px; }}
.stat .v {{ font-family:var(--serif); font-size:clamp(26px,3.4vw,38px); font-weight:700; line-height:1;
  color:var(--ink); font-variant-numeric:tabular-nums; letter-spacing:-.02em; }}
.stat .v span {{ font-size:.5em; color:var(--accent); }}
.stat .k {{ font-size:12px; color:var(--muted); }}
.stat .s {{ font-family:var(--mono); font-size:10px; color:var(--faint); letter-spacing:.03em; }}
.credits {{ margin-top:20px; display:grid; grid-template-columns:1fr 1fr; gap:16px; font-size:12.5px;
  color:var(--muted); }}
.credits h4 {{ margin:0 0 4px; font-family:var(--mono); font-size:11px; letter-spacing:.08em;
  text-transform:uppercase; color:var(--accent); }}
.credits b {{ color:var(--ink); }}

/* ---- benchmark slide ---- */
.config-note {{ font-size:12.5px; color:var(--muted); margin:8px 0 0; max-width:74ch; }}
.bench-stats {{ display:grid; grid-template-columns:1fr 1fr; gap:12px; }}
.sizes {{ display:flex; flex-direction:column; gap:0; font-family:var(--mono); font-size:11px;
  color:var(--muted); background:var(--bg2); border:1px solid var(--line); border-radius:8px; }}
.sizes .row {{ display:flex; justify-content:space-between; gap:10px; padding:6px 12px;
  border-bottom:1px solid var(--line); }}
.sizes .row:last-child {{ border-bottom:none; }}
.sizes .row.warn {{ color:var(--warn); font-weight:600; }}
.pairline {{ font-size:12px; color:var(--muted); margin:2px 0 0; }}

/* ---- combination "formula" (slide 1) ---- */
.stack {{ display:flex; align-items:stretch; gap:12px; margin-top:24px; flex-wrap:wrap; }}
.block {{ flex:1 1 0; min-width:180px; background:var(--bg2); border:1px solid var(--line);
  border-radius:10px; padding:12px 15px; display:flex; flex-direction:column; gap:3px; }}
.block .bk {{ font-family:var(--serif); font-size:16px; font-weight:700; color:var(--ink); }}
.block .bd {{ font-size:12px; color:var(--muted); line-height:1.35; }}
.block.cc {{ border-color:color-mix(in srgb,var(--accent) 45%,transparent);
  background:color-mix(in srgb,var(--accent) 9%,transparent); }}
.block.cc .bd b {{ color:var(--accent); }}
.op {{ align-self:center; font-family:var(--serif); font-size:22px; color:var(--accent); font-weight:700; }}
.stack-eq {{ margin:13px 0 0; font-family:var(--mono); font-size:12.5px; color:var(--muted);
  letter-spacing:.02em; }}
.stack-eq b {{ color:var(--accent); font-weight:600; }}

/* ---- repo line (slide 1) ---- */
.repo {{ margin-top:22px; display:inline-flex; align-items:center; gap:9px;
  font-family:var(--mono); font-size:13.5px; color:var(--muted); }}
.repo svg {{ width:18px; height:18px; fill:var(--accent); flex:0 0 auto; }}
.repo b {{ color:var(--ink); font-weight:600; }}

/* ---- nmrXiv slide ---- */
.nx {{ display:grid; grid-template-columns:1.05fr 1fr; gap:26px; margin-top:20px; flex:1; min-height:0; }}
.nx-col {{ display:flex; flex-direction:column; gap:14px; }}
.cmd {{ font-family:var(--mono); font-size:12.5px; background:#0d1622; color:#dfe8ee;
  border:1px solid #223244; border-radius:9px; padding:13px 15px; line-height:1.7; }}
.cmd .p {{ color:#2fc0d0; }}
.cmd .c {{ color:#e9b366; }}
.cmd .a {{ color:#7f93a3; }}
.hier {{ display:flex; align-items:center; gap:8px; font-family:var(--mono); font-size:12px;
  color:var(--muted); flex-wrap:wrap; }}
.hier .node {{ background:var(--bg2); border:1px solid var(--line); border-radius:6px;
  padding:4px 10px; }}
.hier .node b {{ color:var(--accent); }}
.hier .arr {{ color:var(--faint); }}
.nx-head {{ font-family:var(--mono); font-size:11px; letter-spacing:.08em; text-transform:uppercase;
  color:var(--accent); margin-bottom:2px; }}
.srclist {{ display:flex; flex-direction:column; gap:0; }}
.src {{ display:grid; grid-template-columns:52px 1fr; gap:12px; align-items:baseline;
  padding:11px 0; border-bottom:1px solid var(--line); }}
.src:last-child {{ border-bottom:none; }}
.src .pid {{ font-family:var(--mono); font-size:12.5px; font-weight:700; color:var(--accent); }}
.src .st {{ font-family:var(--serif); font-size:14.5px; font-weight:700; line-height:1.15; }}
.src .sd {{ font-size:12px; color:var(--muted); margin-top:1px; }}
.nx-why {{ font-size:12.5px; color:var(--muted); background:var(--bg2); border:1px solid var(--line);
  border-radius:8px; padding:10px 14px; }}
.nx-why b {{ color:var(--accent); }}

@media (max-width:720px) {{
  .slide {{ aspect-ratio:auto; }}
  .flow,.stats {{ grid-template-columns:1fr 1fr; }}
  .grid9,.team,.two,.credits,.bench-stats,.steps2 {{ grid-template-columns:1fr; }}
  .mol {{ grid-template-columns:80px 1fr; }}
}}
@page {{ size:1280px 720px; margin:0; }}
@media print {{
  :root {{ color-scheme:light;
    --bg:#f5f7f9; --bg2:#eaeef2; --ink:#141b24; --muted:#5a6b7a; --faint:#8496a4;
    --paper:#fbfbf8; --rule:#c7d2da; --line:#dbe3e9;
    --accent:#0f97a6; --accent2:#e0a24e; --ok:#2f9e63; --warn:#d68a2a; --off:#8a97a2;
    --card:#ffffff; --shadow:none; }}
  body {{ background:#fff; }}
  .deck {{ max-width:none; gap:0; padding:0; }}
  .slide {{ width:1280px; height:720px; aspect-ratio:auto; padding:54px 66px;
    break-after:page; break-inside:avoid; box-shadow:none; border:none; border-radius:0; }}
  .slide:last-child {{ break-after:auto; }}
}}
</style>

<div class="deck">

  <!-- ============ SLIDE 1 · TITLE ============ -->
  <section class="slide s-title">
    <div class="kicker">Computer-Assisted Structure Elucidation · from NMR</div>
    <h1>AILSA</h1>
    <p class="expansion">AI + LSD + Agents</p>
    <p class="lede">An AI agent that aims to autonomously determine the structure of an unknown
      organic compound from its NMR spectra — reasoning about the data, building solver
      constraints, and ranking candidate structures without human intervention.</p>
    <div class="title-hero">{spectrum_svg(1000,86)}</div>
    <div class="stack">
      <div class="block"><span class="bk">Domain skill-set</span>
        <span class="bd">extensive NMR / CASE expertise &amp; workflow strategy — the intelligence layer</span></div>
      <span class="op">+</span>
      <div class="block"><span class="bk">Thin tools</span>
        <span class="bd">nmrglue · LSD · RDKit CLI wrappers for data &amp; solvers</span></div>
      <span class="op">+</span>
      <div class="block cc"><span class="bk">Agent team</span>
        <span class="bd"><b>Claude Code's agent-team feature</b> — specialists that coordinate with each other</span></div>
    </div>
    <p class="stack-eq">= one autonomous CASE system, orchestrated entirely inside <b>Claude Code</b>.</p>
    <div class="repo">
      <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82a7.6 7.6 0 0 1 2-.27c.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8z"/></svg>
      <span><b>github.com/steinbeck/ailsa</b></span>
    </div>
    <div class="foot">
      <span class="brand"><b>AILSA</b> · natural-products CASE</span>
      <span>01 / 08</span>
    </div>
  </section>

  <!-- ============ SLIDE 2 · WHAT & WHY ============ -->
  <section class="slide">
    <div class="eyebrow"><span class="bar"></span><span>The idea</span><span class="n">Why an agent</span></div>
    <div class="body two">
      <div style="display:flex;flex-direction:column;gap:16px;">
        <h2>Spectra in, structure out — reasoned, not guessed</h2>
        <p class="lede">A chemist elucidating a natural product juggles ¹H, ¹³C, HSQC, HMBC
          and COSY, forms hypotheses, and rejects the ones the data contradicts. AILSA
          puts that reasoning loop under an AI agent.</p>
        <p class="lede">The Python tools stay deliberately thin — wrappers around
          <b>nmrglue</b>, <b>LSD</b> and <b>RDKit</b>. Domain expertise and strategy live in
          the agent skill, not in hard-coded heuristics.</p>
      </div>
      <div style="display:flex;flex-direction:column;gap:12px;">
        <div class="step"><div class="sn">The hard part</div><h4>Under-determined by design</h4>
          <p>NMR gives connectivity fragments, not a structure. Many candidates fit the same
            data — the agent must generate, rank, and rule out.</p></div>
        <div class="step"><div class="sn">The guardrail</div><h4>A team, not a lone agent</h4>
          <p>A multi-agent architecture prevents unproductive loops and the "clean-but-wrong"
            answer: low error, plausible, yet the wrong isomer.</p></div>
        <div class="step"><div class="sn">The solver</div><h4>Emergent, not forced</h4>
          <p>Rings and skeletons arise from MULT + HMBC + COSY constraints — not from a
            hand-placed answer. Verified: a benzene ring emerged with zero ring bonds asserted.</p></div>
      </div>
    </div>
    <div class="foot"><span class="brand"><b>AILSA</b> · the idea</span><span>02 / 08</span></div>
  </section>

  <!-- ============ SLIDE 3 · PIPELINE ============ -->
  <section class="slide">
    <div class="eyebrow"><span class="bar"></span><span>The pipeline</span><span class="n">Bruker data → answer</span></div>
    <h2>From raw Bruker spectra to a ranked structure</h2>
    <div class="flow">
      <div class="step"><div class="sn">01 · READ</div><h4>NMR data</h4>
        <p>1D ¹H / ¹³C and 2D HSQC · HMBC · COSY read straight from Bruker files.</p>
        <div class="tool">nmrglue</div></div>
      <div class="step"><div class="sn">02 · PICK</div><h4>Peak picking</h4>
        <p>Raw picking with SNR floors so weak quaternary carbons survive; the chemist agent applies DEPT/HMBC guidance.</p>
        <div class="tool">ailsa pick</div></div>
      <div class="step"><div class="sn">03 · DETECT</div><h4>Statistical detection</h4>
        <p>Hybridisation, forbidden/mandatory neighbours & hetero-hetero bonds from 7.9M HOSE stats.</p>
        <div class="tool">ailsa detect</div></div>
      <div class="step"><div class="sn">04 · BUILD</div><h4>Constraints + fragments</h4>
        <p>MULT / HSQC / HMBC / BOND plus DEFF fragment goodlists, written into the LSD file by the LSD-engineer agent.</p>
        <div class="tool">lsd-engineer agent</div></div>
      <div class="step"><div class="sn">05 · SOLVE</div><h4>LSD structure generator</h4>
        <p>Nuzillard's deterministic solver enumerates every structure consistent with the constraints.</p>
        <div class="tool">LSD (Reims)</div></div>
      <div class="step"><div class="sn">06 · RANK</div><h4>¹³C prediction</h4>
        <p>HOSE-code shift prediction scores candidates; match-count first, MAE second — no hallucinated fits.</p>
        <div class="tool">ailsa lsd rank</div></div>
      <div class="step"><div class="sn">07 · CHECK</div><h4>Identity gate</h4>
        <p>Derive identity from the SMILES via <b>ailsa identify</b> — never a recalled name; RDKit-verified.</p>
        <div class="tool">ailsa identify</div></div>
      <div class="step" style="background:transparent;border-style:dashed;">
        <div class="sn">DEREPLICATE</div><h4>Known compound?</h4>
        <p>Optional formula-indexed lookup against 928K compounds runs as a separate path — never inside CASE.</p>
        <div class="tool">ailsa dereplicate</div></div>
    </div>
    <div class="inputbar">
      <div class="input-label"><span class="tag">Input</span> — one data directory per unknown compound</div>
      <div class="input-row">
        <div class="folders">
          {FOLDERS}
        </div>
        <span class="input-plus">+</span>
        <div class="file">
          <svg viewBox="0 0 22 26" aria-hidden="true"><path class="fbody" d="M4 1.5h9.5L18 6v18a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V3.5a2 2 0 0 1 2-2z"/><path d="M13 1.5V6h4.5" fill="none" stroke="var(--rule)" stroke-width="1"/></svg>
          <span>molecular-formula.txt</span>
        </div>
      </div>
      <div class="input-note">Numbered <b>Bruker experiment folders</b> (¹H · ¹³C · HSQC · HMBC · COSY) &nbsp;·&nbsp; plus the known molecular formula</div>
    </div>
    <div class="foot"><span class="brand"><b>AILSA</b> · pipeline</span><span>03 / 08</span></div>
  </section>

  <!-- ============ SLIDE 4 · AGENT TEAM ============ -->
  <section class="slide">
    <div class="eyebrow"><span class="bar"></span><span>The agent team</span><span class="n">Roles &amp; guardrails</span></div>
    <h2>Four specialists, one coordinator</h2>
    <div class="team">
      <div class="orch">
        <span class="agent-name">case.md · coordinator</span>
        <span style="font-size:12.5px;color:var(--muted);">Starts the team, writes the single source-of-truth
          <b style="color:var(--accent)">CASE-PROGRESS.md</b>, detects unproductive loops, and intervenes with
          targeted advisories. Escalates to <b style="color:var(--accent)">ailsa-diagnostic</b> for deep LSD failure analysis.</span>
      </div>
      <div class="agent"><div class="role">spectra</div><span class="agent-name">ailsa-nmr-chemist</span>
        <p>Peak picking, statistical detection, spectral-quality assessment, and the chemistry-first
          evidence hierarchy — NMR always overrides statistics.</p></div>
      <div class="agent"><div class="role">solver</div><span class="agent-name">ailsa-lsd-engineer</span>
        <p>Builds LSD constraint files, iterates HMBC incrementally, owns the constraint inventory
          (read previous, never reconstruct), runs the solver.</p></div>
      <div class="agent"><div class="role">ranking</div><span class="agent-name">ailsa-solution-analyst</span>
        <p>Ranks solutions by ¹³C prediction, judges chemical plausibility, scores confidence,
          and writes the final result with a tentative identity.</p></div>
      <div class="agent"><div class="role">quality gate</div><span class="agent-name">ailsa-devils-advocate</span>
        <p>Validates every LSD file before it runs, checks constraint persistence across iterations,
          and enforces the G-IDENT / G-MULT gates against wrong-but-clean answers.</p></div>
    </div>
    <div class="channels">
      <div class="channel-chip"><b>ailsa-lsd-engineer &#8644; ailsa-devils-advocate</b> &middot; direct review loop — every LSD file is reviewed before the solver runs</div>
      <div class="channel-chip"><b>ailsa-lsd-engineer &#8594; ailsa-nmr-chemist</b> &middot; requests — ask the NMR chemist for more correlations or detection results</div>
    </div>
    <div class="coord"><b>Push-never-pull coordination.</b> The coordinator sends each specialist a <span style="font-family:var(--mono)">[BEGIN]</span> after creating its task; agents never poll. From there the specialists that coordinate with each other work through the direct review loop and ask the NMR chemist when they need more data; the coordinator stays the <b>sole writer</b> of the progress log.</div>
    <div class="foot"><span class="brand"><b>AILSA</b> · agent team</span><span>04 / 08</span></div>
  </section>

  <!-- ============ SLIDE 5 · NMRXIV DATA SOURCE ============ -->
  <section class="slide">
    <div class="eyebrow"><span class="bar"></span><span>Data source</span><span class="n">nmrxiv.org</span></div>
    <h2>Open, FAIR spectra — fetched by DOI</h2>
    <p class="lede" style="margin-top:12px;">nmrXiv is an open, community repository for raw and
      processed NMR data. Every dataset used here — the worked examples and all 256 benchmark
      datasets — is public, citable, and pulled straight from it — no proprietary files, no
      vendor lock-in.</p>
    <div class="nx">
      <div class="nx-col">
        <div>
          <div class="nx-head">Fetch a dataset</div>
          <div class="cmd"><span class="p">$</span> ailsa fetch nmrxiv <span class="c">10.57992/NMRXIV.P9.S51</span><br>
            <span class="a">&#8594; downloads the Bruker experiment folders into ./</span></div>
        </div>
        <div>
          <div class="nx-head">How it is organised</div>
          <div class="hier">
            <span class="node"><b>Project</b> P<i>n</i></span><span class="arr">&#8594;</span>
            <span class="node"><b>Study</b> S<i>n</i></span><span class="arr">&#8594;</span>
            <span class="node"><b>Dataset</b> · Bruker</span>
          </div>
        </div>
        <div class="nx-why"><b>Why it matters —</b> openly citable benchmarks let anyone re-run a
          CASE evaluation on the exact same experimental data.</div>
      </div>
      <div class="nx-col">
        <div class="nx-head">Where the CASE examples come from</div>
        <div class="srclist">
          <div class="src"><span class="pid">P9</span>
            <div><div class="st">Teaching Datasets 1</div><div class="sd">Duisburg-Essen &middot; CASE1, CASE9</div></div></div>
          <div class="src"><span class="pid">P42</span>
            <div><div class="st">Classics in Spectroscopy</div><div class="sd">CASE2, CASE4, CASE5, CASE8</div></div></div>
          <div class="src"><span class="pid">P124</span>
            <div><div class="st">Alkaloids of Virgilia Oroboides</div><div class="sd">Krytovych / Breuning &middot; CASE7</div></div></div>
        </div>
        <div class="input-note" style="margin-top:4px;">CASE3 &amp; CASE6 come from further public
          nmrXiv datasets (pulegone, citronellol).</div>
      </div>
    </div>
    <div class="foot"><span class="brand"><b>AILSA</b> · data source</span><span>05 / 08</span></div>
  </section>

  <!-- ============ SLIDE 6 · BENCHMARK ============ -->
  <section class="slide">
    <div class="eyebrow"><span class="bar"></span><span>Blind benchmark</span><span class="n">256 public datasets</span><span class="n">nmrXiv</span></div>
    <h2>Blind on 256 public datasets: 69.1 % solved at rank 1</h2>
    <p class="config-note">Measured in a restricted configuration: without the agent team (unattended runs form none, so the specialists ran one at a time under the coordinator) and without statistical detection (outdated reference database on the compute host).</p>
    <div class="two" style="margin-top:14px;flex:1;min-height:0;">
      <div style="display:flex;flex-direction:column;gap:9px;">
        <div class="nx-head">How it is measured</div>
        <div class="steps2">
        <div class="step"><div class="sn">01</div><h4>Spectra in, nothing else</h4>
          <p>The coordinator gets a sanitised directory of Bruker spectra and the molecular formula,
            never a name or structure; dereplication is forbidden.</p></div>
        <div class="step"><div class="sn">02</div><h4>Answers locked away</h4>
          <p>Every file mapping a dataset to its answer is moved out of reach for the duration of
            each batch; a system-prompt fence forbids looking for it.</p></div>
        <div class="step"><div class="sn">03</div><h4>Graded from outside</h4>
          <p>An independent grader re-derives every candidate's InChIKey with RDKit; the run's own
            claim is never used.</p></div>
        <div class="step"><div class="sn">04</div><h4>Constitution only</h4>
          <p>Stereochemistry is not tested.</p></div>
        </div>
      </div>
      <div style="display:flex;flex-direction:column;gap:12px;">
        <div class="bench-stats">
          <div class="stat"><div class="v">177 / 256</div><div class="k">correct structure at rank 1</div><div class="s">69.1 %</div></div>
          <div class="stat"><div class="v">189 / 256</div><div class="k">within the top 10</div><div class="s">73.8 %</div></div>
        </div>
        <div class="sizes">
          <div class="row"><span>&le; 15 heavy atoms</span><span>40 / 40</span><span>100 %</span></div>
          <div class="row"><span>16&ndash;20</span><span>28 / 32</span><span>88 %</span></div>
          <div class="row"><span>21&ndash;25</span><span>49 / 70</span><span>70 %</span></div>
          <div class="row warn"><span>&ge; 26</span><span>60 / 114</span><span>53 %</span></div>
        </div>
        <p class="pairline">Same 102 datasets, two model generations: Opus 5 67 / 102 vs Opus 4.8 40 / 102 at rank 1 — won 30, lost 3, exact McNemar p = 1.4 · 10⁻⁶</p>
      </div>
    </div>
    <div class="coord"><b>The limit is size.</b> Up to 15 heavy atoms every molecule was solved; from 26 upward about half. When a run fails, the right structure is almost never further down its list — generation, not ranking, is what limits it. 25 runs hit the three-hour limit and count as failures.</div>
    <div class="foot"><span class="brand"><b>AILSA</b> · benchmark</span><span>06 / 08</span></div>
  </section>

  <!-- ============ SLIDE 7 · EXAMPLES ============ -->
  <section class="slide">
    <div class="eyebrow"><span class="bar"></span><span>Worked examples</span><span class="n">CASE1–9</span><span class="n">8 solved · 1 partial</span></div>
    <div style="display:flex;align-items:baseline;justify-content:space-between;gap:16px;flex-wrap:wrap;">
      <h2>Nine worked examples</h2>
      <p style="margin:0;font-size:13px;color:var(--muted);max-width:44ch;">Illustrative public datasets, separate
        from the benchmark. Ground truth derived independently (nmrXiv + ¹³C verification); each run graded by a
        fresh blind instance, RDKit-verified.</p>
    </div>
    <div class="grid9">
      {STRUCTURE_CARDS}
    </div>
    <div class="foot"><span class="brand"><b>AILSA</b> · examples</span><span>07 / 08</span></div>
  </section>

  <!-- ============ SLIDE 8 · NUMBERS ============ -->
  <section class="slide">
    <div class="eyebrow"><span class="bar"></span><span>By the numbers</span><span class="n">Scale &amp; provenance</span></div>
    <h2>What the agent stands on</h2>
    <div class="stats">
      <div class="stat"><div class="v">928<span>K</span></div><div class="k">reference compounds</div><div class="s">COCONUT (predicted) + NMRShiftDB (experimental)</div></div>
      <div class="stat"><div class="v">7.9<span>M</span></div><div class="k">HOSE statistics</div><div class="s">¹³C shift prediction</div></div>
      <div class="stat"><div class="v">2.4<span>M</span></div><div class="k">fragment SSCs</div><div class="s">DEFF goodlist search</div></div>
      <div class="stat"><div class="v">111<span>K</span></div><div class="k">unique formulas</div><div class="s">formula-indexed lookup</div></div>
      <div class="stat"><div class="v">1372</div><div class="k">passing tests</div><div class="s">pytest · mypy-strict · ruff</div></div>
      <div class="stat"><div class="v">69.1<span>%</span></div><div class="k">rank 1 in the blind benchmark</div><div class="s">177 / 256 · restricted configuration, see slide 6</div></div>
      <div class="stat"><div class="v">16</div><div class="k">CLI command groups</div><div class="s">--format json on all analysis commands</div></div>
      <div class="stat"><div class="v">5</div><div class="k">agents in the team</div><div class="s">coordinator + 4 specialists</div></div>
    </div>
    <div class="credits">
      <div><h4>Built on</h4><p><b>LSD</b> — the deterministic structure generator by
        Jean-Marc Nuzillard (Université de Reims). <b>HOSE codes</b> — Bremser, 1978.
        Parsing via <b>nmrglue</b>; cheminformatics via <b>RDKit</b>.
        <b>Reference data</b> — COCONUT and NMRShiftDB; COCONUT 13C shifts: from J.-M. Nuzillard, Zenodo, doi:10.5281/zenodo.6561449, CC BY 4.0.</p></div>
      <div><h4>Get it</h4><p><b>github.com/steinbeck/ailsa</b> &middot; <b>pip install ailsa</b> &middot; reference
        database DOI <b>10.6084/m9.figshare.31073554</b></p></div>
    </div>
    <div class="foot"><span class="brand"><b>AILSA</b> · by the numbers</span><span>08 / 08</span></div>
  </section>

</div>
"""

with open("deck.html", "w") as f:
    f.write(HTML)
print("wrote deck.html", len(HTML), "bytes")
