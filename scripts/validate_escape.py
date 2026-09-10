"""Sanity check of the brain model on a textbook circuit, before trusting it with music.

Looming detectors (LPLC2) -> giant fiber (DNp01) -> jump motor neuron (TTMn).
Silencing the giant fiber should abolish the jump motor output but spare parallel pathways.
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from flyboard.sim import Brain, Params, rates_hz, simulate
from flyboard.style import BG, INK, MUTED

ROOT = Path(__file__).resolve().parent.parent
SEC, TRIALS = 2.0, 8

brain = Brain()
stim = brain.ids(types=["LPLC2"])
gf = brain.ids(types=["DNp01"])
drive = np.full((TRIALS, int(SEC * 1000), 1), 150.0)
ctrl = rates_hz(simulate(brain, [stim], drive, p=Params(), seed=1)).mean(1)
lesion = rates_hz(simulate(brain, [stim], drive, p=Params(), seed=1, silence=gf)).mean(1)

cells = ["LPLC2", "DNp01", "TTMn", "DNp11", "DNp04"]
df = pd.DataFrame({"type": cells,
                   "control_hz": [ctrl[brain.ids(types=[c])].mean() for c in cells],
                   "gf_silenced_hz": [lesion[brain.ids(types=[c])].mean() for c in cells]}).round(1)
df.to_csv(ROOT / "results" / "escape_check.csv", index=False)
print(df.to_string(index=False))

fig, ax = plt.subplots(figsize=(7, 3.6), facecolor=BG)
ax.set_facecolor(BG)
x = np.arange(len(cells))
ax.bar(x - 0.2, df.control_hz, 0.4, color="#4dabff", label="looming stimulus")
ax.bar(x + 0.2, df.gf_silenced_hz, 0.4, color="#ff4d6d", label="+ giant fiber silenced")
labels = ["LPLC2\n(looming eye)", "DNp01\n(giant fiber)", "TTMn\n(jump muscle MN)", "DNp11", "DNp04\n(parallel DN)"]
ax.set_xticks(x, labels, color=INK, fontsize=8)
ax.set_ylabel("firing rate (Hz)", color=INK)
ax.tick_params(colors=MUTED)
for s in ax.spines.values():
    s.set_color("#333a4d")
ax.legend(frameon=False, labelcolor=INK, fontsize=8)
ax.set_title("Sanity check: the simulated escape reflex", color=INK, fontsize=11)
fig.tight_layout()
fig.savefig(ROOT / "assets" / "escape_check.png", dpi=150, facecolor=BG)
