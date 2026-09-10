"""Sanity probe: do the song readouts respond to fly courtship song more than to noise/tones?"""
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from flyboard import ear
from flyboard.readout import EARS, READOUTS, groups
from flyboard.sim import Brain, Params, simulate

import os
w_list = [float(a) for a in sys.argv[1:]] or [0.125]
GAIN = float(os.environ.get("GAIN", "1"))
SEC = 5.0
rng = np.random.default_rng(0)
n = int(SEC * ear.SR)
tt = np.arange(n) / ear.SR
sounds = {
    "silence": np.zeros(n) + 1e-9 * rng.normal(size=n),
    "fly_song": ear.fly_song(SEC),
    "white_noise": rng.normal(size=n),
    "tone_440": np.sin(2 * np.pi * 440 * tt),
    "tone_200": np.sin(2 * np.pi * 200 * tt),
    "metronome_120bpm": ear.pulse_train(0.5, SEC),
    "pulse_ipi35": ear.pulse_train(0.035, SEC),
}
drives = {k: ear.drive(v) for k, v in sounds.items()}
ref = np.percentile(drives["fly_song"], 95, axis=0)
print("ref drive per band:", ref)
rates = np.stack([ear.to_rates(d, ref) for d in drives.values()]) * GAIN
rates[0] = 0.0  # silence (normalize() would blow the 1e-9 noise up to full volume)
print("GAIN", GAIN)
print("mean JO rate per sound (B, A):", {k: np.round(r.mean(0), 1).tolist() for k, r in zip(sounds, rates)})

brain = Brain()
ears = groups(brain, EARS)
rec = groups(brain, READOUTS)
print({k: len(v) for k, v in {**ears, **rec}.items()})
for w in w_list:
    t0 = time.time()
    out = simulate(brain, list(ears.values()), rates, p=Params(w_syn=w, v_noise=float(os.environ.get("NOISE", "0"))),
                   record=rec, rec_ms=100)
    active = (out["counts"] / SEC > 1).sum(0)
    print(f"\nw_syn={w}  ({time.time() - t0:.0f}s)")
    print(f"{'sound':18s} " + " ".join(f"{k:>12s}" for k in rec) + "   active")
    for i, name in enumerate(sounds):
        print(f"{name:18s} " + " ".join(f"{out['groups'][k][i].mean():12.1f}" for k in rec) + f"   {active[i]}")
