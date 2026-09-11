"""When does the abdominal/flight motor latch switch on? 12 s listens, 3 seeds per sound."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from flyboard import ear
from flyboard.readout import EARS, groups
from flyboard.sim import Brain, Params, simulate
from make_countdown import motor_channels

SEC = 12.0
tracks = pd.read_csv(ROOT / "results" / "tracks.csv", index_col="id")
ref = np.load(ROOT / "results" / "ear_ref.npy")
names = ["korea_08", "japan_21", "global_00", "global_04"]
xs = [ear.load_audio(ROOT / tracks.loc[s, "audio"], SEC) for s in names] + [ear.fly_song(SEC, seed=1)]
names.append("flysong")
rates = np.stack([ear.rates_for(x, ref, SEC) for x in xs] * 3)
brain = Brain()
ab = motor_channels(brain)["abdomen"]
out = simulate(brain, list(groups(brain, EARS).values()), rates, p=Params(), seed=77, record={"ab": ab}, rec_ms=200)
a = out["groups"]["ab"]  # [15, 60]
for i, nm in enumerate(names * 3):
    on = np.flatnonzero(a[i] > 10)
    print(f"{nm:10s} seed{i // len(names)}  onset: {on[0] * 0.2 if len(on) else None}")
