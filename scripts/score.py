"""Combine listening sessions into the final FLY SCORE and check that the ranking is robust.

sim(song)   cosine similarity between the brain-wide response to the song (log1p firing rate of every
            neuron except the ear's own JO neurons) and the REFERENCE response.
REFERENCE   mean log1p response to fly courtship song over all main sessions. One 30 s listen can
            contain a random burst of self-sustained activity; averaging listens removes that.
FLY SCORE   100 * (sim(song) - sim(white noise)) / (1 - sim(white noise))      per session
            0 = white noise, 100 = the reference response. Final = mean over sessions, 95% t-CI.
Robustness  Spearman rank correlation between sessions, and with runs under different model settings.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "results" / "runs"
MAIN = ["s1", "s2", "s3", "s4"]
VARIANTS = {"w_syn 0.10 mV (weaker synapses)": "v_w010", "no ear adaptation": "v_noadapt"}


def brain_mask():
    types = pd.read_parquet(ROOT / "data" / "neurons.parquet", columns=["type"])["type"].fillna("")
    return ~(types.str.startswith("JO-A") | types.str.startswith("JO-B")).to_numpy()


def cos_to(ref_vec, hz, mask):
    V = np.log1p(hz[mask].astype(np.float32))
    return V.T @ ref_vec / (np.linalg.norm(V, axis=0) * np.linalg.norm(ref_vec) + 1e-12)


def session_scores(tag, ref_vec, mask):
    z = np.load(RUNS / f"{tag}_rates.npz")
    ids = list(z["ids"])
    c = pd.Series(cos_to(ref_vec, z["hz"], mask), index=ids)
    return 100 * (c - c["ctrl_noise"]) / (1 - c["ctrl_noise"])


def main():
    mask = brain_mask()
    main_tags = [t for t in MAIN if (RUNS / f"{t}_rates.npz").exists()]
    refs = [np.log1p(np.load(RUNS / f"{t}_rates.npz")["ref_hz"].astype(np.float32)[mask]) for t in main_tags]
    ref_vec = np.mean(refs, 0)
    S = pd.DataFrame({t: session_scores(t, ref_vec, mask) for t in main_tags})
    n = S.shape[1]

    meta = pd.read_csv(RUNS / f"{main_tags[0]}.csv", index_col="id")
    df = meta[["chart", "artist", "title"]].copy()
    df["fly_score"] = S.mean(1)
    df["ci95"] = stats.t.ppf(0.975, n - 1) * S.std(1, ddof=1) / np.sqrt(n)
    for col in ["neurons_lit", "heart_aPN1_hz", "panic_GF_hz", "jo_A_hz", "jo_B_hz"]:
        df[col] = pd.DataFrame({t: pd.read_csv(RUNS / f"{t}.csv", index_col="id")[col] for t in main_tags}).mean(1)
    for t in S:
        df[f"score_{t}"] = S[t]

    songs = df[df.chart != "control"].copy()
    songs["overall_rank"] = songs.fly_score.rank(ascending=False, method="min").astype(int)
    songs["chart_rank"] = songs.groupby("chart").fly_score.rank(ascending=False, method="min").astype(int)
    out = pd.concat([songs, df[df.chart == "control"]]).round(2)
    out.index.name = "id"
    out.to_csv(ROOT / "results" / "scores.csv", encoding="utf-8")

    sidx = songs.index
    rob = {"sessions": n, "reference_listens": len(refs), "median_ci95": round(float(songs.ci95.median()), 2),
           "score_range": [round(float(songs.fly_score.min()), 1), round(float(songs.fly_score.max()), 1)],
           "controls": {k: round(float(df.loc[k, "fly_score"]), 1) for k in df[df.chart == "control"].index},
           "variants": {}}
    rho_s = [stats.spearmanr(S.loc[sidx, a], S.loc[sidx, b]).statistic for i, a in enumerate(S) for b in list(S)[i + 1:]]
    rob["between_sessions_spearman_rho"] = round(float(np.mean(rho_s)), 3)
    for name, tag in VARIANTS.items():
        if (RUNS / f"{tag}_rates.npz").exists():
            z = np.load(RUNS / f"{tag}_rates.npz")
            v = session_scores(tag, np.log1p(z["ref_hz"].astype(np.float32)[mask]), mask).loc[sidx]
            rho = stats.spearmanr(songs.fly_score, v).statistic
            top10 = len(set(songs.fly_score.nlargest(10).index) & set(v.nlargest(10).index))
            rob["variants"][name] = {"spearman_rho": round(float(rho), 3), "top10_overlap": top10}
    bass = songs.jo_B_hz / (songs.jo_A_hz + songs.jo_B_hz)
    rob["corr_score_vs_bass_share"] = round(float(np.corrcoef(bass, songs.fly_score)[0, 1]), 3)
    (ROOT / "results" / "robustness.json").write_text(json.dumps(rob, indent=2))
    print(json.dumps(rob, indent=2))
    for chart, g in songs.groupby("chart"):
        print(f"\n== {chart}")
        print(g.sort_values("fly_score", ascending=False).head(5)[["artist", "title", "fly_score", "ci95"]].to_string())


if __name__ == "__main__":
    main()
