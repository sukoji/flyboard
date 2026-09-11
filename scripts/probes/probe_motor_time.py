"""Time course of body-part motor channels during a 30 s song (1 s bins)."""
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

tracks = pd.read_csv(ROOT / "results" / "tracks.csv", index_col="id")
ref = np.load(ROOT / "results" / "ear_ref.npy")
xs = [ear.load_audio(ROOT / tracks.loc["korea_08", "audio"], 30), ear.fly_song(30, seed=1)]
brain = Brain()
ears = groups(brain, EARS)
ch = motor_channels(brain)
keep = {k: ch[k] for k in ["abdomen", "wingL", "wingR", "Lhl", "haltere", "jump"] if k in ch}
out = simulate(brain, list(ears.values()), np.stack([ear.rates_for(x, ref, 30) for x in xs]), p=Params(), seed=4,
               record=keep, rec_ms=1000)
for k, v in out["groups"].items():
    print(f"{k:8s} song:", np.round(v[0], 1).tolist())
    print(f"{'':8s} fly: ", np.round(v[1], 1).tolist())
