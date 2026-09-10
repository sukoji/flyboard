"""Build the FLYBOARD chart pages (docs/) and render README images (assets/) with headless Chrome.

  docs/index.html          interactive site (tabs, all charts) for GitHub Pages
  docs/_render/*.html      fixed-width pages, screenshotted into assets/*.png
"""
import html
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
ASSETS = ROOT / "assets"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
REPO = "github.com/sukoji/flyboard"
CHARTS = {
    "global": dict(name="HOT 30", label="Songs of the Century", color="#f5c542", flag=""),
    "japan": dict(name="JAPAN", label="J-POP", color="#ff4d6d", flag=""),
    "korea": dict(name="KOREA", label="K-POP", color="#4dabff", flag=""),
    "all": dict(name="ALL-TIME", label="Every chart combined", color="#c77dff", flag=""),
}

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Anton&family=Inter:wght@400;600;800&family=Noto+Sans+JP:wght@400;700;900&family=Noto+Sans+KR:wght@400;700;900&display=block');
:root { --bg:#07080d; --panel:#10131c; --line:#1d2230; --ink:#f4f5f8; --muted:#8b91a4; --acc:#f5c542; }
* { box-sizing:border-box; margin:0; padding:0; }
body { background:var(--bg); color:var(--ink); font-family:Inter,'Noto Sans JP','Noto Sans KR',sans-serif; }
.page { width:1200px; padding:48px 56px 40px; position:relative; overflow:hidden;
  background: radial-gradient(900px 500px at 85% -5%, color-mix(in srgb, var(--acc) 22%, transparent), transparent 70%),
              radial-gradient(700px 500px at -10% 30%, rgba(80,110,255,.10), transparent 70%), var(--bg); }
.mast { display:flex; align-items:flex-end; gap:22px; }
.logo { font-family:Anton,Impact,sans-serif; font-size:92px; line-height:.85; letter-spacing:1px; }
.logo .fly { font-size:70px; margin-right:6px; }
.chartname { font-family:Anton,Impact,sans-serif; font-size:92px; line-height:.85; color:var(--acc); }
.sub { margin-top:14px; font-size:17px; color:var(--ink); font-weight:600; }
.sub2 { margin-top:6px; font-size:13px; color:var(--muted); }
.ref { margin-top:26px; display:flex; align-items:center; gap:16px; padding:14px 18px; border:1px solid color-mix(in srgb, var(--acc) 55%, transparent);
  border-radius:14px; background:linear-gradient(90deg, color-mix(in srgb, var(--acc) 12%, transparent), transparent); }
.ref .e { font-size:30px; } .ref .t { font-weight:800; font-size:17px; } .ref .a { color:var(--muted); font-size:12.5px; margin-top:2px; }
.ref .s { margin-left:auto; font-family:Anton,Impact,sans-serif; font-size:34px; color:var(--acc); }
.podium { display:grid; grid-template-columns:1.25fr 1fr 1fr; gap:18px; margin-top:26px; }
.card { background:var(--panel); border:1px solid var(--line); border-radius:18px; overflow:hidden; position:relative; }
.card img { width:100%; aspect-ratio:1; display:block; object-fit:cover; }
.card .rk { position:absolute; top:12px; left:16px; font-family:Anton,Impact,sans-serif; font-size:64px; line-height:1;
  color:#fff; text-shadow:0 4px 24px rgba(0,0,0,.6); }
.card.first .rk { font-size:88px; color:var(--acc); }
.card .body { padding:14px 16px 16px; }
.card .t { font-weight:900; font-size:21px; line-height:1.2; }
.card.first .t { font-size:25px; }
.card .a { color:var(--muted); font-size:13.5px; margin-top:4px; }
.card .row { display:flex; align-items:baseline; justify-content:space-between; margin-top:12px; }
.card .sc { font-family:Anton,Impact,sans-serif; font-size:40px; color:var(--acc); }
.card .ci { color:var(--muted); font-size:12px; }
.tags { display:flex; gap:6px; flex-wrap:wrap; margin-top:10px; }
.tag { font-size:11px; padding:3px 8px; border-radius:99px; background:#1b2030; color:#c9cde0; white-space:nowrap; }
.tag.hot { background:color-mix(in srgb, var(--acc) 25%, #1b2030); color:#fff; }
.tag.jump { background:#3a2a07; color:#ffcf5a; }
.list { margin-top:22px; border-top:1px solid var(--line); }
.item { display:grid; grid-template-columns:54px 58px 1fr 300px 76px; align-items:center; gap:16px; padding:9px 6px; border-bottom:1px solid var(--line); }
.item .rk { font-family:Anton,Impact,sans-serif; font-size:28px; text-align:center; color:#dfe2ea; }
.item img { width:58px; height:58px; border-radius:10px; display:block; }
.item .t { font-weight:800; font-size:16px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.item .a { color:var(--muted); font-size:12.5px; margin-top:2px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.bar { position:relative; height:10px; background:#1a1f2d; border-radius:99px; }
.bar i { position:absolute; left:0; top:0; bottom:0; border-radius:99px; background:linear-gradient(90deg, color-mix(in srgb, var(--acc) 45%, #334), var(--acc)); }
.bar b { position:absolute; top:-4px; bottom:-4px; border-left:1px solid #fff8; border-right:1px solid #fff8; }
.item .sc { font-family:Anton,Impact,sans-serif; font-size:26px; text-align:right; }
.item .sc small { display:block; font-family:Inter,sans-serif; font-size:10.5px; color:var(--muted); font-weight:400; }
.chip { font-size:10.5px; color:var(--muted); margin-top:4px; }
.foot { margin-top:26px; color:var(--muted); font-size:12px; line-height:1.6; }
.foot b { color:var(--ink); }
.hero .trio { display:grid; grid-template-columns:repeat(3,1fr); gap:20px; margin-top:28px; }
.hero .card .chart { position:absolute; top:14px; right:14px; font-size:12px; font-weight:800; padding:5px 10px; border-radius:99px;
  background:rgba(0,0,0,.55); backdrop-filter:blur(6px); }
.hero .card .rk { font-size:54px; }
.kpis { display:flex; gap:28px; margin-top:22px; }
.kpi { font-size:13px; color:var(--muted); } .kpi b { display:block; font-family:Anton,Impact,sans-serif; font-size:34px; color:var(--ink); font-weight:400; }
"""


def esc(s):
    return html.escape(str(s))


def tags(r, hot_cut, jump_cut):
    t = [f'<span class="tag">🧠 {int(r.neurons_lit):,} neurons lit</span>']
    if r.jo_B_hz / (r.jo_A_hz + r.jo_B_hz) >= hot_cut:
        t.append('<span class="tag hot">🔊 bass the fly loves</span>')
    if r.panic_GF_hz >= jump_cut:
        t.append('<span class="tag jump">⚡ jump scare</span>')
    return "".join(t)


def chart_page(key, rows, ref, stats, cover_rel, chart_tag=False):
    c = CHARTS[key]
    lo = min(0.0, rows.fly_score.min() - 5)
    width = lambda s: float(np.clip(100 * (s - lo) / (100 - lo), 1.5, 100))
    podium = []
    for i, r in enumerate(rows.head(3).itertuples()):
        podium.append(f"""
      <div class="card {'first' if i == 0 else ''}"><img src="{cover_rel}/{r.Index}.png"><div class="rk">{r.rank}</div>
        <div class="body"><div class="t">{esc(r.title)}</div><div class="a">{esc(r.artist)}{' · ' + CHARTS[r.chart]['name'] if chart_tag else ''}</div>
        <div class="row"><div class="sc">{r.fly_score:.1f}</div><div class="ci">± {r.ci95:.1f} (95% CI)</div></div>
        <div class="tags">{tags(r, stats['hot_cut'], stats['jump_cut'])}</div></div></div>""")
    items = []
    for r in rows.iloc[3:].itertuples():
        items.append(f"""
      <div class="item"><div class="rk">{r.rank}</div><img src="{cover_rel}/{r.Index}.png">
        <div><div class="t">{esc(r.title)}</div><div class="a">{esc(r.artist)}{' · ' + CHARTS[r.chart]['name'] if chart_tag else ''}</div></div>
        <div><div class="bar"><i style="width:{width(r.fly_score):.1f}%"></i><b style="left:{width(r.fly_score - r.ci95):.1f}%;width:{width(r.fly_score + r.ci95) - width(r.fly_score - r.ci95):.1f}%"></b></div>
          <div class="chip">🧠 {int(r.neurons_lit):,} neurons lit{' · ⚡ jump scare' if r.panic_GF_hz >= stats['jump_cut'] else ''}</div></div>
        <div class="sc">{r.fly_score:.1f}<small>± {r.ci95:.1f}</small></div></div>""")
    return f"""
  <section class="page" style="--acc:{c['color']}">
    <div class="mast"><div class="logo"><span class="fly">🪰</span>FLYBOARD</div><div class="chartname">{c['name']}</div></div>
    <div class="sub">{c['label']} — ranked by a fruit fly brain</div>
    <div class="sub2">{stats['n_neurons']:,} simulated neurons of a real male fly (MaleCNS v1.0 connectome) listened to every song {stats['sessions']}×.
      FLY SCORE: 0 = white noise, 100 = the brain's exact response to fly love song.</div>
    <div class="ref"><div class="e">🪰</div><div><div class="t">Courtship Song</div><div class="a">another fruit fly · control, not ranked · what a real hit sounds like to this brain</div></div><div class="s">{stats['fly_ref']:.1f}</div></div>
    <div class="podium">{''.join(podium)}</div>
    <div class="list">{''.join(items)}</div>
    <div class="foot"><b>How it's scored:</b> the song is turned into input to the fly's ear (Johnston's organ), a spiking model of the
      whole CNS listens, and we measure how similar the brain-wide response is to its response to real fly love song.
      Parody chart, not affiliated with Billboard. Connectome © Janelia/Google (CC-BY 4.0). {REPO}</div>
  </section>"""


def hero_page(top1, stats, cover_rel):
    cards = []
    for key in ["global", "japan", "korea"]:
        r = top1[key]
        c = CHARTS[key]
        cards.append(f"""
      <div class="card" style="--acc:{c['color']}"><img src="{cover_rel}/{r.name}.png"><div class="rk" style="color:{c['color']}">#1</div>
        <div class="chart" style="color:{c['color']}">{c['name']}</div>
        <div class="body"><div class="t">{esc(r.title)}</div><div class="a">{esc(r.artist)}</div>
        <div class="row"><div class="sc" style="color:{c['color']}">{r.fly_score:.1f}</div><div class="ci">± {r.ci95:.1f}</div></div></div></div>""")
    return f"""
  <section class="page hero" style="--acc:#c77dff">
    <div class="mast"><div class="logo"><span class="fly">🪰</span>FLYBOARD</div></div>
    <div class="sub" style="font-size:22px">The music chart voted by a fruit fly brain.</div>
    <div class="sub2" style="font-size:14px">We played {stats['n_songs']} songs to a simulation of an entire male fruit fly nervous system and asked:
      which one sounds most like love?</div>
    <div class="kpis"><div class="kpi"><b>{stats['n_neurons']:,}</b>neurons</div><div class="kpi"><b>90M</b>synapses</div>
      <div class="kpi"><b>{stats['n_songs']}</b>songs</div><div class="kpi"><b>{stats['sessions']}×</b>listening sessions</div>
      <div class="kpi"><b>0</b>humans consulted</div></div>
    <div class="trio">{''.join(cards)}</div>
    <div class="foot">Album art: every dot is a real neuron at its real position, lit by how hard it fired for that song. {REPO}</div>
  </section>"""


def page(body, extra_css=""):
    return f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}{extra_css}</style></head><body>{body}</body></html>"


def shoot(html_path, png_path, width=1200, height=6000):
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--window-size={width},{height}",
                    "--virtual-time-budget=8000", "--force-device-scale-factor=2", f"--screenshot={png_path}",
                    html_path.as_uri()], check=True, capture_output=True)
    im = Image.open(png_path).convert("RGB")
    a = np.asarray(im).astype(int)
    bg = a[-1, -1]
    rows = np.where(np.abs(a - bg).sum(2).max(1) > 12)[0]
    im.crop((0, 0, im.width, int(rows.max()) + 1 if len(rows) else im.height)).save(png_path, optimize=True)


def main():
    df = pd.read_csv(ROOT / "results" / "scores.csv", index_col="id")
    rob = json.loads((ROOT / "results" / "robustness.json").read_text())
    songs = df[df.chart != "control"].copy()
    songs["ci95"] = songs["ci95"].fillna(0)
    bass = songs.jo_B_hz / (songs.jo_A_hz + songs.jo_B_hz)
    stats = {"n_neurons": 165122, "n_songs": len(songs), "sessions": rob["sessions"],
             "fly_ref": float(df.loc["ctrl_flysong", "fly_score"]),
             "hot_cut": float(bass.quantile(0.8)), "jump_cut": float(songs.panic_GF_hz.quantile(0.85))}

    (DOCS / "_render").mkdir(parents=True, exist_ok=True)
    pages = {}
    for key in ["global", "japan", "korea"]:
        rows = songs[songs.chart == key].sort_values("fly_score", ascending=False)
        rows = rows.assign(rank=rows.chart_rank.astype(int))
        pages[key] = chart_page(key, rows, None, stats, "../covers")
    allrows = songs.sort_values("fly_score", ascending=False).head(10)
    allrows = allrows.assign(rank=allrows.overall_rank.astype(int))
    pages["all"] = chart_page("all", allrows, None, stats, "../covers", chart_tag=True)
    top1 = {k: songs[songs.chart == k].sort_values("fly_score").iloc[-1] for k in ["global", "japan", "korea"]}
    pages["hero"] = hero_page(top1, stats, "../covers")

    for name, body in pages.items():
        p = DOCS / "_render" / f"{name}.html"
        p.write_text(page(body), encoding="utf-8")
        shoot(p, ASSETS / f"chart_{name}.png")
        print("rendered", name)

    # interactive site: all pages stacked with tabs
    tabs = "".join(f'<button onclick="show(\'{k}\')" id="b-{k}">{CHARTS[k]["name"]}</button>' for k in ["all", "global", "japan", "korea"])
    secs = "".join(f'<div class="tab" id="t-{k}" style="display:none">{pages[k].replace("../covers", "covers")}</div>' for k in ["all", "global", "japan", "korea"])
    site_css = """
nav { position:sticky; top:0; z-index:9; display:flex; gap:8px; justify-content:center; padding:14px; background:#07080dcc; backdrop-filter:blur(10px); border-bottom:1px solid #1d2230; }
nav button { font:800 14px Inter,sans-serif; color:#cfd3e0; background:#141826; border:1px solid #262c3e; padding:9px 16px; border-radius:99px; cursor:pointer; }
nav button.on { background:#f4f5f8; color:#07080d; }
.wrap { display:flex; flex-direction:column; align-items:center; }
video { width:1200px; max-width:100%; border-radius:16px; margin:28px 0 8px; border:1px solid #1d2230; }
"""
    video = '<video src="flyboard_countdown.mp4" controls muted loop playsinline></video>' if (DOCS / "flyboard_countdown.mp4").exists() else ""
    site = page(f"""<nav>{tabs}</nav><div class="wrap">{pages['hero'].replace('../covers', 'covers')}{video}{secs}</div>
<script>function show(k){{document.querySelectorAll('.tab').forEach(e=>e.style.display='none');document.getElementById('t-'+k).style.display='block';
document.querySelectorAll('nav button').forEach(b=>b.classList.remove('on'));document.getElementById('b-'+k).classList.add('on');}}show('all');</script>""",
                site_css)
    (DOCS / "index.html").write_text(site, encoding="utf-8")
    print("wrote docs/index.html")


if __name__ == "__main__":
    main()
