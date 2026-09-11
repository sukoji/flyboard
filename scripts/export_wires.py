"""Connections for the 3D viewer (docs/data/), drawn soma to soma as straight lines.

  wires.bin      the connectome's backbone: the strongest connections (most synapses) between neurons with a soma
                 uint32 pre, uint32 post (soma indices), uint8 strength
  songwires.bin  per song and per command: the strongest connections *between neurons that were active*,
                 ranked by synapses x presynaptic firing; offsets written into songs.json / commands.json
Run after export_web.py and export_commands.py.
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from flyboard import connectome

OUT = ROOT / "docs" / "data"
N_BACKBONE, N_ACTIVE = 20000, 1500
SESSIONS = ["s1", "s2", "s3", "s4"]


def pack(pre, post, s):
    return pre.astype(np.uint32).tobytes() + post.astype(np.uint32).tobytes() + s.astype(np.uint8).tobytes() + b"\0" * (-len(s) % 4)


def top_edges(pre, post, w, rate, active, k):
    """Strongest edges inside the active set, ranked by synapses x log presynaptic rate."""
    m = active[pre] & active[post] & (pre != post)
    p, q, ww = pre[m], post[m], w[m]
    score = ww * np.log1p(rate[p])
    o = np.argsort(-score)[:k]
    s = score[o]
    return p[o], q[o], np.clip(np.round(255 * s / (s.max() + 1e-9)), 1, 255)


def main():
    nr, pre, post, w = connectome.load()
    web_index = np.load(ROOT / "results" / "web_index.npy")
    has = web_index >= 0
    m = has[pre] & has[post] & (pre != post)
    o = np.argsort(-w[m])[:N_BACKBONE]
    bp, bq, bw = pre[m][o], post[m][o], w[m][o].astype(float)
    (OUT / "wires.bin").write_bytes(pack(web_index[bp], web_index[bq], np.clip(np.round(255 * np.log1p(bw) / np.log1p(bw.max())), 1, 255)))
    print(f"backbone: {len(o):,} edges, {w[m][o].min()}-{w[m][o].max()} synapses")

    blob = bytearray()
    songs_meta = json.loads((OUT / "songs.json").read_text(encoding="utf-8"))
    hz = np.mean([np.load(ROOT / "results" / "runs" / f"{t}_rates.npz")["hz"].astype(np.float32) for t in SESSIONS], 0)
    ids = list(np.load(ROOT / "results" / "runs" / "s1_rates.npz")["ids"])
    col = {s: i for i, s in enumerate(ids)}
    for s in songs_meta["songs"]:
        r = hz[:, col[s["id"]]]
        p, q, st = top_edges(pre, post, w, r, (r > 0.5) & has, N_ACTIVE)
        s["woff"], s["wn"] = len(blob), int(len(p))
        blob += pack(web_index[p], web_index[q], st)

    cmd_meta = json.loads((OUT / "commands.json").read_text(encoding="utf-8"))
    cbin = (OUT / "commands.bin").read_bytes()
    inv = np.full(int(web_index.max()) + 1, -1, np.int64)
    inv[web_index[has]] = np.flatnonzero(has)
    for c in cmd_meta["commands"]:
        counts = np.zeros(len(nr), np.float32)
        for off, n in c["frames"]:
            counts[inv[np.frombuffer(cbin, np.uint32, n, off)]] += 1
        r = counts / (len(c["frames"]) * cmd_meta["frame_ms"] / 1000)
        p, q, st = top_edges(pre, post, w, r, (r > 0.5) & has, N_ACTIVE)
        c["woff"], c["wn"] = len(blob), int(len(p))
        blob += pack(web_index[p], web_index[q], st)
        print(f"{c['emoji']} {c['label']:15s} {len(p)} active edges")

    (OUT / "songwires.bin").write_bytes(bytes(blob))
    (OUT / "songs.json").write_text(json.dumps(songs_meta, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (OUT / "commands.json").write_text(json.dumps(cmd_meta, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wires.bin {(OUT / 'wires.bin').stat().st_size / 1e6:.2f} MB, songwires.bin {len(blob) / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
