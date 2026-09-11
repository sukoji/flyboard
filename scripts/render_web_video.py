"""Render the countdown video from the three.js page (docs/video.html) with headless Chrome.

Needs docs/data/replay.* (scripts/export_replay.py) and docs/data/songs.json etc. (scripts/export_web.py).
-> docs/flyboard_countdown.mp4 (with a synthetic fruit-fly courtship song as soundtrack) + assets/flyboard_countdown.gif
"""
import functools
import http.server
import subprocess
import sys
import threading
import wave
from pathlib import Path

import numpy as np
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from flyboard import ear

DOCS, ASSETS = ROOT / "docs", ROOT / "assets"
FPS = 25


def serve():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(DOCS))
    handler.log_message = lambda *a: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def main():
    srv = serve()
    url = f"http://127.0.0.1:{srv.server_address[1]}/video.html"
    silent = ASSETS / "_web_silent.mp4"
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", args=["--use-angle=d3d11", "--enable-gpu", "--ignore-gpu-blocklist"])
        pg = b.new_page(viewport={"width": 1920, "height": 1080})
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(url)
        pg.wait_for_function("window.ready === true", timeout=120_000)
        pg.evaluate("document.fonts.ready")
        n = pg.evaluate("window.totalFrames")
        ff = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "image2pipe", "-c:v", "mjpeg", "-r", str(FPS), "-i", "-",
                               "-vf", "scale=1280:720:flags=lanczos", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "27",
                               "-preset", "slow", "-tune", "animation", str(silent)], stdin=subprocess.PIPE)
        for i in range(n):
            pg.evaluate("""async (i) => { renderAt(i); const c = document.getElementById('cover');
                           if (c && c.src && !c.complete) await c.decode().catch(() => {}); }""", i)
            ff.stdin.write(pg.screenshot(type="jpeg", quality=92))
            if i % 100 == 0:
                print(f"frame {i}/{n}", flush=True)
        ff.stdin.close()
        ff.wait()
        b.close()
    if errors:
        print("page errors:", errors[:5])

    total = n / FPS
    sr = 44100
    fly = ear.fly_song(total, seed=3)
    fly = np.interp(np.arange(int(total * sr)) / sr, np.arange(len(fly)) / ear.SR, fly)
    fly = 0.3 * fly / np.abs(fly).max()
    wav = ASSETS / "_fly.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((fly * 32767).astype(np.int16).tobytes())
    mp4 = DOCS / "flyboard_countdown.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(silent), "-i", str(wav), "-c:v", "copy", "-c:a", "aac",
                    "-b:a", "64k", "-shortest", str(mp4)], check=True)
    silent.unlink()
    wav.unlink()
    gif = ASSETS / "flyboard_countdown.gif"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", "3", "-t", "9", "-i", str(mp4), "-vf",
                    "fps=10,scale=720:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128[p];[b][p]paletteuse=dither=bayer:bayer_scale=4",
                    str(gif)], check=True)
    print("saved", mp4, f"{mp4.stat().st_size / 1e6:.1f} MB", gif, f"{gif.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
