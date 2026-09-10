"""Is the response to the same input identical whether simulated alone (B=1) or inside a batch?"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from flyboard import ear
from flyboard.readout import EARS, groups
from flyboard.sim import Brain, Params, simulate

SEC = float(sys.argv[1]) if len(sys.argv) > 1 else 5.0
a, b = ear.fly_song(SEC, seed=0), ear.fly_song(SEC, seed=1)
ref = np.percentile(ear.drive(ear.fly_song(30.0, seed=0)), 95, axis=0)
ra, rb = ear.rates_for(a, ref, SEC), ear.rates_for(b, ref, SEC)
print("mean JO rates a/b:", ra.mean(0), rb.mean(0))
brain = Brain()
ears = groups(brain, EARS)
jo = np.concatenate(list(ears.values()))
m = np.ones(brain.n, bool)
m[jo] = False
alone = simulate(brain, list(ears.values()), ra[None], p=Params(), seed=123)["counts"][:, 0] / SEC
both = simulate(brain, list(ears.values()), np.stack([ra, rb]), p=Params(), seed=5)["counts"] / SEC
cos = lambda x, y: float(np.log1p(x[m]) @ np.log1p(y[m]) / np.linalg.norm(np.log1p(x[m])) / np.linalg.norm(np.log1p(y[m])))
print("lit alone", (alone > 1).sum(), "| batch a", (both[:, 0] > 1).sum(), "| batch b", (both[:, 1] > 1).sum())
print("cos(alone, batch a)", cos(alone, both[:, 0]), " cos(alone, batch b)", cos(alone, both[:, 1]),
      " cos(batch a, batch b)", cos(both[:, 0], both[:, 1]))
