"""Simulate the 5 highlight listens (each chart's #1, last place, fly song) and export them for replay in
the browser: which somata spiked in each 40 ms frame, plus body-part channels. -> docs/data/replay.{bin,json}

The abdominal/flight motor latch switches on at a random moment, so each 12 s listen is cut to the
6 s window that starts 2.5 s before it (or the first 6 s if it never happens), as in the video.
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from flyboard import ear
from flyboard.readout import EARS, groups
from flyboard.sim import Brain, Params, simulate
from make_countdown import FRAME_MS, SEG_SEC, SIM_SEC, calibration, motor_channels, segments

OUT = ROOT / "docs" / "data"


def main():
    segs, fly_ref = segments()
    ref = np.load(ROOT / "results" / "ear_ref.npy")
    rates = np.stack([ear.rates_for(s["x"], ref, SIM_SEC) for s in segs])
    brain = Brain()
    chans = motor_channels(brain)
    full = calibration(chans)
    out = simulate(brain, list(groups(brain, EARS).values()), rates, p=Params(), seed=21, frame_ms=FRAME_MS,
                   frame_cols=tuple(range(len(segs))), record=chans, rec_ms=FRAME_MS)
    frames = out["frames"]
    web_index = np.load(ROOT / "results" / "web_index.npy")
    n_show = int(SEG_SEC * 1000 / FRAME_MS)
    ear_env = rates.reshape(len(segs), -1, FRAME_MS, rates.shape[2]).mean(2) / ear.R_MAX  # [S, F, 2]

    blob, meta = bytearray(), []
    for k, s in enumerate(segs):
        on = np.flatnonzero(out["groups"]["abdomen"][k] > 10)
        start = int(np.clip(on[0] - 2500 / FRAME_MS, 0, frames.shape[0] - n_show)) if len(on) else 0
        offs = []
        for f in range(start, start + n_show):
            w = web_index[np.flatnonzero(frames[f, :, k])]
            w = w[w >= 0].astype(np.uint32)
            offs.append([len(blob), int(len(w))])
            blob += w.tobytes()
        body = {c: np.round(np.clip(out["groups"][c][k, start:start + n_show] / full[c], 0, 1), 3).tolist() for c in chans}
        body["ear"] = np.round(ear_env[k, start:start + n_show].sum(1) / 2, 3).tolist()
        meta.append({"id": s["id"], "kicker": s["kicker"], "title": s["title"], "artist": s["artist"], "chart": s["chart"],
                     "score": round(float(s["fly_score"]), 1), "t0": round(start * FRAME_MS / 1000, 2),
                     "latch_s": round(float(on[0] * FRAME_MS / 1000), 2) if len(on) else None,
                     "frames": offs, "body": body})
        print(f"{s['kicker']:18s} window t={start * FRAME_MS / 1000:.1f}s  latch={meta[-1]['latch_s']}")
    (OUT / "replay.bin").write_bytes(bytes(blob))
    (OUT / "replay.json").write_text(json.dumps({"frame_ms": FRAME_MS, "fly_ref": fly_ref, "segments": meta},
                                                ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"replay.bin {len(blob) / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
