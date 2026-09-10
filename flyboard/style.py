"""Shared look for FLYBOARD figures."""
from pathlib import Path

import matplotlib
from matplotlib import font_manager as fm
from matplotlib.patches import Ellipse, Circle

# Optional nicer fonts (Pretendard / Noto Sans JP/KR); falls back to Windows system fonts.
FONT_DIRS = [Path(__file__).resolve().parent.parent / "assets" / "fonts", Path("D:/ditto/song/fonts")]
for d in FONT_DIRS:
    if d.exists():
        for f in list(d.glob("*.ttf")) + list(d.glob("*.otf")):
            fm.fontManager.addfont(str(f))

_have = {f.name for f in fm.fontManager.ttflist}
TEXT = [f for f in ["Pretendard", "Noto Sans JP", "Yu Gothic", "Malgun Gothic", "DejaVu Sans"] if f in _have]
DISPLAY = [f for f in ["Impact", "Franklin Gothic Heavy"] if f in _have] + TEXT
matplotlib.rcParams["font.family"] = TEXT
matplotlib.rcParams["axes.unicode_minus"] = False

BG = "#0b0d14"
PANEL = "#151926"
INK = "#f2f2f2"
MUTED = "#8a90a3"
CHARTS = {
    "global": dict(name="HOT 30", sub="Songs of the Century", color="#f5c542"),
    "japan": dict(name="JAPAN", sub="J-POP", color="#ff4d6d"),
    "korea": dict(name="KOREA", sub="K-POP", color="#4dabff"),
    "control": dict(name="CONTROL", sub="", color="#9aa0a6"),
}


def fly_icon(ax, x, y, s=1.0, color=INK, wing="#9ecbff", z=5):
    """Tiny vector fruit fly (top view), size s in axes data units."""
    for dx, ang in ((-0.28, 25), (0.28, -25)):
        ax.add_patch(Ellipse((x + dx * s, y + 0.1 * s), 0.55 * s, 0.9 * s, angle=ang, fc=wing, ec="none", alpha=0.55, zorder=z))
    ax.add_patch(Ellipse((x, y - 0.05 * s), 0.34 * s, 0.8 * s, fc=color, ec="none", zorder=z + 1))
    ax.add_patch(Circle((x, y + 0.45 * s), 0.16 * s, fc=color, ec="none", zorder=z + 1))
    for dx in (-0.08, 0.08):
        ax.add_patch(Circle((x + dx * s, y + 0.5 * s), 0.06 * s, fc="#d7263d", ec="none", zorder=z + 2))
