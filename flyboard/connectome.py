"""Download and compile the MaleCNS v1.0 connectome into a signed graph.

Data: Janelia FlyEM / Google Research, "Sexual dimorphism in the complete connectome of the
Drosophila male central nervous system" (Cell, 2026). CC-BY 4.0.
"""
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.feather as feather

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
BASE = "https://storage.googleapis.com/flyem-male-cns/v1.0/connectome-data/flat-connectome"
FILES = {
    "ann": "body-annotations-male-cns-v1.0-minconf-0.5.feather",       # 13 MB
    "nt": "body-neurotransmitters-male-cns-v1.0.feather",             # 42 MB
    "w": "connectome-weights-male-cns-v1.0-minconf-0.5.feather",      # 1.1 GB
}
# GABA / glutamate (GluCl) / histamine (HisCl) are inhibitory; everything else excitatory
INHIBITORY = {"gaba", "glutamate", "histamine"}


def download():
    DATA.mkdir(exist_ok=True)
    for name in FILES.values():
        dst = DATA / name
        if not dst.exists():
            print(f"downloading {name}")
            subprocess.run(["curl", "-sSL", "-o", str(dst), f"{BASE}/{name}"], check=True)


def build(min_syn=5):
    """Traced neurons only, connections with >= min_syn synapses, sign from consensus NT."""
    ann = pd.read_feather(DATA / FILES["ann"])
    ann = ann[ann.status == "Traced"].reset_index(drop=True)
    neurons = ann[["bodyId", "type", "instance", "superclass", "class", "subclass",
                   "somaSide", "synonyms", "somaLocation"]].copy()
    nt = pd.read_feather(DATA / FILES["nt"], columns=["body", "consensus_nt"]).rename(columns={"body": "bodyId"})
    neurons = neurons.merge(nt, on="bodyId", how="left")
    neurons["consensus_nt"] = neurons["consensus_nt"].fillna("unclear")
    sign = np.where(neurons["consensus_nt"].isin(INHIBITORY), -1, 1).astype(np.int8)

    body = neurons["bodyId"].to_numpy()
    t = feather.read_table(DATA / FILES["w"], memory_map=True)
    ids = pa.array(body)
    t = t.filter(pc.and_(pc.and_(pc.is_in(t["body_pre"], value_set=ids), pc.is_in(t["body_post"], value_set=ids)),
                         pc.greater_equal(t["weight"], min_syn)))
    sorter = np.argsort(body)
    idx = lambda col: sorter[np.searchsorted(body, col.to_numpy(), sorter=sorter)].astype(np.int32)
    pre, post = idx(t["body_pre"]), idx(t["body_post"])
    w = t["weight"].to_numpy().astype(np.float32) * sign[pre]

    xyz = np.full((len(neurons), 3), np.nan, dtype=np.float32)
    has = neurons["somaLocation"].notna().to_numpy()
    xyz[has] = np.stack(neurons.loc[has, "somaLocation"].to_numpy()).astype(np.float32) * 8e-3  # 8 nm voxels -> um
    neurons = neurons.drop(columns="somaLocation")
    neurons[["x", "y", "z"]] = xyz

    np.savez(DATA / f"graph_min{min_syn}.npz", pre=pre, post=post, w=w)
    neurons.to_parquet(DATA / "neurons.parquet")
    print(f"{len(neurons):,} neurons, {len(w):,} connections, {np.abs(w).sum():,.0f} synapses (>= {min_syn})")


def load(min_syn=5):
    g = np.load(DATA / f"graph_min{min_syn}.npz")
    return pd.read_parquet(DATA / "neurons.parquet"), g["pre"], g["post"], g["w"]


if __name__ == "__main__":
    download()
    build()
