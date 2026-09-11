"""FLYBOARD countdown video (3D): each chart's #1, the last place, and the fly's true #1.

Per segment: left = brain-painted cover + score, middle = the whole CNS in 3D with firing neurons
lighting up, right = a fly puppet whose legs / wings / abdomen / proboscis / head are driven by the
simulated motor neurons of those body parts. Soundtrack: synthetic fruit-fly courtship song only.
-> docs/flyboard_countdown.mp4 and assets/flyboard_countdown.gif
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

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from flyboard import ear
from flyboard.puppet import Fly, draw_fly
from flyboard.readout import EARS, groups
from flyboard.render3d import Camera, brain_coords, draw_brain
from flyboard.sim import Brain, Params, simulate
from flyboard.style import BG, DISPLAY, INK, MUTED, fly_icon

ROOT = Path(__file__).resolve().parent.parent
ASSETS, DOCS = ROOT / "assets", ROOT / "docs"
W, H, DPI, FPS, FRAME_MS = 1920, 1080, 100, 25, 40
SEG_SEC, CARD_SEC, SIM_SEC = 6.0, 3.0, 12.0  # show 6 s out of a 12 s listen
FLAGS = {"global": "HOT 30", "japan": "JAPAN", "korea": "KOREA", "control": ""}
COLORS = {"global": "#f5c542", "japan": "#ff4d6d", "korea": "#4dabff", "control": "#9ecbff"}
METERS = [("walk", "legs", ["Lfl", "Rfl", "Lml", "Rml", "Lhl", "Rhl"]), ("wings", "wing motor", ["wingL", "wingR"]),
          ("abdomen", "abdominal MNs", ["abdomen"]), ("jump", "giant fiber → TTMn", ["jump"]),
          ("proboscis", "MN9/11/12", ["proboscis"]), ("ear", "Johnston's organ", ["ear"])]


def motor_channels(brain):
    nr = brain.neurons
    mot = nr.superclass.isin(["vnc_motor", "cb_motor"]).to_numpy()
    sub = nr.subclass.fillna("").to_numpy()
    side = nr.somaSide.fillna("").to_numpy()
    ch = {}
    for seg in ("fl", "ml", "hl"):
        for s in ("L", "R"):
            ch[f"{s}{seg}"] = np.flatnonzero(mot & (sub == seg) & (side == s))
    for s in ("L", "R"):
        ch[f"wing{s}"] = np.flatnonzero(mot & (sub == "wm") & (side == s))
        ch[f"neck{s}"] = np.flatnonzero(mot & (sub == "nm") & (side == s))
    ch["abdomen"] = np.flatnonzero(mot & (sub == "ad"))
    ch["proboscis"] = np.flatnonzero(mot & (sub == "pm"))
    ch["haltere"] = np.flatnonzero(mot & (sub == "hm"))
    ch["jump"] = brain.ids(types=["TTMn", "Tergotr. MN"])
    return {k: v for k, v in ch.items() if len(v)}


def calibration(chans):
    """Per-channel full-scale = highest mean rate any chart song produced (session s1), x1.5 for moment-to-moment peaks."""
    z = np.load(ROOT / "results" / "runs" / "s1_rates.npz")
    hz = z["hz"].astype(np.float32)
    return {k: max(1.0, 1.5 * float(hz[idx].mean(0).max())) for k, idx in chans.items()}


def segments():
    df = pd.read_csv(ROOT / "results" / "scores.csv", index_col="id")
    tracks = pd.read_csv(ROOT / "results" / "tracks.csv", index_col="id")
    songs = df[df.chart != "control"]
    segs = []
    for chart in ["korea", "japan", "global"]:
        sid = songs[songs.chart == chart].fly_score.idxmax()
        segs.append(dict(id=sid, kicker=f"#1 IN {FLAGS[chart]}", **df.loc[sid, ["title", "artist", "chart", "fly_score"]].to_dict(),
                         x=ear.load_audio(ROOT / tracks.loc[sid, "audio"], SIM_SEC)))
    sid = songs.fly_score.idxmin()
    segs.append(dict(id=sid, kicker="LAST PLACE", **df.loc[sid, ["title", "artist", "chart", "fly_score"]].to_dict(),
                     x=ear.load_audio(ROOT / tracks.loc[sid, "audio"], SIM_SEC)))
    segs.append(dict(id="ctrl_flysong", kicker="THE FLY'S TRUE #1", title="Courtship Song", artist="another fruit fly",
                     chart="control", fly_score=float(df.loc["ctrl_flysong", "fly_score"]), x=ear.fly_song(SIM_SEC, seed=1)))
    return segs, float(df.loc["ctrl_flysong", "fly_score"])


def main():
    segs, fly_ref = segments()
    ref = np.load(ROOT / "results" / "ear_ref.npy")
    rates = np.stack([ear.rates_for(s["x"], ref, SIM_SEC) for s in segs])
    brain = Brain()
    ears = groups(brain, EARS)
    chans = motor_channels(brain)
    full = calibration(chans)
    out = simulate(brain, list(ears.values()), rates, p=Params(), seed=21, frame_ms=FRAME_MS,
                   frame_cols=tuple(range(len(segs))), record=chans, rec_ms=FRAME_MS)
    frames = out["frames"]                                     # [F, n, S]
    # the abdominal/flight motor latch switches on at a random moment (0.4-8 s for songs, never for fly song in 12 s):
    # show the 6 s window that starts 2.5 s before it, or the first 6 s if it never happens
    n_show = int(SEG_SEC * 1000 / FRAME_MS)
    on = [np.flatnonzero(out["groups"]["abdomen"][k] > 10) for k in range(len(segs))]
    start = [int(np.clip(o[0] - 2500 / FRAME_MS, 0, frames.shape[0] - n_show)) if len(o) else 0 for o in on]
    series = {k: np.clip(v / full[k], 0, 1) for k, v in out["groups"].items()}  # [S, F]
    ear_env = rates.reshape(len(segs), -1, FRAME_MS, rates.shape[2]).mean(2).sum(2) / (2 * ear.R_MAX)
    series["ear"] = np.clip(ear_env * 1.6, 0, 1)
    for k in series:  # smooth for motion (EMA ~150 ms)
        a = 1 - np.exp(-FRAME_MS / 150)
        s = series[k].copy()
        for f in range(1, s.shape[1]):
            s[:, f] = s[:, f - 1] + a * (s[:, f] - s[:, f - 1])
        series[k] = s

    P, ok = brain_coords(brain.neurons)
    P = np.nan_to_num(P)
    bg_idx = np.flatnonzero(ok)[::3]
    fig = plt.figure(figsize=(W / DPI, H / DPI), dpi=DPI, facecolor=BG)
    ffmpeg = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}",
                               "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20",
                               str(ASSETS / "_countdown_silent.mp4")], stdin=subprocess.PIPE)
    clock = {"t": 0.0}

    def emit():
        fig.canvas.draw()
        ffmpeg.stdin.write(np.asarray(fig.canvas.buffer_rgba()).tobytes())
        clock["t"] += 1 / FPS

    def brain_axes():
        ax = fig.add_axes([0.27, 0.06, 0.42, 0.84])
        ax.set_facecolor(BG)
        ax.set_xlim(-0.9, 0.9)
        ax.set_ylim(-0.85, 0.85)
        ax.set_aspect("equal")
        ax.axis("off")
        return ax

    def bcam():
        return Camera(yaw=35 + 28 * np.sin(2 * np.pi * clock["t"] / 14), pitch=18, dist=4.6)

    def title_card(lines, sec):
        for f in range(int(sec * FPS)):
            fig.clf()
            ax = fig.add_axes([0, 0, 1, 1])
            ax.set_xlim(0, 19.2)
            ax.set_ylim(0, 10.8)
            ax.axis("off")
            bax = fig.add_axes([0.52, 0.05, 0.46, 0.9])
            bax.set_facecolor(BG)
            bax.set_xlim(-0.9, 0.9)
            bax.set_ylim(-0.85, 0.85)
            bax.set_aspect("equal")
            bax.axis("off")
            draw_brain(bax, bcam(), P, ok, np.zeros(brain.n), "#c77dff", bg_idx)
            a = min(1, f / (0.4 * FPS))
            fly_icon(ax, 1.6, 7.6, s=1.4)
            for i, (txt, size, col, fam) in enumerate(lines):
                ax.text(0.9, 5.9 - i * 1.15, txt, fontsize=size, color=col, alpha=a, family=fam or None, weight="bold")
            emit()

    title_card([("FLYBOARD", 84, INK, DISPLAY), ("We played 84 songs to a simulated fruit fly.", 26, INK, None),
                ("Every neuron of its brain and nerve cord. Every twitch of its body.", 17, MUTED, None)], CARD_SEC)

    for k, s in enumerate(segs):
        color = COLORS[s["chart"]]
        cover = plt.imread(DOCS / "covers" / f"{s['id']}.png")
        fly = Fly()
        trail = np.zeros(brain.n, np.float32)
        n = n_show
        fcam = Camera(yaw=30, pitch=20, dist=7.0, target=(0.2, 0.05, 0))
        for i in range(n):
            f = start[k] + i
            fig.clf()
            ax = fig.add_axes([0, 0, 1, 1])
            ax.set_xlim(0, 19.2)
            ax.set_ylim(0, 10.8)
            ax.axis("off")
            # left column
            ax.text(0.6, 10.05, s["kicker"], fontsize=30, color=color, family=DISPLAY, va="center")
            ax.text(0.6, 9.25, s["title"], fontsize=34 if len(s["title"]) < 20 else 26, color=INK, weight="bold", va="center")
            ax.text(0.6, 8.55, s["artist"], fontsize=17, color=MUTED, va="center")
            cax = fig.add_axes([0.03, 0.30, 0.22, 0.22 * W / H])
            cax.imshow(cover)
            cax.axis("off")
            prog = min(1, i / (0.6 * n))
            shown = s["fly_score"] * (1 - (1 - prog) ** 3)
            ax.text(0.6, 1.95, f"{shown:.1f}", fontsize=68, color=color, family=DISPLAY, va="center")
            mx0, mx1, my = 3.0, 5.0, 1.9
            ax.add_patch(plt.Rectangle((mx0, my - 0.09), mx1 - mx0, 0.18, color="#1d2233", lw=0))
            ax.add_patch(plt.Rectangle((mx0, my - 0.09), (mx1 - mx0) * max(shown, 0) / 100, 0.18, color=color, lw=0))
            fx = mx0 + (mx1 - mx0) * fly_ref / 100
            ax.plot([fx], [my + 0.3], marker="v", color="#9ecbff", ms=10)
            ax.text(fx, my + 0.55, "fly song", color="#9ecbff", fontsize=10, ha="center")
            ax.text(0.62, 1.0, "FLY SCORE", fontsize=13, color=INK, weight="bold")
            ax.text(0.62, 0.55, "0 = white noise · 100 = brain's response to fly love song", fontsize=10.5, color=MUTED)
            # middle: 3D brain
            bax = brain_axes()
            trail = trail * 0.8 + frames[f, :, k]
            draw_brain(bax, bcam(), P, ok, trail, color, bg_idx, spark=frames[f, :, k] > 0)
            bax.text(0.5, 0.99, "BRAIN  ·  165,122 neurons", transform=bax.transAxes, ha="center", va="top",
                     fontsize=13, color=MUTED, weight="bold")
            bax.text(0.5, 0.02, f"{int((frames[f, :, k] > 0).sum()):4d} neurons firing", transform=bax.transAxes,
                     ha="center", fontsize=12, color=MUTED, family="monospace")
            # right: fly puppet + meters
            fax = fig.add_axes([0.69, 0.33, 0.3, 0.57])
            fax.set_facecolor(BG)
            fax.set_xlim(-0.85, 0.85)
            fax.set_ylim(-0.55, 0.75)
            fax.set_aspect("equal")
            fax.axis("off")
            ch = {key: float(v[k, f]) for key, v in series.items()}
            fcam.yaw = bcam().yaw  # body and brain seen from the same angle
            fax.text(0.5, 0.92, f"listening t = {f * FRAME_MS / 1000:4.1f} s", transform=fax.transAxes, ha="center",
                     va="top", fontsize=11, color=MUTED, family="monospace")
            draw_fly(fax, fcam, fly, ch, 1 / FPS)
            fax.text(0.5, 0.99, "BODY  ·  driven by its motor neurons", transform=fax.transAxes, ha="center", va="top",
                     fontsize=13, color=MUTED, weight="bold")
            for i, (name, src, keys) in enumerate(METERS):
                v = float(np.mean([ch.get(c, 0) for c in keys]))
                y = 3.1 - i * 0.42
                ax.text(13.4, y, name.upper(), fontsize=11, color=INK, weight="bold", va="center")
                ax.text(14.9, y, src, fontsize=9, color=MUTED, va="center")
                ax.add_patch(plt.Rectangle((16.9, y - 0.09), 1.9, 0.18, color="#1d2233", lw=0))
                ax.add_patch(plt.Rectangle((16.9, y - 0.09), 1.9 * v, 0.18, color=color, lw=0))
            emit()

    title_card([("FLYBOARD", 84, INK, DISPLAY), ("Full charts: HOT 30 · JAPAN · KOREA", 26, INK, None),
                ("github.com/sukoji/flyboard", 22, "#c77dff", None)], CARD_SEC)
    ffmpeg.stdin.close()
    ffmpeg.wait()

    total = 2 * CARD_SEC + len(segs) * SEG_SEC
    sr = 44100
    flys = ear.fly_song(total, seed=3)
    flys = np.interp(np.arange(int(total * sr)) / sr, np.arange(len(flys)) / ear.SR, flys)
    flys = 0.3 * flys / np.abs(flys).max()
    with wave.open(str(ASSETS / "_fly.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((flys * 32767).astype(np.int16).tobytes())
    DOCS.mkdir(exist_ok=True)
    mp4 = DOCS / "flyboard_countdown.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(ASSETS / "_countdown_silent.mp4"), "-i", str(ASSETS / "_fly.wav"),
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "96k", "-shortest", str(mp4)], check=True)
    (ASSETS / "_countdown_silent.mp4").unlink()
    (ASSETS / "_fly.wav").unlink()
    gif = ASSETS / "flyboard_countdown.gif"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(CARD_SEC), "-t", "9", "-i", str(mp4), "-vf",
                    "fps=12,scale=860:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128[p];[b][p]paletteuse=dither=bayer:bayer_scale=4",
                    str(gif)], check=True)
    print("saved", mp4, gif, f"{gif.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
