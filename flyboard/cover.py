"""Album covers painted by the fly's brain.

Every dot is a real neuron at its real soma position (top view of the whole CNS). Brightness is how
hard it fired while listening; colour is how much *more* it fired for this song than for the
average song, so each song gets its own fingerprint. No copyrighted artwork involved.
"""
import colorsys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap, to_rgb

from .style import BG


def palette(base_hex, shift):
    """Two-tone palette around a chart colour; `shift` (0..1) rotates the hue per song."""
    h, l, s = colorsys.rgb_to_hls(*to_rgb(base_hex))
    a = colorsys.hls_to_rgb((h + 0.18 * (shift - 0.5)) % 1, 0.62, min(1, s * 1.1))
    b = colorsys.hls_to_rgb((h + 0.5 + 0.25 * shift) % 1, 0.7, 0.85)
    return LinearSegmentedColormap.from_list("c", [(0.25, 0.3, 0.45), a, (1, 1, 1), b])


def render(path, xy, hz, mean_log, base_hex, shift, size_px=720, density=None, extent=None, ring=None):
    """xy [n,2] soma positions (NaN allowed), hz [n] firing rates, mean_log [n] mean log1p rate over songs.
    ring: optional [T, 2] ear input (JO-B, JO-A) over the song, drawn as a circular waveform."""
    ok = ~np.isnan(xy).any(1)
    lg = np.log1p(hz[ok])
    fp = lg - mean_log[ok]                     # fingerprint: above/below the average song
    on = lg > 0.3
    pts, lg, fp = xy[ok][on], lg[on], fp[on]
    order = np.argsort(lg)
    pts, lg, fp = pts[order], lg[order], fp[order]
    col = palette(base_hex, shift)(np.clip(0.5 + fp / 1.2, 0, 1))

    dpi = 100
    fig = plt.figure(figsize=(size_px / dpi, size_px / dpi), dpi=dpi, facecolor=BG)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor(BG)
    x0, x1, y0, y1 = extent
    cx, cy, half = (x0 + x1) / 2, (y0 + y1) / 2, max(x1 - x0, y1 - y0) / 2 * 1.04
    g = np.linspace(-1, 1, 256)
    rad = np.sqrt(g[None] ** 2 + g[:, None] ** 2)
    glow = LinearSegmentedColormap.from_list("g", [to_rgb(base_hex), BG])(np.clip(rad / 1.25, 0, 1))
    glow[..., :3] = glow[..., :3] * 0.35 + np.array(to_rgb(BG)) * 0.65
    ax.imshow(glow, extent=(cx - half, cx + half, cy + half, cy - half), zorder=0)
    if density is not None:
        ax.imshow(density, extent=(x0, x1, y1, y0), cmap=LinearSegmentedColormap.from_list("d", ["#00000000", "#ffffff"]),
                  alpha=0.10, zorder=1)
    w = lg / (lg.max() + 1e-9)
    hot = np.clip(fp / 1.2, 0, 1)                # neurons this song drives more than others get bigger
    ax.scatter(pts[:, 0], pts[:, 1], s=260 * w ** 2 + 20 + 200 * hot, c=col, alpha=0.05, lw=0, zorder=2)
    ax.scatter(pts[:, 0], pts[:, 1], s=40 * w + 4 + 30 * hot, c=col, alpha=0.4, lw=0, zorder=3)
    ax.scatter(pts[:, 0], pts[:, 1], s=6 * w + 0.6, c="white", alpha=0.9, lw=0, zorder=4)
    if ring is not None:
        half *= 1.18
        r0, amp = 0.80 * half, 0.15 * half
        k = len(ring)
        th = np.linspace(-np.pi / 2, 1.5 * np.pi, k, endpoint=False)
        a = palette(base_hex, shift)
        for j, (c, sgn) in enumerate([(a(0.3), -1), (a(0.95), 1)]):
            v = ring[:, j] / (ring.max() + 1e-9)
            r = r0 + sgn * amp * v
            ax.fill(np.r_[cx + r0 * np.cos(th), (cx + r * np.cos(th))[::-1]],
                    np.r_[cy + r0 * np.sin(th), (cy + r * np.sin(th))[::-1]], color=c, alpha=0.55, lw=0, zorder=5)
        ax.add_patch(plt.Circle((cx, cy), r0, fill=False, ec=(1, 1, 1, 0.25), lw=0.6, zorder=6))
    ax.set_xlim(cx - half, cx + half)
    ax.set_ylim(cy + half, cy - half)
    ax.axis("off")
    fig.savefig(path, dpi=dpi, facecolor=BG)
    plt.close(fig)
