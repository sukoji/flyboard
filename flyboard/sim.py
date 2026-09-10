"""GPU leaky integrate-and-fire model of the whole male fly CNS (165k neurons).

Equations and parameters follow Shiu et al. 2024 (Nature, "A Drosophila computational brain
model reveals sensorimotor processing"):

    dv/dt = (v_0 - v + g) / t_mbr        (v frozen while refractory)
    dg/dt = -g / tau
    presynaptic spike -> g_post += w_syn * n_synapses * sign    (after t_dly)
    Poisson input     -> g += poi_kick

w_syn is rescaled for MaleCNS: its neurons carry ~1.4x more synapses than FlyWire's, and the
FlyWire value (0.275 mV) sends ~20k neurons into saturation. See README "Model".

State is laid out (neurons, batch) so every step is one cuSPARSE SpMM for the whole batch;
different batch columns can play different songs.
"""
from dataclasses import dataclass

import numpy as np
import torch

from . import connectome


@dataclass
class Params:
    dt: float = 0.2          # ms (t_rfc and t_dly are exact multiples; 0.1 gives the same rates)
    v_0: float = -52.0       # mV resting
    v_rst: float = -52.0     # mV reset
    v_th: float = -45.0      # mV threshold
    t_mbr: float = 20.0      # ms membrane time constant
    tau: float = 5.0         # ms synaptic time constant
    t_rfc: float = 2.2       # ms refractory period
    t_dly: float = 1.8       # ms synaptic delay
    w_syn: float = 0.125     # mV per synapse (Shiu: 0.275 on FlyWire)
    poi_kick: float = 68.75  # mV per Poisson input event (Shiu: 250 x 0.275)
    v_noise: float = 0.0     # mV, stationary std of membrane noise (spontaneous activity; Shiu: 0)


class Brain:
    def __init__(self, device="cuda", min_syn=5):
        self.neurons, pre, post, w = connectome.load(min_syn)
        self.n = len(self.neurons)
        self.device = device
        # built on the GPU: CPU coalesce crashes (OpenMP clash) once scipy has run in the process
        idx = torch.from_numpy(np.stack([post, pre]).astype(np.int64)).to(device)
        self.W = torch.sparse_coo_tensor(idx, torch.from_numpy(w).to(device), (self.n, self.n)).coalesce().to_sparse_csr()

    def ids(self, types=None, synonym=None, prefix=None):
        nr = self.neurons
        m = np.zeros(self.n, bool)
        if types is not None:
            m |= nr["type"].isin(list(types)).to_numpy()
        if synonym is not None:
            m |= nr["synonyms"].fillna("").str.contains(synonym, regex=False).to_numpy()
        if prefix is not None:
            m |= nr["type"].fillna("").str.startswith(prefix).to_numpy()
        return np.flatnonzero(m)


@torch.no_grad()
def simulate(brain, stim_groups, rates, bin_ms=1.0, p=Params(), seed=0,
             record=None, rec_ms=10.0, frame_ms=None, frame_cols=(0,), silence=None):
    """
    stim_groups: list of G index arrays (neurons driven by input channel g)
    rates:       float array/tensor [B, T_bins, G], Poisson rate in Hz per channel over time
    record:      dict name -> index array; returns mean rate (Hz) per group every rec_ms
    frame_ms:    if set, also return per-neuron spike counts of batch columns `frame_cols` per frame

    Returns dict(counts [n, B] int32, groups {name: [B, n_rec] Hz}, frames [n_frames, n, len(frame_cols)] uint8)
    """
    dev, n = brain.device, brain.n
    rates = torch.as_tensor(rates, dtype=torch.float32, device=dev)
    B, T_bins, G = rates.shape
    steps = int(T_bins * bin_ms / p.dt)
    bin_steps = int(round(bin_ms / p.dt))
    dly, rfc = int(round(p.t_dly / p.dt)), int(round(p.t_rfc / p.dt))
    decay_g, k_v = float(np.exp(-p.dt / p.tau)), p.dt / p.t_mbr
    noise_step = p.v_noise * np.sqrt(2 * p.dt / p.t_mbr)  # OU increment giving std v_noise
    gen = torch.Generator(device=dev).manual_seed(seed)

    stim_idx = torch.as_tensor(np.concatenate(stim_groups), dtype=torch.long, device=dev)
    stim_ch = torch.as_tensor(np.concatenate([np.full(len(s), i) for i, s in enumerate(stim_groups)]), device=dev)
    p_ch = rates * (p.dt / 1000.0)  # [B, T_bins, G] hit probability per step

    v = torch.full((n, B), p.v_0, device=dev)
    g = torch.zeros((n, B), device=dev)
    refr = torch.zeros((n, B), dtype=torch.int16, device=dev)
    counts = torch.zeros((n, B), dtype=torch.int32, device=dev)
    ring = torch.zeros((dly, n, B), device=dev)
    alive = None
    if silence is not None and len(silence):
        alive = torch.ones((n, 1), dtype=torch.bool, device=dev)
        alive[torch.as_tensor(np.asarray(silence), device=dev)] = False

    rec_names = list(record or {})
    rec_steps = int(round(rec_ms / p.dt))
    if rec_names:
        rows = np.concatenate([np.full(len(record[k]), i) for i, k in enumerate(rec_names)])
        cols = np.concatenate([record[k] for k in rec_names])
        vals = np.concatenate([np.full(len(record[k]), 1.0 / len(record[k])) for k in rec_names])
        M = torch.sparse_coo_tensor(torch.as_tensor(np.stack([rows, cols]), device=dev),
                                    torch.as_tensor(vals, dtype=torch.float32, device=dev),
                                    (len(rec_names), n)).coalesce().to_sparse_csr()
        rec_acc = torch.zeros((len(rec_names), B), device=dev)
        rec_out = []
    frame_steps = int(round(frame_ms / p.dt)) if frame_ms else 0
    if frame_steps:
        fcols = torch.as_tensor(list(frame_cols), device=dev)
        frame_acc = torch.zeros((n, len(frame_cols)), dtype=torch.int16, device=dev)
        frames = []

    kick = torch.tensor(p.poi_kick, device=dev)
    for t in range(steps):
        slot = t % dly
        g += ring[slot]
        hit = torch.rand(B, len(stim_idx), generator=gen, device=dev) < p_ch[:, t // bin_steps, stim_ch]
        g.index_add_(0, stim_idx, hit.T.float() * kick)

        active = refr == 0
        dv = k_v * (p.v_0 - v + g)
        if noise_step:
            dv += noise_step * torch.randn(n, B, generator=gen, device=dev)
        v.add_(active * dv)
        g.mul_(decay_g)
        refr.sub_(1).clamp_(min=0)

        spk = v >= p.v_th
        if alive is not None:
            spk &= alive
        v.masked_fill_(spk, p.v_rst)
        refr.masked_fill_(spk, rfc)
        counts += spk
        s = spk.float()
        ring[slot] = torch.sparse.mm(brain.W, s).mul_(p.w_syn)

        if rec_names:
            rec_acc += torch.sparse.mm(M, s)
            if (t + 1) % rec_steps == 0:
                rec_out.append(rec_acc * (1000.0 / rec_ms))
                rec_acc = torch.zeros_like(rec_acc)
        if frame_steps:
            frame_acc += spk[:, fcols]
            if (t + 1) % frame_steps == 0:
                frames.append(frame_acc.clamp(max=255).to(torch.uint8).cpu())
                frame_acc.zero_()

    out = {"counts": counts.cpu().numpy(), "t_ms": steps * p.dt}
    if rec_names:
        r = torch.stack(rec_out, 2).cpu().numpy()  # [G, B, T]
        out["groups"] = {k: r[i] for i, k in enumerate(rec_names)}
    if frame_steps:
        out["frames"] = torch.stack(frames).numpy()
    return out


def rates_hz(out):
    return out["counts"] / (out["t_ms"] / 1000.0)
