"""Render a brain-painted cover for every song from the saved per-neuron firing rates."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from flyboard import connectome, ear
from flyboard.cover import render
from flyboard.style import CHARTS
from run_charts import SEC, controls

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "covers"
OUT.mkdir(parents=True, exist_ok=True)

runs = sorted((ROOT / "results" / "runs").glob("s*_rates.npz"))
ids = np.load(runs[0])["ids"]
hz = np.mean([np.load(r)["hz"].astype(np.float32) for r in runs], axis=0)  # [n, items]
scores = pd.read_csv(ROOT / "results" / "scores.csv", index_col="id")
neurons, *_ = connectome.load()
xy = neurons[["x", "y"]].to_numpy()
ok = ~np.isnan(xy).any(1)
x0, x1 = np.percentile(xy[ok, 0], [0.2, 99.8])
y0, y1 = np.percentile(xy[ok, 1], [0.2, 99.8])
dens, _, _ = np.histogram2d(xy[ok, 0], xy[ok, 1], bins=(200, 150), range=((x0, x1), (y0, y1)))
dens = np.log1p(dens.T) / np.log1p(dens).max()

song_cols = [i for i, s in enumerate(ids) if not s.startswith("ctrl_")]
mean_log = np.log1p(hz[:, song_cols]).mean(1)
bass = (scores.jo_B_hz / (scores.jo_A_hz + scores.jo_B_hz)).rank(pct=True)
tracks = pd.read_csv(ROOT / "results" / "tracks.csv", index_col="id")
ref = np.load(ROOT / "results" / "ear_ref.npy")
ctrl_audio = {k: v[2] for k, v in controls().items()}


def ring_of(sid):
    x = ctrl_audio[sid] if sid in ctrl_audio else ear.load_audio(ROOT / tracks.loc[sid, "audio"], SEC)
    r = ear.rates_for(x, ref, SEC)  # [30000 ms, 2]
    r = r[: len(r) // 250 * 250].reshape(-1, 250, 2).mean(1)  # 120 slices of 250 ms
    k = np.ones(3) / 3
    return np.stack([np.convolve(r[:, j], k, "same") for j in range(2)], 1)


for i, sid in enumerate(ids):
    chart = scores.loc[sid, "chart"]
    render(OUT / f"{sid}.png", xy, hz[:, i], mean_log, CHARTS[chart]["color"], float(bass.get(sid, 0.5)),
           size_px=480, density=dens, extent=(x0, x1, y0, y1), ring=ring_of(sid))
print(f"{len(ids)} covers -> {OUT}")
