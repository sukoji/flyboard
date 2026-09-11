"""How much does the brain add? Score every song with the same formula as the FLY SCORE, but on the
ear input alone (no brain), with several reasonable summaries of what the two JO channels carry:

  level        mean drive of JO-A and JO-B (how loud each band is)
  bass_share   JO-B / (JO-A + JO-B), ranked directly (no template)
  rhythm       modulation spectrum of both channels, 1-60 Hz (pulses, beats, rhythm)
  level+rhythm both

Template variants: EAR SCORE = 100 * (sim(song) - sim(white noise)) / (1 - sim(white noise)),
sim = cosine to the same fly song the brain reference used.
-> results/baseline_ear.json
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import signal, stats

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from flyboard import ear
from run_charts import SEC, controls

FS = 250  # Hz, after binning the 1 ms JO rates


def features(x, ref):
    r = ear.rates_for(x, ref, SEC)                        # [30000 ms, 2]
    r = r[: len(r) // 4 * 4].reshape(-1, 4, 2).mean(1)    # 4 ms bins
    f, p = signal.welch(r, fs=FS, nperseg=512, axis=0)
    keep = (f >= 1) & (f <= 60)
    level = np.log1p(r.mean(0))
    rhythm = np.log1p(np.sqrt(p[keep]).ravel())
    return {"level": level, "rhythm": rhythm, "level+rhythm": np.concatenate([level, rhythm]),
            "bass": r[:, 0].mean() / (r.mean(0).sum() + 1e-9)}   # channel 0 = JO-B (low band)


def main():
    ref = np.load(ROOT / "results" / "ear_ref.npy")
    scores = pd.read_csv(ROOT / "results" / "scores.csv", index_col="id")
    tracks = pd.read_csv(ROOT / "results" / "tracks.csv", index_col="id")
    ctrl = {k: v[2] for k, v in controls().items()}
    target = features(ear.fly_song(SEC, seed=0), ref)
    feats = {}
    for sid in scores.index:
        x = ctrl[sid] if sid in ctrl else ear.load_audio(ROOT / tracks.loc[sid, "audio"], SEC)
        feats[sid] = features(x, ref)

    songs = scores[scores.chart != "control"]
    res = {}
    for kind in ["level", "rhythm", "level+rhythm", "bass"]:
        if kind == "bass":
            s = pd.Series({k: v["bass"] for k, v in feats.items()}) * 100
        else:
            t = target[kind]
            sim = pd.Series({k: float(v[kind] @ t / (np.linalg.norm(v[kind]) * np.linalg.norm(t))) for k, v in feats.items()})
            s = 100 * (sim - sim["ctrl_noise"]) / (1 - sim["ctrl_noise"])
        e = s[songs.index]
        top = lambda v: set(v.nlargest(10).index)
        res[kind] = {"spearman_rho": round(float(stats.spearmanr(songs.fly_score, e).statistic), 3),
                     "top10_overlap": len(top(songs.fly_score) & top(e)),
                     "same_chart_number1": sum(int(g.fly_score.idxmax() == e[g.index].idxmax()) for _, g in songs.groupby("chart")),
                     "controls": {k: round(float(s[k]), 1) for k in ctrl}}
        if kind == "level+rhythm":
            scores["ear_score"] = s.round(2)
    scores.to_csv(ROOT / "results" / "scores.csv", encoding="utf-8")
    (ROOT / "results" / "baseline_ear.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(res, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
