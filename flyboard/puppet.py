"""A 3D fruit-fly puppet whose body parts are driven by the simulated motor neurons.

Not a physics simulation: each body part moves in proportion to the activity of the motor neurons
that innervate it (MaleCNS `subclass`: fl/ml/hl legs, wm wings, ad abdomen, pm proboscis, nm neck,
hm halteres), plus the giant fiber / TTMn for the escape jump.

Fly coordinates: x forward, y left, z up (1 unit ~ 1 mm body scale). World for the camera: X = x, Y = z, Z = -y.
"""
import numpy as np
from matplotlib.collections import LineCollection, PolyCollection
from matplotlib.colors import to_rgb

from .render3d import Camera

LIGHT = np.array([0.35, 0.85, 0.4]) / np.linalg.norm([0.35, 0.85, 0.4])
GROUND = -0.62
LEGS = [(side, seg) for seg in ("fl", "ml", "hl") for side in ("L", "R")]
ATTACH_X = {"fl": 0.62, "ml": 0.42, "hl": 0.22}
FOOT_DX = {"fl": 0.55, "ml": 0.0, "hl": -0.6}
FOOT_DY = {"fl": 0.85, "ml": 1.0, "hl": 0.92}
TRIPOD = {("L", "fl"): 0, ("R", "ml"): 0, ("L", "hl"): 0, ("R", "fl"): 1, ("L", "ml"): 1, ("R", "hl"): 1}


def to_world(p):
    p = np.asarray(p, float)
    return np.stack([p[..., 0], p[..., 2], -p[..., 1]], -1)


def rot_y(a):  # pitch about the fly's y axis (nose up/down)
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def rot_z(a):  # yaw about the fly's z axis
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def ellipsoid(center, radii, rot=np.eye(3), nu=30, nv=16):
    u = np.linspace(0, 2 * np.pi, nu + 1)
    v = np.linspace(0, np.pi, nv + 1)
    g = np.stack([np.cos(u)[None] * np.sin(v)[:, None], np.sin(u)[None] * np.sin(v)[:, None],
                  np.cos(v)[:, None] * np.ones_like(u)[None]], -1) * np.asarray(radii)
    g = g @ rot.T + np.asarray(center)
    quads = np.stack([g[:-1, :-1], g[:-1, 1:], g[1:, 1:], g[1:, :-1]], 2)  # [nv, nu, 4, 3]
    lat = np.repeat(np.arange(nv)[:, None], nu, 1)
    lon = np.repeat(np.arange(nu)[None], nv, 0)
    return quads.reshape(-1, 4, 3), lat.ravel(), lon.ravel(), np.asarray(center, float)


def wing_outline(L=1.45, W=0.48, n=14):
    s = np.linspace(0, 1, n)
    w = W * np.sin(np.pi * s) ** 0.7
    top = np.stack([s * L, 0.15 * w, np.zeros(n)], 1)
    bot = np.stack([s * L, -w, np.zeros(n)], 1)[::-1]
    return np.vstack([top, bot])


class Fly:
    def __init__(self):
        self.t = 0.0
        self.scroll = 0.0
        self.jump = 0.0

    def pose(self, ch, dt):
        """ch: dict of channel -> 0..1 activity. Returns (polys, colors, lines) in fly coordinates."""
        self.t += dt
        t = self.t
        walk = np.mean([ch.get(f"{s}{g}", 0) for s, g in LEGS])
        self.scroll = (self.scroll + dt * 1.6 * walk) % 1.0
        self.jump += (ch.get("jump", 0) - self.jump) * min(1, dt * 6)
        lift = 0.55 * self.jump
        body_off = np.array([0.0, 0.0, lift])
        polys, cols, lines = [], [], []

        def add_ell(center, radii, color, rot=np.eye(3), stripes=None, pivot=None, prot=None):
            q, lat, lon, c = ellipsoid(center, radii, rot)
            qc = q.mean(1) - c  # quad centres relative to the ellipsoid centre, before posing
            if prot is not None:
                q = (q - pivot) @ prot.T + pivot
                c = (c - pivot) @ prot.T + pivot
            q = q + body_off
            c = c + body_off
            for k in range(len(q)):
                col = color
                if stripes is not None and qc[k, 2] > -0.05:  # dark tergite bands on the back
                    col = stripes[int((qc[k, 0] + 1.0) / 0.2) % len(stripes)]
                polys.append(q[k])
                cols.append((col, c))

        # thorax, head (neck yaw), abdomen (curl + pumping)
        add_ell((0.45, 0, 0.35), (0.52, 0.38, 0.38), "#9a7148")
        yaw = np.radians(22) * (ch.get("neckL", 0) - ch.get("neckR", 0))
        neck = np.array([0.92, 0, 0.38])
        R_head = rot_z(yaw)
        add_ell((1.15, 0, 0.38), (0.26, 0.36, 0.3), "#b8895a", pivot=neck, prot=R_head)
        for sy in (1, -1):
            add_ell((1.2, 0.27 * sy, 0.44), (0.17, 0.13, 0.2), "#d23a2c", pivot=neck, prot=R_head)
        curl = ch.get("abdomen", 0)
        pump = np.radians(35 * curl + 5 * curl * np.sin(2 * np.pi * 3.0 * t))
        add_ell((-0.5, 0, 0.3), (0.64, 0.37, 0.32), "#c9a070", pivot=np.array([-0.02, 0, 0.36]),
                prot=rot_y(pump), stripes=["#3d2716", "#c9a070"])

        # legs: tripod gait, amplitude from each leg's motor neurons
        for side, seg in LEGS:
            sy = 1 if side == "L" else -1
            amp = ch.get(f"{side}{seg}", 0)
            ph = 2 * np.pi * 7.0 * t + np.pi * TRIPOD[(side, seg)]
            A = np.array([ATTACH_X[seg], 0.22 * sy, 0.12]) + body_off
            F = np.array([ATTACH_X[seg] + FOOT_DX[seg] + 0.32 * amp * np.sin(ph), FOOT_DY[seg] * sy,
                          GROUND + 0.16 * amp * max(0.0, np.cos(ph))])
            mid = (A + F) / 2
            K = mid + np.array([0.0, 0.18 * sy, 0.42 - 0.2 * self.jump])
            T = F + np.array([0.12 if seg != "hl" else -0.12, 0.06 * sy, 0.0])
            lines.append((np.stack([A, K, F, T]), "#3a2718", 2.6))

        # proboscis
        pe = ch.get("proboscis", 0)
        base = neck + (np.array([1.28, 0, 0.2]) - neck) @ R_head.T
        tip = base + np.array([0.12 * pe, 0, -0.1 - 0.42 * pe])
        lines.append((np.stack([base, tip]) + body_off, "#6b4a2d", 3.2))
        # antennae vibrate with the ear input
        ear = ch.get("ear", 0)
        for sy in (1, -1):
            b = neck + (np.array([1.38, 0.08 * sy, 0.52]) - neck) @ R_head.T
            jit = 0.06 * ear * np.sin(2 * np.pi * 11 * t + (0 if sy > 0 else 1.3))
            tipa = b + np.array([0.14, 0.1 * sy + jit, 0.16])
            lines.append((np.stack([b, tipa]) + body_off, "#e0c090", 1.6))
        # halteres
        for sy in (1, -1):
            b = np.array([0.1, 0.3 * sy, 0.55])
            k = b + np.array([-0.08, 0.08 * sy, 0.12 + 0.05 * ch.get("haltere", 0) * np.sin(2 * np.pi * 9 * t)])
            lines.append((np.stack([b, k]) + body_off, "#d8c8a0", 2.0))

        # wings: folded over the abdomen at rest, spread and blurred when the wing motor is active
        wings = []
        for side in ("L", "R"):
            sy = 1 if side == "L" else -1
            buzz = ch.get(f"wing{side}", 0)
            spread = np.radians(12 + 58 * buzz)
            base = np.array([0.4, 0.18 * sy, 0.72]) + body_off
            outline = wing_outline()
            outline[:, 1] *= sy
            copies = [0.0] if buzz < 0.05 else [-1, -0.33, 0.33, 1]
            for c in copies:
                elev = np.radians(50 * buzz * c + 6)
                R = rot_z(np.pi - sy * spread) @ np.array([[1, 0, 0], [0, np.cos(elev * sy), -np.sin(elev * sy)],
                                                           [0, np.sin(elev * sy), np.cos(elev * sy)]])
                wings.append((outline @ R.T + base, 0.55 if buzz < 0.05 else 0.16))
        return polys, cols, lines, wings


def draw_fly(ax, cam, fly, ch, dt, ground_color="#1b2233"):
    polys, cols, lines, wings = fly.pose(ch, dt)
    # ground grid scrolling backward as the fly walks
    gx = np.linspace(-3, 3, 13) - (fly.scroll * 0.5) % 0.5
    seg = [[(x, -2.2, GROUND), (x, 2.2, GROUND)] for x in gx] + [[(-3, y, GROUND), (3, y, GROUND)] for y in np.linspace(-2.2, 2.2, 9)]
    seg = [cam.project(to_world(np.array(s)))[0] for s in seg]
    ax.add_collection(LineCollection(seg, colors=ground_color, linewidths=0.8, zorder=0))
    # shadow
    sh = np.stack([0.2 + 1.2 * np.cos(np.linspace(0, 2 * np.pi, 40)), 0.55 * np.sin(np.linspace(0, 2 * np.pi, 40)),
                   np.full(40, GROUND)], 1) * [1 / (1 + fly.jump), 1 / (1 + fly.jump), 1]
    s_xy, _ = cam.project(to_world(sh))
    ax.fill(s_xy[:, 0], s_xy[:, 1], color="black", alpha=0.35 / (1 + 2 * fly.jump), lw=0, zorder=1)

    body_c = cam.project(to_world(np.array([[0.3, 0, 0.3]])))[1][0]
    # body faces: back-face cull, painter's sort, lambert shading
    P = np.array(polys)
    W = to_world(P)
    xy, d = cam.project(W)
    cen = W.mean(1)
    centers = to_world(np.array([c for _, c in cols]))
    nrm = cen - centers
    nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-9
    front = (cam.view(cen + 0.05 * nrm)[:, 2] - cam.view(cen)[:, 2]) < 0  # normal points toward the camera
    lam = np.clip(nrm @ LIGHT, 0, 1) * 0.7 + 0.3
    rgb = np.array([to_rgb(c) for c, _ in cols]) * lam[:, None]
    order = np.argsort(-d.mean(1))
    order = order[front[order]]

    def draw_lines(which, z):
        for pts, col, lw in which:
            p, dd = cam.project(to_world(pts))
            ax.plot(p[:, 0], p[:, 1], color=col, lw=lw * 3.2 / dd.mean(), solid_capstyle="round", zorder=z)

    depth_of = lambda l: cam.project(to_world(l[0]))[1].mean()
    draw_lines([l for l in lines if depth_of(l) > body_c], 3)
    fc = np.clip(rgb[order], 0, 1)
    ax.add_collection(PolyCollection(xy[order], facecolors=fc, edgecolors=fc, linewidths=0.4, zorder=4))
    draw_lines([l for l in lines if depth_of(l) <= body_c], 5)
    for pts, alpha in wings:
        p, _ = cam.project(to_world(pts))
        ax.fill(p[:, 0], p[:, 1], color=(0.78, 0.88, 1.0), alpha=alpha, lw=0.6, ec=(1, 1, 1, alpha), zorder=6)
