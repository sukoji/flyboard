"""Export compact binary data for the three.js viewer (docs/data/).

  somata.bin   int16 xyz (x 30000 scale) of every neuron with a soma, in brain_coords() orientation
  region.bin   uint8 region code per soma: 0 central brain, 1 optic lobe, 2 nerve cord, 3 other
  songs.json   metadata, scores, body-part channel activity, ear rings, byte offsets into rates.bin
  rates.bin    per song: uint32 soma indices + uint8 log-rate + uint8 fingerprint (active neurons only)
  replay.bin   5 highlight listens (the video's segments): per 40 ms frame, the somata that spiked
  replay.json  offsets, channel time series and metadata for replay.bin
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from flyboard import connectome, ear
from flyboard.render3d import brain_coords

OUT = ROOT / "docs" / "data"
OUT.mkdir(parents=True, exist_ok=True)
SESSIONS = ["s1", "s2", "s3", "s4"]


def region_codes(nr):
    sc = nr.superclass.fillna("")
    r = np.full(len(nr), 3, np.uint8)
    r[sc.str.startswith("cb_").to_numpy()] = 0
    r[(sc.str.startswith("ol_") | sc.str.startswith("visual")).to_numpy()] = 1
    r[sc.str.startswith("vnc").to_numpy()] = 2
    return r


def body_channels(nr, hz):
    """Mean rate per body-part channel for each item [items] -> dict of arrays."""
    mot = nr.superclass.isin(["vnc_motor", "cb_motor"]).to_numpy()
    sub = nr.subclass.fillna("").to_numpy()
    side = nr.somaSide.fillna("").to_numpy()
    sel = {"legs": mot & np.isin(sub, ["fl", "ml", "hl"]), "wings": mot & (sub == "wm"), "abdomen": mot & (sub == "ad"),
           "proboscis": mot & (sub == "pm"), "neckL": mot & (sub == "nm") & (side == "L"),
           "neckR": mot & (sub == "nm") & (side == "R"), "haltere": mot & (sub == "hm"),
           "jump": nr.type.isin(["TTMn", "Tergotr. MN"]).to_numpy()}
    return {k: hz[np.flatnonzero(m)].mean(0) for k, m in sel.items()}


def main():
    nr, *_ = connectome.load()
    P, ok = brain_coords(nr)
    soma = np.flatnonzero(ok)
    web_index = np.full(len(nr), -1, np.int64)
    web_index[soma] = np.arange(len(soma))
    (np.clip(P[soma], -1.09, 1.09) * 30000).astype(np.int16).tofile(OUT / "somata.bin")
    region_codes(nr)[soma].tofile(OUT / "region.bin")

    hz = np.mean([np.load(ROOT / "results" / "runs" / f"{t}_rates.npz")["hz"].astype(np.float32) for t in SESSIONS], 0)
    ids = list(np.load(ROOT / "results" / "runs" / "s1_rates.npz")["ids"])
    song_cols = [i for i, s in enumerate(ids) if not s.startswith("ctrl_")]
    lg = np.log1p(hz)
    mean_log = lg[:, song_cols].mean(1)
    chans = body_channels(nr, hz)
    full = {k: max(1.0, float(v[song_cols].max()) * 1.2) for k, v in chans.items()}

    scores = pd.read_csv(ROOT / "results" / "scores.csv", index_col="id")
    tracks = pd.read_csv(ROOT / "results" / "tracks.csv", index_col="id")
    refv = np.load(ROOT / "results" / "ear_ref.npy")
    from run_charts import SEC, controls
    ctrl_audio = {k: v[2] for k, v in controls().items()}

    axes = pd.read_csv(ROOT / "results" / "axes.csv", index_col="id") if (ROOT / "results" / "axes.csv").exists() else None
    AX = ["love", "flybuzz", "danger", "startle", "arousal"]
    blob, songs = bytearray(), []
    for i, sid in enumerate(ids):
        act = np.flatnonzero((hz[:, i] > 0.5) & ok)
        idx = web_index[act].astype(np.uint32)
        rate = np.clip(np.round(40 * lg[act, i]), 1, 255).astype(np.uint8)
        fp = np.clip(np.round(128 + 100 * (lg[act, i] - mean_log[act])), 0, 255).astype(np.uint8)
        off = len(blob)
        blob += idx.tobytes() + rate.tobytes() + fp.tobytes()
        blob += b"\0" * (-len(blob) % 4)  # keep every block 4-byte aligned for Uint32Array views
        x = ctrl_audio[sid] if sid in ctrl_audio else ear.load_audio(ROOT / tracks.loc[sid, "audio"], SEC)
        ring = ear.rates_for(x, refv, SEC)
        ring = ring[: len(ring) // 250 * 250].reshape(-1, 250, 2).mean(1) / ear.R_MAX
        r = scores.loc[sid]
        songs.append({
            "id": sid, "chart": r.chart, "title": str(r.title), "artist": str(r.artist),
            "score": round(float(r.fly_score), 2), "spread": round(float(r["mad"]), 2),
            "rank": None if r.chart == "control" else int(r.chart_rank),
            "overall": None if r.chart == "control" else int(r.overall_rank),
            "lit": int(r.neurons_lit), "gf": round(float(r.panic_GF_hz), 1),
            "body": {k: round(float(min(1, v[i] / full[k])), 3) for k, v in chans.items()},
            "ring": np.round(ring, 3).tolist(), "offset": off, "n": int(len(idx)),
            "cover": f"covers/{sid}.png",
            "listen": tracks.loc[sid, "itunes_url"] if sid in tracks.index else None,
            "axes": None if axes is None else {k: [float(axes.loc[sid, f"p_{k}"]),
                                                    None if pd.isna(axes.loc[sid, k]) else float(axes.loc[sid, k])] for k in AX},
        })
    (OUT / "rates.bin").write_bytes(bytes(blob))
    meta = {"n_somata": int(len(soma)), "n_neurons": int(len(nr)), "scale": 30000,
            "body_full_scale_hz": {k: round(v, 2) for k, v in full.items()}, "songs": songs}
    (OUT / "songs.json").write_text(json.dumps(meta, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"somata {len(soma):,}  rates.bin {len(blob) / 1e6:.2f} MB  songs {len(songs)}")
    np.save(ROOT / "results" / "web_index.npy", web_index)


if __name__ == "__main__":
    main()
