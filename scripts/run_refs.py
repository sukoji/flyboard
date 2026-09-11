"""Simulate extra reference sounds (4 independent listens each) for the multi-axis scores.

  flybuzz   another fruit fly flying past (wingbeat buzz ~220 Hz, pass-by swells)
  wasp      a wasp-like predator coming at you (~130 Hz buzz, crescendos)
-> results/runs/refs_rates.npz  (hz [n_neurons, n_listens] float16, ids)
"""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from flyboard import ear
from flyboard.readout import EARS, groups
from flyboard.sim import Brain, Params, simulate

SEC, N_LISTENS = 30.0, 4
REFS = {"flybuzz": lambda s: ear.buzz(SEC, f0=220.0, seed=s), "wasp": lambda s: ear.buzz(SEC, f0=130.0, seed=s, approach=True)}


def main():
    ref = np.load(ROOT / "results" / "ear_ref.npy")
    ids, rates = [], []
    for name, make in REFS.items():
        for k in range(N_LISTENS):
            ids.append(f"{name}_{k}")
            rates.append(ear.rates_for(make(100 + k), ref, SEC))   # a different sound instance per listen
    brain = Brain()
    out = simulate(brain, list(groups(brain, EARS).values()), np.stack(rates), p=Params(), seed=31)
    hz = (out["counts"] / SEC).astype(np.float16)
    np.savez_compressed(ROOT / "results" / "runs" / "refs_rates.npz", hz=hz, ids=np.array(ids))
    print("saved", hz.shape, "mean JO drive", np.stack(rates).mean((0, 1)))


if __name__ == "__main__":
    main()
