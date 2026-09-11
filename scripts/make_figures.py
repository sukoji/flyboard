"""Analysis figure: what the fly's score actually tracks. -> assets/fly_likes_bass.png"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from flyboard.style import BG, CHARTS, INK, MUTED

ROOT = Path(__file__).resolve().parent.parent


def trim(s, n):
    return s if len(s) <= n else s[: n - 1] + "…"


def main():
    df = pd.read_csv(ROOT / "results" / "scores.csv", index_col="id")
    songs = df[df.chart != "control"]
    bass = lambda d: d.jo_B_hz / (d.jo_A_hz + d.jo_B_hz)
    fig, ax = plt.subplots(figsize=(9, 5.6), facecolor=BG)
    ax.set_facecolor(BG)
    for chart, g in songs.groupby("chart"):
        ax.scatter(bass(g), g.fly_score, s=46, color=CHARTS[chart]["color"], edgecolor="none", alpha=0.9, zorder=3,
                   label={"global": "Hot 30", "japan": "Japan", "korea": "Korea"}[chart])
        ax.errorbar(bass(g), g.fly_score, yerr=g.mad, fmt="none", ecolor=CHARTS[chart]["color"], alpha=0.35, zorder=2)
    label = set(songs.fly_score.nlargest(4).index) | set(songs.fly_score.nsmallest(2).index)
    for sid in label:
        r = songs.loc[sid]
        ax.annotate(trim(str(r.title), 22), (bass(r), r.fly_score), xytext=(6, 3), textcoords="offset points", fontsize=8.5, color=INK)
    r_ = np.corrcoef(bass(songs), songs.fly_score)[0, 1]
    ax.set_xlabel("share of low-frequency (80-300 Hz) input to the fly's ear  —  JO-B / (JO-A + JO-B)", color=INK)
    ax.set_ylabel("FLY SCORE", color=INK)
    ax.set_title(f"The fly likes bass: songs that feed its low-frequency ear neurons score higher (r = {r_:.2f})",
                 color=INK, fontsize=11)
    ax.tick_params(colors=MUTED)
    for s in ax.spines.values():
        s.set_color("#333a4d")
    ax.legend(frameon=False, labelcolor=INK, loc="upper left")
    fig.tight_layout()
    fig.savefig(ROOT / "assets" / "fly_likes_bass.png", dpi=150, facecolor=BG)
    print("saved assets/fly_likes_bass.png", f"r={r_:.2f}")


def radars():
    """Five-axis radars (percentile among the 84 songs) for the #1s, the last place and two controls."""
    ax_df = pd.read_csv(ROOT / "results" / "axes.csv", index_col="id")
    df = pd.read_csv(ROOT / "results" / "scores.csv", index_col="id")
    songs = df[df.chart != "control"]
    picks = [songs[songs.chart == c].fly_score.idxmax() for c in ["global", "japan", "korea"]]
    picks += [songs.fly_score.idxmin(), "ctrl_flysong", "ctrl_metronome"]
    names = ["love", "fly buzz", "danger", "startle", "arousal"]
    keys = ["p_love", "p_flybuzz", "p_danger", "p_startle", "p_arousal"]
    ang = np.linspace(0, 2 * np.pi, len(keys), endpoint=False).tolist()
    fig, axs = plt.subplots(1, 6, figsize=(15, 3.2), subplot_kw={"polar": True}, facecolor=BG)
    for a, sid in zip(axs, picks):
        chart = df.loc[sid, "chart"]
        col = CHARTS[chart]["color"] if chart in CHARTS else "#9ecbff"
        v = ax_df.loc[sid, keys].to_numpy(float).tolist()
        a.set_facecolor(BG)
        a.fill(ang + ang[:1], v + v[:1], color=col, alpha=0.35)
        a.plot(ang + ang[:1], v + v[:1], color=col, lw=1.8)
        a.set_ylim(0, 100)
        a.set_xticks(ang)
        a.set_xticklabels(names, color=MUTED, fontsize=8)
        a.set_yticklabels([])
        a.grid(color="#2a3044")
        a.spines["polar"].set_color("#2a3044")
        title = "fly song (control)" if sid == "ctrl_flysong" else "metronome (control)" if sid == "ctrl_metronome" else trim(str(df.loc[sid, "title"]), 18)
        a.set_title(title, color=INK, fontsize=10, pad=14)
    fig.suptitle("Five axes, as percentiles among the 84 songs", color=INK, fontsize=11, y=1.02)
    fig.savefig(ROOT / "assets" / "axes.png", dpi=130, facecolor=BG, bbox_inches="tight")
    print("saved assets/axes.png")


if __name__ == "__main__":
    main()
    radars()
