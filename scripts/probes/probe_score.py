"""Quick check that FLY SCORE separates fly song from controls and songs (10 s clips)."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from flyboard import ear
from flyboard.readout import EARS, groups
from flyboard.sim import Brain, Params, simulate

ROOT = Path(__file__).resolve().parents[2]
SEC = 10.0
n = int(SEC * ear.SR)
t = np.arange(n) / ear.SR
rng = np.random.default_rng(0)
xs = {"ref": ear.fly_song(SEC, seed=0), "flysong2": ear.fly_song(SEC, seed=1), "noise": rng.normal(size=n),
      "tone440": np.sin(2 * np.pi * 440 * t), "tone200": np.sin(2 * np.pi * 200 * t), "metronome": ear.pulse_train(0.5, SEC)}
for f in sorted((ROOT / "audio" / "global").glob("*.m4a"))[:4]:
    xs[f.stem] = ear.load_audio(f, SEC)
ref = np.percentile(ear.drive(xs["ref"]), 95, axis=0)
rates = np.stack([ear.rates_for(x, ref, SEC) for x in xs.values()])

brain = Brain()
ears = groups(brain, EARS)
jo = np.concatenate(list(ears.values()))
mask = np.ones(brain.n, bool)
mask[jo] = False
out = simulate(brain, list(ears.values()), rates, p=Params())
hz = out["counts"] / SEC
V = np.log1p(hz[mask])
for name, tf in [("log1p", lambda h: np.log1p(h)), ("sqrt", np.sqrt), ("binary>1Hz", lambda h: (h > 1).astype(float))]:
    V = tf(hz[mask])
    cos = V.T @ V[:, 0] / (np.linalg.norm(V, axis=0) * np.linalg.norm(V[:, 0]) + 1e-12)
    print(name, {k: round(100 * c, 1) for k, c in zip(xs, cos)})
print("lit", {k: int((hz[mask, i] > 1).sum()) for i, k in enumerate(xs)})
print("JO B/A mean Hz", {k: (round(hz[ears['JO-B'], i].mean()), round(hz[ears['JO-A'], i].mean())) for i, k in enumerate(xs)})
