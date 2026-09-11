"""Command mode: switch on a command neuron type (optogenetics-style Poisson input) and record what the
whole CNS and each body part's motor neurons do. 3 s per command: 0.5 s rest, 2 s ON, 0.5 s off.
-> docs/data/commands.{bin,json} (same layout as replay: spiking somata per 40 ms frame + body channels)

Which commands drive the body in this model was checked with scripts/probes/probe_commands.py.
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from flyboard.sim import Brain, Params, simulate
from make_countdown import FRAME_MS, motor_channels

OUT = ROOT / "docs" / "data"
PRE, ON, POST = 0.5, 2.0, 0.5
# id, emoji, label, neuron types, input Hz, style hint for the puppet, what it is
COMMANDS = [
    ("jump", "🦘", "Looming shadow", ["LPLC2"], 150, "hop", "LPLC2 looming detectors → giant fiber (DNp01) → jump muscle (TTMn)"),
    ("backward", "🔙", "Moonwalk", ["MDN"], 200, "backward", "MDN, the 'moonwalker' descending neurons (backward walking)"),
    ("sing", "🎵", "Sing", ["pIP10"], 200, "sing", "pIP10, the courtship-song command neuron"),
    ("groom", "🧼", "Groom", ["DNg12_a", "DNg12_b", "DNg12_c", "DNg12_d", "DNg12_e", "DNg12_f", "DNg12_g", "DNg12_h"], 200, "groom",
     "DNg12 descending neurons (antennal grooming family)"),
    ("p9", "🚶", "P9", ["DNp09"], 200, "walk", "DNp09 (P9), linked to forward walking and courtship pursuit"),
    ("feed", "👅", "Proboscis", ["MN9"], 200, "feed", "MN9, the proboscis-extension motor neuron"),
]


def main():
    brain = Brain()
    t = brain.neurons.type.fillna("")
    groups = []
    for _, _, _, types, *_ in COMMANDS:
        idx = np.flatnonzero(t.isin(types).to_numpy() | t.str.startswith(tuple(types)).to_numpy())
        groups.append(idx)
    T = int((PRE + ON + POST) * 1000)
    rates = np.zeros((len(COMMANDS), T, len(COMMANDS)), np.float32)
    for k, c in enumerate(COMMANDS):
        rates[k, int(PRE * 1000): int((PRE + ON) * 1000), k] = c[4]
    chans = motor_channels(brain)
    out = simulate(brain, groups, rates, p=Params(), seed=13, frame_ms=FRAME_MS, frame_cols=tuple(range(len(COMMANDS))),
                   record=chans, rec_ms=FRAME_MS)
    frames = out["frames"]
    web_index = np.load(ROOT / "results" / "web_index.npy")
    # full scale per channel: the strongest any command produced, so every command's movement is visible
    full = {c: max(2.0, float(v.max())) for c, v in out["groups"].items()}
    blob, meta = bytearray(), []
    for k, (cid, emoji, label, types, hz, style, what) in enumerate(COMMANDS):
        offs = []
        for f in range(frames.shape[0]):
            w = web_index[np.flatnonzero(frames[f, :, k])]
            w = w[w >= 0].astype(np.uint32)
            offs.append([len(blob), int(len(w))])
            blob += w.tobytes()
        body = {c: np.round(np.clip(v[k] / full[c], 0, 1), 3).tolist() for c, v in out["groups"].items()}
        peak = {c: round(float(v[k].max()), 1) for c, v in out["groups"].items() if v[k].max() > 1}
        meta.append({"id": cid, "emoji": emoji, "label": label, "what": what, "style": style, "n_neurons": int(len(groups[k])),
                     "on": [PRE, PRE + ON], "frames": offs, "body": body, "peak_hz": peak})
        print(f"{emoji} {label:15s} {len(groups[k]):4d} neurons  peaks: {peak}")
    (OUT / "commands.bin").write_bytes(bytes(blob))
    (OUT / "commands.json").write_text(json.dumps({"frame_ms": FRAME_MS, "commands": meta}, ensure_ascii=False,
                                                  separators=(",", ":")), encoding="utf-8")
    print(f"commands.bin {len(blob) / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
