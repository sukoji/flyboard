"""Side-by-side video: the fly brain listening to fly song vs the #1 song vs the last-place song.

Renders assets/flyboard_brain.mp4 (silent; song audio is not redistributed) and a README GIF.
"""
import subprocess
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from flyboard import ear
from flyboard.readout import EARS, groups
from flyboard.sim import Brain, Params, simulate
from flyboard.style import BG, CHARTS, DISPLAY, INK, MUTED, fly_icon

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
SEC, FRAME_MS, FPS = 12.0, 40, 25
W, H, DPI = 1280, 720, 100
BRAIN_CMAP = LinearSegmentedColormap.from_list("brain", [BG, "#3a4052", "#c9cdd8"])


def pick_panels(preview):
    tracks = pd.read_csv(ROOT / "results" / "tracks.csv").set_index("id")
    fly = dict(title="Courtship Song", artist="another fruit fly", color="#9ecbff", label="REFERENCE",
               x=ear.fly_song(SEC, seed=1))
    song = lambda sid, label, color, score: dict(
        title=tracks.loc[sid, "title"], artist=tracks.loc[sid, "artist"], label=label, color=color, score=score,
        x=ear.load_audio(ROOT / tracks.loc[sid, "audio"], SEC))
    if preview:  # before scores exist: fixed songs, no scores
        fly["score"] = None
        return [fly, song("global_00", "PREVIEW", CHARTS["global"]["color"], None),
                song("japan_00", "PREVIEW", CHARTS["japan"]["color"], None)]
    df = pd.read_csv(ROOT / "results" / "scores.csv")
    songs = df[df.chart != "control"].sort_values("fly_score", ascending=False)
    best, worst = songs.iloc[0], songs.iloc[-1]
    fly["score"] = float(df.loc[df.id == "ctrl_flysong", "fly_score"].iat[0])
    return [fly, song(best.id, "#1 OVERALL", CHARTS[best.chart]["color"], best.fly_score),
            song(worst.id, "LAST PLACE", "#8a90a3", worst.fly_score)]


def main():
    global SEC
    preview = "--preview" in sys.argv
    if preview:
        SEC = 6.0
    name = "preview_brain" if preview else "flyboard_brain"
    panels = pick_panels(preview)
    ref = (np.load(ROOT / "results" / "ear_ref.npy") if (ROOT / "results" / "ear_ref.npy").exists()
           else np.percentile(ear.drive(ear.fly_song(30.0, seed=0)), 95, axis=0))
    rates = np.stack([ear.rates_for(p["x"], ref, SEC) for p in panels])

    brain = Brain()
    ears = groups(brain, EARS)
    out = simulate(brain, list(ears.values()), rates, p=Params(), seed=11, frame_ms=FRAME_MS, frame_cols=(0, 1, 2))
    frames = out["frames"]  # [F, n, 3]
    nr = brain.neurons
    xy = nr[["x", "y"]].to_numpy()
    has = ~np.isnan(xy).any(1)
    xy_h = xy[has]
    fr = frames[:, has, :]

    x0, x1 = np.nanpercentile(xy_h[:, 0], [0.2, 99.8])
    y0, y1 = np.nanpercentile(xy_h[:, 1], [0.2, 99.8])
    hist, xe, ye = np.histogram2d(xy_h[:, 0], xy_h[:, 1], bins=(220, 170), range=((x0, x1), (y0, y1)))
    bgimg = np.log1p(hist.T)

    # ear input envelopes for the scrolling strip (sum of both JO bands, 40 ms bins)
    env = rates.reshape(3, -1, FRAME_MS, rates.shape[2]).mean(2).sum(2)
    env /= env.max()

    fig = plt.figure(figsize=(W / DPI, H / DPI), dpi=DPI, facecolor=BG)
    hdr = fig.add_axes([0, 0.87, 1, 0.13])
    hdr.axis("off")
    hdr.set_xlim(0, 12.8)
    hdr.set_ylim(0, 1)
    fly_icon(hdr, 0.55, 0.52, s=0.55)
    hdr.text(1.0, 0.55, "FLYBOARD", fontsize=30, color=INK, family=DISPLAY, va="center", weight="bold")
    hdr.text(4.05, 0.62, "What a fruit fly brain hears", fontsize=15, color=INK, va="center")
    hdr.text(4.05, 0.3, "165,122 simulated neurons (MaleCNS v1.0 connectome). Dots = neurons firing right now.",
             fontsize=9.5, color=MUTED, va="center")
    tlabel = hdr.text(12.5, 0.55, "", fontsize=12, color=MUTED, va="center", ha="right", family="monospace")

    axes, dots, glows, strips, heads = [], [], [], [], []
    for i, p in enumerate(panels):
        left = 0.02 + i * 0.327
        ax = fig.add_axes([left, 0.2, 0.31, 0.66])
        ax.set_facecolor(BG)
        ax.imshow(bgimg, extent=(x0, x1, y1, y0), cmap=BRAIN_CMAP, vmin=0, vmax=bgimg.max() * 1.6, aspect="equal")
        ax.set_xlim(x0, x1)
        ax.set_ylim(y1, y0)
        ax.axis("off")
        glows.append(ax.scatter([], [], s=60, color=p["color"], alpha=0.18, lw=0))
        dots.append(ax.scatter([], [], s=6, color="white", alpha=0.95, lw=0))
        ax.text(0.02, 0.97, p["label"], transform=ax.transAxes, fontsize=9, color=p["color"], weight="bold", va="top")
        info = fig.add_axes([left, 0.01, 0.31, 0.19])
        info.axis("off")
        info.set_xlim(0, 1)
        info.set_ylim(0, 1)
        info.text(0.02, 0.86, (p["title"][:26] + "…") if len(p["title"]) > 27 else p["title"], fontsize=13, color=INK, weight="bold")
        info.text(0.02, 0.66, p["artist"][:34], fontsize=9.5, color=MUTED)
        if p["score"] is not None:
            info.text(0.98, 0.78, f"{p['score']:.1f}", fontsize=24, color=p["color"], ha="right", weight="bold", family=DISPLAY)
            info.text(0.98, 0.6, "FLY SCORE", fontsize=7, color=MUTED, ha="right")
        sx = np.linspace(0.02, 0.98, env.shape[1])
        info.fill_between(sx, 0.08, 0.08 + 0.36 * env[i], color=p["color"], alpha=0.35, lw=0)
        heads.append(info.axvline(0.02, 0.05, 0.5, color=INK, lw=1))
        strips.append(info.text(0.02, 0.47, "ear input", fontsize=7, color=MUTED))

    ffmpeg = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}",
                               "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20",
                               str(ASSETS / f"{name}.mp4")], stdin=subprocess.PIPE)
    trail = np.zeros_like(fr[0], dtype=np.float32)
    for f in range(len(fr)):
        trail = trail * 0.55 + fr[f]
        for i in range(3):
            on = trail[:, i] > 0.3
            pts = xy_h[on]
            glows[i].set_offsets(pts)
            glows[i].set_sizes(20 + 25 * np.minimum(trail[on, i], 4))
            dots[i].set_offsets(xy_h[fr[f][:, i] > 0])
            heads[i].set_xdata([0.02 + 0.96 * f / len(fr)] * 2)
        tlabel.set_text(f"t = {f * FRAME_MS / 1000:5.2f} s")
        fig.canvas.draw()
        ffmpeg.stdin.write(np.asarray(fig.canvas.buffer_rgba()).tobytes())
    ffmpeg.stdin.close()
    ffmpeg.wait()

    print("saved", ASSETS / f"{name}.mp4")
    if preview:
        return
    gif = ASSETS / f"{name}.gif"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-t", "8", "-i", str(ASSETS / f"{name}.mp4"), "-vf",
                    "fps=12,scale=860:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96[p];[b][p]paletteuse=dither=bayer:bayer_scale=4",
                    str(gif)], check=True)
    print("saved", gif, f"{gif.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
