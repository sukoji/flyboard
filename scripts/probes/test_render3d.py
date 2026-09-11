"""Static test frames for the 3D brain and the fly puppet."""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from flyboard.puppet import Fly, draw_fly
from flyboard.render3d import Camera, brain_coords, draw_brain
from flyboard.style import BG

out = Path(sys.argv[1])
fig, axes = plt.subplots(1, 3, figsize=(18, 6), facecolor=BG)
for ax in axes:
    ax.set_facecolor(BG)
    ax.set_aspect("equal")
    ax.axis("off")

cam = Camera(yaw=35, pitch=22, dist=7.0, target=(0.2, 0.0, 0))
rest = {}
busy = {"Lfl": .8, "Rfl": .8, "Lml": .8, "Rml": .8, "Lhl": .8, "Rhl": .8, "wingL": .8, "wingR": .8, "abdomen": .7,
        "jump": .6, "proboscis": .8, "ear": 1, "neckL": .6, "haltere": 1}
for ax, ch in zip(axes[:2], [rest, busy]):
    fly = Fly()
    for _ in range(10):
        pass
    draw_fly(ax, cam, fly, ch, 0.9)
    ax.set_xlim(-0.9, 0.9)
    ax.set_ylim(-0.6, 0.7)

nr = pd.read_parquet(ROOT / "data" / "neurons.parquet")
P, ok = brain_coords(nr)
z = np.load(ROOT / "results" / "runs" / "s1_rates.npz")
hz = z["hz"][:, 0].astype(np.float32)
bg = np.flatnonzero(ok)[:: 3]
bcam = Camera(yaw=35, pitch=18, dist=4.6)
draw_brain(axes[2], bcam, np.nan_to_num(P), ok, np.log1p(hz), "#f5c542", bg)
axes[2].set_xlim(-0.9, 0.9)
axes[2].set_ylim(-0.85, 0.85)
print("P range", np.nanmin(P, 0), np.nanmax(P, 0))
fig.savefig(out, dpi=80, facecolor=BG)
