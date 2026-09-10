"""FLYBOARD countdown video: each chart's #1, the last place, and the fly's true #1.

Every segment shows the brain-painted cover, the brain firing live while it listens, and the score
counting up. Soundtrack: synthetic fruit-fly courtship song only (song audio is not redistributed).
-> assets/flyboard_countdown.mp4 (+ docs copy) and assets/flyboard_countdown.gif
"""
import subprocess
import sys
import wave
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from flyboard import ear
from flyboard.readout import EARS, groups
from flyboard.sim import Brain, Params, simulate
from flyboard.style import BG, DISPLAY, INK, MUTED, fly_icon

ROOT = Path(__file__).resolve().parent.parent
ASSETS, DOCS = ROOT / "assets", ROOT / "docs"
W, H, DPI, FPS, FRAME_MS = 1280, 720, 100, 25, 40
SEG_SEC, CARD_SEC = 5.0, 2.6
FLAGS = {"global": "HOT 30", "japan": "JAPAN", "korea": "KOREA", "control": ""}
COLORS = {"global": "#f5c542", "japan": "#ff4d6d", "korea": "#4dabff", "control": "#9ecbff"}
BRAIN_CMAP = LinearSegmentedColormap.from_list("brain", [BG, "#2c3242", "#b9bfcc"])


def segments():
    df = pd.read_csv(ROOT / "results" / "scores.csv", index_col="id")
    tracks = pd.read_csv(ROOT / "results" / "tracks.csv", index_col="id")
    songs = df[df.chart != "control"]
    segs = []
    for chart in ["korea", "japan", "global"]:
        sid = songs[songs.chart == chart].fly_score.idxmax()
        segs.append(dict(id=sid, kicker=f"#1 IN {FLAGS[chart]}", **df.loc[sid, ["title", "artist", "chart", "fly_score"]].to_dict(),
                         x=ear.load_audio(ROOT / tracks.loc[sid, "audio"], SEG_SEC)))
    sid = songs.fly_score.idxmin()
    segs.append(dict(id=sid, kicker="LAST PLACE", **df.loc[sid, ["title", "artist", "chart", "fly_score"]].to_dict(),
                     x=ear.load_audio(ROOT / tracks.loc[sid, "audio"], SEG_SEC)))
    segs.append(dict(id="ctrl_flysong", kicker="THE FLY'S TRUE #1", title="Courtship Song", artist="another fruit fly",
                     chart="control", fly_score=float(df.loc["ctrl_flysong", "fly_score"]), x=ear.fly_song(SEG_SEC, seed=1)))
    return segs


def main():
    segs = segments()
    ref = np.load(ROOT / "results" / "ear_ref.npy")
    rates = np.stack([ear.rates_for(s["x"], ref, SEG_SEC) for s in segs])
    brain = Brain()
    ears = groups(brain, EARS)
    out = simulate(brain, list(ears.values()), rates, p=Params(), seed=21, frame_ms=FRAME_MS,
                   frame_cols=tuple(range(len(segs))))
    frames = out["frames"]
    xy = brain.neurons[["x", "y"]].to_numpy()
    has = ~np.isnan(xy).any(1)
    xy_h, fr = xy[has], frames[:, has, :]
    x0, x1 = np.percentile(xy_h[:, 0], [0.2, 99.8])
    y0, y1 = np.percentile(xy_h[:, 1], [0.2, 99.8])
    hist, _, _ = np.histogram2d(xy_h[:, 0], xy_h[:, 1], bins=(330, 255), range=((x0, x1), (y0, y1)))
    bgimg = np.log1p(hist.T)
    bgimg[bgimg < 0.8] = 0  # stray somata outside the CNS outline -> background
    fly_ref = float(pd.read_csv(ROOT / "results" / "scores.csv", index_col="id").loc["ctrl_flysong", "fly_score"])

    fig = plt.figure(figsize=(W / DPI, H / DPI), dpi=DPI, facecolor=BG)
    ffmpeg = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}",
                               "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "19",
                               str(ASSETS / "_countdown_silent.mp4")], stdin=subprocess.PIPE)
    def emit():
        fig.canvas.draw()
        ffmpeg.stdin.write(np.asarray(fig.canvas.buffer_rgba()).tobytes())

    def title_card(lines, sec, color=INK):
        n = int(sec * FPS)
        for f in range(n):
            fig.clf()
            ax = fig.add_axes([0, 0, 1, 1])
            ax.set_xlim(0, 12.8)
            ax.set_ylim(0, 7.2)
            ax.axis("off")
            ax.set_facecolor(BG)
            a = min(1, f / (0.4 * FPS))
            fly_icon(ax, 6.4, 5.2, s=1.2)
            for i, (txt, size, col, fam) in enumerate(lines):
                ax.text(6.4, 3.7 - i * 0.9, txt, fontsize=size, color=col, ha="center", va="center", alpha=a,
                        family=fam or None, weight="bold")
            emit()

    title_card([("FLYBOARD", 64, INK, DISPLAY), ("We played 84 songs to a simulated fruit fly brain.", 18, INK, None),
                ("165,122 neurons. 90 million synapses. Here's what it liked.", 13, MUTED, None)], 3.2)

    for k, s in enumerate(segs):
        color = COLORS[s["chart"]]
        cover = plt.imread(DOCS / "covers" / f"{s['id']}.png")
        n = int(SEG_SEC * 1000 / FRAME_MS)
        trail = np.zeros(fr.shape[1], np.float32)
        recent = np.zeros((5, fr.shape[1]), bool)
        for f in range(n):
            fig.clf()
            ax = fig.add_axes([0, 0, 1, 1])
            ax.set_xlim(0, 12.8)
            ax.set_ylim(0, 7.2)
            ax.axis("off")
            # kicker + title block
            ax.text(0.6, 6.55, s["kicker"], fontsize=22, color=color, family=DISPLAY, va="center")
            ax.text(0.6, 5.95, s["title"], fontsize=26 if len(s["title"]) < 22 else 20, color=INK, weight="bold", va="center")
            ax.text(0.6, 5.45, s["artist"], fontsize=14, color=MUTED, va="center")
            prog = min(1, f / (0.6 * n))
            shown = s["fly_score"] * (1 - (1 - prog) ** 3)
            ax.text(0.6, 1.3, f"{shown:.1f}", fontsize=54, color=color, family=DISPLAY, va="center")
            # meter: 0 = white noise ... 100 = brain's response to fly love song; triangle = another fly's song
            mx0, mx1, my = 2.35, 4.75, 1.25
            ax.add_patch(plt.Rectangle((mx0, my - 0.07), mx1 - mx0, 0.14, color="#1d2233", lw=0))
            ax.add_patch(plt.Rectangle((mx0, my - 0.07), (mx1 - mx0) * max(shown, 0) / 100, 0.14, color=color, lw=0))
            fx = mx0 + (mx1 - mx0) * fly_ref / 100
            ax.plot([fx], [my + 0.2], marker="v", color="#9ecbff", ms=8)
            ax.text(fx, my + 0.42, "fly song", color="#9ecbff", fontsize=8, ha="center")
            ax.text(mx0, my - 0.3, "0", color=MUTED, fontsize=8)
            ax.text(mx1, my - 0.3, "100", color=MUTED, fontsize=8, ha="right")
            ax.text(0.62, 0.45, "FLY SCORE  (0 = white noise · 100 = brain's response to fly love song)", fontsize=10,
                    color=MUTED, va="center")
            cax = fig.add_axes([0.047, 0.285, 0.3, 0.3 * W / H * 0.82])
            cax.imshow(cover)
            cax.axis("off")
            bax = fig.add_axes([0.4, 0.05, 0.58, 0.9])
            bax.set_facecolor(BG)
            bax.imshow(bgimg, extent=(x0, x1, y1, y0), cmap=BRAIN_CMAP, vmin=0, vmax=bgimg.max() * 1.4, aspect="equal",
                       interpolation="bilinear")
            trail = trail * 0.8 + fr[f, :, k]
            recent[f % 5] = fr[f, :, k] > 0
            on = trail > 0.25
            bax.scatter(xy_h[on, 0], xy_h[on, 1], s=30 + 40 * np.minimum(trail[on], 5), color=color, alpha=0.22, lw=0)
            bax.scatter(xy_h[on, 0], xy_h[on, 1], s=4 + 4 * np.minimum(trail[on], 5), color=color, alpha=0.8, lw=0)
            live = fr[f, :, k] > 0
            bax.scatter(xy_h[live, 0], xy_h[live, 1], s=9, color="white", alpha=0.95, lw=0)
            bax.set_xlim(x0, x1)
            bax.set_ylim(y1, y0)
            bax.axis("off")
            bax.text(0.99, 0.99, f"{int(recent.any(0).sum()):4d} neurons firing (last 200 ms)", transform=bax.transAxes,
                     ha="right", va="top", fontsize=11, color=MUTED, family="monospace")
            emit()

    title_card([("FLYBOARD", 64, INK, DISPLAY), ("Full charts: HOT 30 · JAPAN · KOREA", 18, INK, None),
                ("github.com/sukoji/flyboard", 16, "#c77dff", None)], CARD_SEC)
    ffmpeg.stdin.close()
    ffmpeg.wait()

    # soundtrack: fruit-fly courtship song (synthetic, copyright-free), quiet
    total = 3.2 + len(segs) * SEG_SEC + CARD_SEC
    sr = 44100
    fly = ear.fly_song(total, seed=3)
    fly = np.interp(np.arange(int(total * sr)) / sr, np.arange(len(fly)) / ear.SR, fly)
    fly = 0.3 * fly / np.abs(fly).max()
    with wave.open(str(ASSETS / "_fly.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((fly * 32767).astype(np.int16).tobytes())
    mp4 = ASSETS / "flyboard_countdown.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(ASSETS / "_countdown_silent.mp4"), "-i", str(ASSETS / "_fly.wav"),
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "96k", "-shortest", str(mp4)], check=True)
    (ASSETS / "_countdown_silent.mp4").unlink()
    (ASSETS / "_fly.wav").unlink()
    DOCS.mkdir(exist_ok=True)
    (DOCS / "flyboard_countdown.mp4").write_bytes(mp4.read_bytes())
    gif = ASSETS / "flyboard_countdown.gif"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", "3.2", "-t", "10", "-i", str(mp4), "-vf",
                    "fps=12,scale=800:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128[p];[b][p]paletteuse=dither=bayer:bayer_scale=4",
                    str(gif)], check=True)
    print("saved", mp4, gif, f"{gif.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
