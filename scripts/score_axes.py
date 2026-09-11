"""Five axes instead of one. Template axes use the FLY SCORE formula against different reference sounds;
readout axes are percentiles among the 84 songs.

  love     brain response vs fly courtship song                      (= FLY SCORE)
  flybuzz  brain response vs another fruit fly flying past (~220 Hz)   "sounds like one of us"
  danger   brain response vs a wasp-like predator coming at you (~130 Hz)
  startle  giant-fiber (escape neuron) firing, percentile
  arousal  neurons lit, percentile
-> results/axes.csv, results/axes.json (correlations between axes)
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from score import MAIN, RUNS, brain_mask, cos_to


def template_scores(ref_vec, mask, tags):
    per = {}
    for t in tags:
        z = np.load(RUNS / f"{t}_rates.npz")
        c = pd.Series(cos_to(ref_vec, z["hz"], mask), index=list(z["ids"]))
        per[t] = 100 * (c - c["ctrl_noise"]) / (1 - c["ctrl_noise"])
    return pd.DataFrame(per).median(1)


def main():
    mask = brain_mask()
    tags = [t for t in MAIN if (RUNS / f"{t}_rates.npz").exists()]
    refs = np.load(RUNS / "refs_rates.npz")
    rid = list(refs["ids"])
    lg = lambda hz: np.log1p(hz.astype(np.float32)[mask])
    templates = {
        "love": np.median([lg(np.load(RUNS / f"{t}_rates.npz")["ref_hz"]) for t in tags], 0),
        "flybuzz": np.median([lg(refs["hz"][:, i]) for i, s in enumerate(rid) if s.startswith("flybuzz")], 0),
        "danger": np.median([lg(refs["hz"][:, i]) for i, s in enumerate(rid) if s.startswith("wasp")], 0),
    }
    scores = pd.read_csv(ROOT / "results" / "scores.csv", index_col="id")
    ax = pd.DataFrame({k: template_scores(v, mask, tags) for k, v in templates.items()})
    songs = scores.index[scores.chart != "control"]
    pct = lambda s: 100 * s.rank(pct=True)
    ax["startle"] = np.nan
    ax["arousal"] = np.nan
    ax.loc[songs, "startle"] = pct(scores.loc[songs, "panic_GF_hz"])
    ax.loc[songs, "arousal"] = pct(scores.loc[songs, "neurons_lit"])
    # radar scale: percentile among the 84 songs (controls placed on the songs' distribution)
    for k in ["love", "flybuzz", "danger"]:
        dist = np.sort(ax.loc[songs, k].to_numpy())
        ax[f"p_{k}"] = 100 * np.searchsorted(dist, ax[k].to_numpy(), side="right") / len(dist)
    for k, col in [("startle", "panic_GF_hz"), ("arousal", "neurons_lit")]:
        dist = np.sort(scores.loc[songs, col].to_numpy())
        ax[f"p_{k}"] = 100 * np.searchsorted(dist, scores.loc[ax.index, col].to_numpy(), side="right") / len(dist)
    ax = ax.round(1)
    ax.index.name = "id"
    ax.to_csv(ROOT / "results" / "axes.csv", encoding="utf-8")
    s = ax.loc[songs, ["love", "flybuzz", "danger", "startle", "arousal"]]
    corr = s.corr(method="spearman").round(2)
    tops = {k: [scores.loc[i, "title"] for i in s[k].nlargest(3).index] for k in s}
    out = {"spearman_between_axes": corr.to_dict(), "top3": tops,
           "controls": ax.loc[[i for i in ax.index if i.startswith("ctrl_")], ["love", "flybuzz", "danger"]].to_dict("index")}
    (ROOT / "results" / "axes.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(corr.to_string())
    print(json.dumps(tops, indent=1, ensure_ascii=False))
    print(out["controls"])


if __name__ == "__main__":
    main()
