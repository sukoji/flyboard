"""Sound for the 3D viewer, without hosting any copyrighted audio.

- Songs: look up Apple's official 30 s preview URL for each track (iTunes lookup API). The browser streams it
  straight from Apple, next to a link to the song on Apple Music. -> results/preview_urls.json
- Controls (fly courtship song, white noise, 440 Hz tone, metronome) are synthesised here, so they are
  encoded as small MP3s and served from the site. -> docs/data/audio/ctrl_*.mp3
"""
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from flyboard import ear
from run_charts import SEC, controls


def main():
    tracks = pd.read_csv(ROOT / "results" / "tracks.csv", index_col="id")
    ids = {sid: re.search(r"[?&]i=(\d+)", str(u)).group(1) for sid, u in tracks.itunes_url.items()
           if isinstance(u, str) and re.search(r"[?&]i=(\d+)", u)}
    urls = {}
    tid = list(ids.values())
    for k in range(0, len(tid), 150):
        q = ",".join(tid[k:k + 150])
        with urllib.request.urlopen(f"https://itunes.apple.com/lookup?id={q}&entity=song", timeout=30) as r:
            res = json.load(r)["results"]
        got = {str(x.get("trackId")): x.get("previewUrl") for x in res if x.get("previewUrl")}
        for sid, t in ids.items():
            if t in got:
                urls[sid] = got[t]
    (ROOT / "results" / "preview_urls.json").write_text(json.dumps(urls, indent=1), encoding="utf-8")
    print(f"preview urls: {len(urls)} / {len(tracks)}")

    out = ROOT / "docs" / "data" / "audio"
    out.mkdir(parents=True, exist_ok=True)
    for sid, (_, _, x) in controls().items():
        x = 0.5 * x / (np.abs(x).max() + 1e-9)
        pcm = (np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes()
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "s16le", "-ar", str(ear.SR), "-ac", "1", "-i", "-",
                        "-b:a", "48k", "-ar", "22050", str(out / f"{sid}.mp3")], input=pcm, check=True)
    print("control audio:", sorted(p.name for p in out.glob("*.mp3")))


if __name__ == "__main__":
    main()
