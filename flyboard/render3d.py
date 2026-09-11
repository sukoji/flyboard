"""Tiny software 3D renderer on top of matplotlib: a perspective camera and a glowing brain point cloud.

Coordinates: X right, Y up, Z toward the viewer at yaw = 0.
"""
import numpy as np


class Camera:
    def __init__(self, yaw=0.0, pitch=0.0, dist=4.0, fov=35.0, target=(0, 0, 0)):
        self.yaw, self.pitch, self.dist, self.fov = yaw, pitch, dist, fov
        self.target = np.asarray(target, float)

    def view(self, p):
        """World points [N,3] -> camera coords [N,3] (x right, y up, z = depth away from camera)."""
        p = np.asarray(p, float) - self.target
        cy, sy = np.cos(np.radians(self.yaw)), np.sin(np.radians(self.yaw))
        cp, sp = np.cos(np.radians(self.pitch)), np.sin(np.radians(self.pitch))
        x = cy * p[..., 0] + sy * p[..., 2]
        z = -sy * p[..., 0] + cy * p[..., 2]
        y = cp * p[..., 1] - sp * z
        z = sp * p[..., 1] + cp * z
        return np.stack([x, y, self.dist - z], -1)

    def project(self, p):
        """-> screen xy [N,2] (units of focal length) and depth [N]."""
        v = self.view(p)
        f = 1.0 / np.tan(np.radians(self.fov) / 2)
        d = np.maximum(v[..., 2], 1e-3)
        return np.stack([f * v[..., 0] / d, f * v[..., 1] / d], -1), d


def brain_coords(neurons):
    """Soma positions (um) -> centred, unit-scaled world coords oriented like the fly puppet:
    +X anterior (brain; EM z is small there), Y up (EM y points ventral), Z across the body (EM x).
    The nerve cord therefore trails behind and below the brain, as inside a real fly."""
    xyz = neurons[["x", "y", "z"]].to_numpy(float)
    ok = ~np.isnan(xyz).any(1)
    lo, hi = np.percentile(xyz[ok], 0.5, 0), np.percentile(xyz[ok], 99.5, 0)
    c = (lo + hi) / 2
    w = np.stack([-(xyz[:, 2] - c[2]), -(xyz[:, 1] - c[1]), xyz[:, 0] - c[0]], 1)
    return w / ((hi - lo).max() / 2), ok


def draw_brain(ax, cam, P, ok, glow, color, bg_idx, spark=None):
    """P world coords, glow [n] trail intensity (>=0), spark [n] bool spiking now, bg_idx subsample for the dust."""
    xy, d = cam.project(P[bg_idx])
    shade = np.clip(1.0 - 0.45 * (d - cam.dist), 0.25, 1.0)  # nearer dust is brighter
    ax.scatter(xy[:, 0], xy[:, 1], s=0.9 * shade + 0.15, c=np.c_[shade * 0.62, shade * 0.66, shade * 0.8].clip(0, 1),
               alpha=0.55, lw=0, zorder=1)
    on = ok & (glow > 0.25)
    if on.any():
        xy, d = cam.project(P[on])
        g = np.minimum(glow[on], 5)
        order = np.argsort(-d)
        ax.scatter(xy[order, 0], xy[order, 1], s=(30 + 45 * g[order]) / d[order], color=color, alpha=0.18, lw=0, zorder=2)
        ax.scatter(xy[order, 0], xy[order, 1], s=(5 + 6 * g[order]) / d[order], color=color, alpha=0.85, lw=0, zorder=3)
    if spark is not None:
        on = ok & spark
        if on.any():
            xy, d = cam.project(P[on])
            ax.scatter(xy[:, 0], xy[:, 1], s=14 / d, color="white", alpha=0.95, lw=0, zorder=4)
