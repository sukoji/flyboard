"""Which 'commands' move the body in this model? Drive a command neuron type (optogenetics-style Poisson
input) for 2 s and read the motor channels of each body part."""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from flyboard.sim import Brain, Params, simulate
from make_countdown import motor_channels

SEC, HZ = 2.0, 200.0
brain = Brain()
nr = brain.neurons
t = nr.type.fillna("")
side = nr.somaSide.fillna("")
CMDS = {
    "jump (DNp01)": t == "DNp01",
    "backward walk (MDN)": t == "MDN",
    "forward walk (DNp09)": t == "DNp09",
    "turn left (DNa02 L)": (t == "DNa02") & (side == "L"),
    "steer (DNa01)": t == "DNa01",
    "sing (pIP10)": t == "pIP10",
    "groom (DNg12)": t.str.startswith("DNg12"),
    "proboscis (MN9)": t == "MN9",
    "control (no input)": t == "__none__",
}
groups = [np.flatnonzero(m.to_numpy()) for m in CMDS.values()]
groups = [g if len(g) else np.array([0]) for g in groups]
T = int(SEC * 1000)
rates = np.zeros((len(CMDS), T, len(CMDS)), np.float32)
for k in range(len(CMDS) - 1):
    rates[k, :, k] = HZ
chans = motor_channels(brain)
out = simulate(brain, groups, rates, p=Params(), seed=5, record=chans, rec_ms=int(SEC * 1000))
names = list(CMDS)
keys = ["Lfl", "Rfl", "Lml", "Rml", "Lhl", "Rhl", "wingL", "wingR", "abdomen", "proboscis", "neckL", "neckR", "haltere", "jump"]
print(f"{'command':24s}" + "".join(f"{k:>9s}" for k in keys))
for i, n in enumerate(names):
    print(f"{n:24s}" + "".join(f"{out['groups'][k][i, 0]:9.1f}" if k in out["groups"] else f"{'-':>9s}" for k in keys))
