"""Where does JO input actually go? Top targets and top responders to fly song."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from flyboard import connectome, ear
from flyboard.readout import EARS, READOUTS, groups
from flyboard.sim import Brain, Params, simulate

brain = Brain()
nr = brain.neurons
ears = groups(brain, EARS)
rec = groups(brain, READOUTS)
_, pre, post, w = connectome.load()

jo = np.concatenate(list(ears.values()))
m = np.isin(pre, jo)
tgt = pd.DataFrame({"post": post[m], "w": w[m]}).groupby("post").w.sum().sort_values(ascending=False)
t = nr.loc[tgt.index, ["type", "superclass", "consensus_nt", "synonyms"]].assign(syn_from_JO=tgt.values)
print("== top JO-A/B targets by synapses (>=5-syn connections)")
print(t.groupby(["type", "consensus_nt"]).syn_from_JO.agg(["sum", "size"]).sort_values("sum", ascending=False).head(20).to_string())
print("JO output synapses total:", int(np.abs(w[m]).sum()), " per JO neuron:", int(np.abs(w[m]).sum() / len(jo)))

# graph hops from JO to each readout group
A_next = {}
dist = np.full(brain.n, -1)
dist[jo] = 0
front = np.zeros(brain.n, bool)
front[jo] = True
exc = w > 0
for d in range(1, 6):
    nxt = np.zeros(brain.n, bool)
    nxt[post[front[pre] & exc]] = True
    nxt &= dist < 0
    dist[nxt] = d
    front = nxt
print("\n== min excitatory hops from JO:", {k: int(dist[v][dist[v] >= 0].min()) if (dist[v] >= 0).any() else -1 for k, v in rec.items()})

x = ear.fly_song(5.0)
d = ear.drive(x)
ref = np.percentile(d, 95, axis=0)
out = simulate(brain, list(ears.values()), ear.to_rates(d, ref)[None] * float(sys.argv[1] if len(sys.argv) > 1 else 1.0),
               p=Params(w_syn=0.125))
r = out["counts"][:, 0] / 5.0
df = nr.assign(rate=r)
df = df[~df.index.isin(jo)]
print("\n== top responders to fly song (w_syn=0.125)")
print(df.groupby(["type", "superclass"]).rate.agg(["mean", "size"]).sort_values("mean", ascending=False).head(25).to_string())
