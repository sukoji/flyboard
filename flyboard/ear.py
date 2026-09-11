"""Turn audio into Johnston's-organ (JO) input rates: what the fly's antenna 'hears'.

Assumptions (simple, stated in the README):
- The antenna only cares about < ~1 kHz. Audio is resampled to 8 kHz and loudness-normalized
  inside the fly's hearing band, so every song is played "at the same volume".
- JO-B neurons carry low-frequency vibration (80-300 Hz, where fly courtship song lives),
  JO-A neurons higher frequencies (300-1200 Hz) [Kamikouchi et al. 2009, Nature].
- JO neurons adapt: drive = fast envelope minus a fraction of a slow envelope, so onsets and
  rhythm matter more than a sustained drone.
- Rates are scaled so that the peaks of real Drosophila pulse song reach ~R_MAX.
"""
import subprocess

import numpy as np
from scipy import signal

SR = 8000
R_MAX = 300.0            # Hz; JO neurons follow vibration at a few hundred Hz. At 150 Hz (Shiu's
                         # stimulus rate) almost nothing gets past the first auditory relay.
BANDS = {"JO-B": (80, 300), "JO-A": (300, 1200)}
TAU_FAST, TAU_SLOW, ADAPT = 0.010, 0.300, 0.6   # s, s, fraction subtracted
ADAPT_DEFAULT = ADAPT
TARGET_RMS = 0.1


def load_audio(path, seconds=30.0, offset=0.0):
    cmd = ["ffmpeg", "-v", "quiet", "-ss", str(offset), "-t", str(seconds), "-i", str(path),
           "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"]
    x = np.frombuffer(subprocess.run(cmd, capture_output=True, check=True).stdout, dtype=np.float32)
    return x.astype(np.float64)


def _smooth(x, tau):
    a = np.exp(-1.0 / (tau * SR))
    return signal.lfilter([1 - a], [1, -a], x)


def normalize(x):
    sos = signal.butter(4, (80, 1200), "bandpass", fs=SR, output="sos")
    band = signal.sosfiltfilt(sos, x)
    return x / (np.sqrt(np.mean(band ** 2)) + 1e-12) * TARGET_RMS


def drive(x):
    """Per-band adapted envelope at 1 ms resolution, unscaled. Returns [T_ms, n_bands]."""
    x = normalize(x)
    out = []
    for lo, hi in BANDS.values():
        sos = signal.butter(4, (lo, hi), "bandpass", fs=SR, output="sos")
        env = np.abs(signal.sosfiltfilt(sos, x))
        d = np.maximum(_smooth(env, TAU_FAST) - ADAPT * _smooth(env, TAU_SLOW), 0.0)
        out.append(d[:: SR // 1000])
    return np.stack(out, 1)


def to_rates(d, ref):
    """ref: per-band drive level that maps to R_MAX (from fly courtship song)."""
    return R_MAX * np.clip(d / ref, 0.0, 1.0)


def rates_for(x, ref, seconds):
    """Fixed-length [T_ms, n_bands] JO rates (zero-padded if the clip is short)."""
    T = int(seconds * 1000)
    d = to_rates(drive(x), ref)[:T]
    out = np.zeros((T, d.shape[1]), np.float32)
    out[: len(d)] = d
    return out


def fly_song(seconds=30.0, ipi=0.035, pulse_hz=250.0, sine_hz=150.0, seed=0):
    """Synthetic D. melanogaster courtship song: pulse-song trains (IPI ~35 ms, ~250 Hz carrier)
    alternating with sine song (~150 Hz) [Bennet-Clark & Ewing 1969; Clemens et al. 2018]."""
    rng = np.random.default_rng(seed)
    t_total = int(seconds * SR)
    x = np.zeros(t_total)
    t = 0
    while t < t_total:
        n_pulses = rng.integers(15, 40)
        for _ in range(n_pulses):
            x[t: t + len(PULSE)] += PULSE[: max(0, min(len(PULSE), t_total - t))]
            t += int(ipi * SR * rng.normal(1.0, 0.03))
            if t >= t_total:
                break
        t += int(rng.uniform(0.05, 0.2) * SR)
        n_sine = int(rng.uniform(0.3, 0.8) * SR)
        seg = np.arange(min(n_sine, max(0, t_total - t)))
        x[t: t + len(seg)] += 0.4 * np.sin(2 * np.pi * sine_hz * seg / SR) * np.hanning(len(seg))
        t += n_sine + int(rng.uniform(0.2, 0.6) * SR)
    return x


def buzz(seconds=30.0, f0=220.0, seed=0, approach=False):
    """Wingbeat buzz: a harmonic tone at the wingbeat frequency with slow loudness swells.
    f0 ~220 Hz = another Drosophila flying past (wingbeat ~200-230 Hz); f0 ~130 Hz = a wasp-like
    predator. approach=True makes each swell a crescendo that stops at its loudest (something coming at you)."""
    rng = np.random.default_rng(seed)
    n = int(seconds * SR)
    t = np.arange(n) / SR
    f = f0 * (1 + 0.02 * np.sin(2 * np.pi * 0.3 * t + rng.uniform(0, 6)))
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = sum(a * np.sin(k * ph) for k, a in [(1, 1.0), (2, 0.5), (3, 0.25), (4, 0.12)])
    env, pos = np.zeros(n), 0
    while pos < n:
        dur, gap = int(rng.uniform(1.0, 3.0) * SR), int(rng.uniform(0.3, 1.5) * SR)
        seg = np.arange(min(dur, n - pos)) / max(1, dur)
        env[pos: pos + len(seg)] = seg ** 2 if approach else np.sin(np.pi * seg) ** 2
        pos += dur + gap
    return x * env


def pulse_train(ipi, seconds=30.0, pulse_hz=250.0):
    """Pulse-only song with a fixed inter-pulse interval (for the tuning curve)."""
    x = np.zeros(int(seconds * SR))
    for t in range(0, len(x) - len(PULSE), int(ipi * SR)):
        x[t: t + len(PULSE)] += PULSE
    return x


def _pulse(hz=250.0, cycles=2.0):
    n = int(cycles / hz * SR * 2)
    t = (np.arange(n) - n / 2) / SR
    return np.sin(2 * np.pi * hz * t) * np.exp(-0.5 * (t * hz / (cycles / 2)) ** 2)


PULSE = _pulse()
