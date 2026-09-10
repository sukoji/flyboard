"""Speed check + sanity check against the escape-circuit result (LPLC2 -> DNp01 -> TTMn)."""
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from flyboard.sim import Brain, Params, rates_hz, simulate

brain = Brain()
stim = brain.ids(types=["LPLC2"])
for B in (1, 8, 16):
    rates = np.full((B, 500, 1), 150.0)  # 500 ms of 150 Hz
    t0 = time.time()
    out = simulate(brain, [stim], rates, p=Params(w_syn=0.1), record={"GF": brain.ids(types=["DNp01"])})
    dt = time.time() - t0
    r = rates_hz(out).mean(1)
    print(f"B={B:2d}: {dt:5.1f}s wall for 0.5 s sim ({dt / 0.5:.0f}x slower than real time, {dt / 0.5 / B:.1f}x per column)"
          f"  LPLC2={r[stim].mean():.0f}Hz GF={r[brain.ids(types=['DNp01'])].mean():.0f}Hz "
          f"TTMn={r[brain.ids(types=['TTMn'])].mean():.0f}Hz active={(r > 1).sum()}")
