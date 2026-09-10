"""Play every song to the simulated male fly (one "listening session") and record its response.

Similarity = cosine between the brain-wide response to a song and the response to Drosophila
courtship song (log1p firing rates of every neuron except the ear's own JO neurons).
scripts/score.py turns several sessions into the final anchored FLY SCORE.

usage: python scripts/run_charts.py --tag s1 --seed 1 [--w-syn 0.125] [--adapt 0.6] [--save-rates]
"""
import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from flyboard import ear
from flyboard.readout import EARS, READOUTS, groups
from flyboard.sim import Brain, Params, simulate

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "results" / "runs"
SEC = 30.0
BATCH = 32


def controls():
    n = int(SEC * ear.SR)
    t = np.arange(n) / ear.SR
    rng = np.random.default_rng(7)
    return {
        "ctrl_flysong": ("Drosophila melanogaster", "Courtship Song (another fly)", ear.fly_song(SEC, seed=1)),
        "ctrl_noise": ("Control", "White Noise", rng.normal(size=n)),
        "ctrl_tone": ("Control", "440 Hz Tone", np.sin(2 * np.pi * 440 * t)),
        "ctrl_metronome": ("Control", "Metronome 120 BPM", ear.pulse_train(0.5, SEC)),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="s0")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--w-syn", type=float, default=Params.w_syn)
    ap.add_argument("--adapt", type=float, default=ear.ADAPT)
    ap.add_argument("--save-rates", action="store_true")
    a = ap.parse_args()
    ear.ADAPT = a.adapt
    P = Params(w_syn=a.w_syn)
    RUNS.mkdir(parents=True, exist_ok=True)

    tracks = pd.read_csv(ROOT / "results" / "tracks.csv")
    tracks = tracks[tracks.found].reset_index(drop=True)
    items = [(r.id, r.chart, r.artist, r.title, ear.load_audio(ROOT / r.audio, SEC)) for r in tracks.itertuples()]
    items += [(k, "control", ar, ti, x) for k, (ar, ti, x) in controls().items()]
    ref_x = ear.fly_song(SEC, seed=0)
    ref = np.percentile(ear.drive(ref_x), 95, axis=0)
    if a.adapt == ear.ADAPT_DEFAULT:  # variant runs must not overwrite the ear calibration used by the videos
        np.save(ROOT / "results" / "ear_ref.npy", ref)

    brain = Brain()
    ears = groups(brain, EARS)
    rec = groups(brain, READOUTS)
    jo = np.concatenate(list(ears.values()))
    mask = np.ones(brain.n, bool)
    mask[jo] = False
    rates_of = lambda xs: np.stack([ear.rates_for(x, ref, SEC) for x in xs])

    t0 = time.time()
    ref_out = simulate(brain, list(ears.values()), rates_of([ref_x]), p=P, seed=10_000 + a.seed)
    ref_hz = ref_out["counts"][:, 0] / SEC
    ref_vec = np.log1p(ref_hz[mask])
    print(f"[{a.tag}] reference fly song ({time.time() - t0:.0f}s); neurons lit: {(ref_hz > 1).sum()}", flush=True)

    rows, all_hz = [], []
    for b in range(0, len(items), BATCH):
        chunk = items[b: b + BATCH]
        t0 = time.time()
        out = simulate(brain, list(ears.values()), rates_of([c[4] for c in chunk]), p=P, seed=a.seed * 1000 + b)
        hz = out["counts"] / SEC
        all_hz.append(hz.astype(np.float16))
        for j, (sid, chart, artist, title, _) in enumerate(chunk):
            vec = np.log1p(hz[mask, j])
            rows.append({"id": sid, "chart": chart, "artist": artist, "title": title,
                         "cos": float(vec @ ref_vec / (np.linalg.norm(vec) * np.linalg.norm(ref_vec) + 1e-12)),
                         "neurons_lit": int((hz[mask, j] > 1).sum()),
                         "heart_aPN1_hz": float(hz[rec["aPN1"], j].mean()),
                         "panic_GF_hz": float(hz[rec["GF"], j].mean()),
                         "jo_A_hz": float(hz[ears["JO-A"], j].mean()),
                         "jo_B_hz": float(hz[ears["JO-B"], j].mean())})
        print(f"[{a.tag}] batch {b // BATCH + 1}: {len(chunk)} songs in {time.time() - t0:.0f}s", flush=True)

    pd.DataFrame(rows).to_csv(RUNS / f"{a.tag}.csv", index=False, encoding="utf-8")
    if a.save_rates:
        np.savez_compressed(RUNS / f"{a.tag}_rates.npz", ids=np.array([r["id"] for r in rows]),
                            hz=np.concatenate(all_hz, 1), ref_hz=ref_hz.astype(np.float16))
    print(f"[{a.tag}] done", flush=True)


if __name__ == "__main__":
    main()
