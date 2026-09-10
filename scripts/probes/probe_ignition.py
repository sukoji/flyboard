"""When does 'ignition' happen, and does it persist? Per-second activity for two 30 s fly songs."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from flyboard import ear
from flyboard.readout import EARS, groups
from flyboard.sim import Brain, Params, simulate

SEC = 30.0
ref = np.percentile(ear.drive(ear.fly_song(30.0, seed=0)), 95, axis=0)
xs = [ear.fly_song(SEC, seed=s) for s in (0, 1, 2, 3)]
brain = Brain()
ears = groups(brain, EARS)
jo = np.concatenate(list(ears.values()))
out = simulate(brain, list(ears.values()), np.stack([ear.rates_for(x, ref, SEC) for x in xs]), p=Params(), seed=9,
               frame_ms=1000, frame_cols=(0, 1, 2, 3))
fr = out["frames"].astype(np.float32)  # [30 s, n, 4]
fr[:, jo, :] = 0
active = (fr > 0).sum(1)  # neurons spiking in each second
print("neurons active per second (cols = fly song seeds 0..3):")
for t in range(0, 30, 2):
    print(f"  t={t:2d}s ", active[t])
hz = fr.mean(0)
extra = np.flatnonzero((hz[:, 1] > 1) & (hz[:, 0] < 0.2))
print("extra in seed1 vs seed0:", len(extra))
nr = brain.neurons.iloc[extra]
print(nr.groupby(["superclass", "type"]).size().sort_values(ascending=False).head(15).to_string())
on = (fr[:, extra, 1] > 0).mean(1)
print("fraction of 'extra' neurons active per second (seed1):", np.round(on, 2))
np.save(Path(__file__).resolve().parents[2] / "results" / "ignition_extra.npy", extra)
