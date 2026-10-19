"""Small signal-processing helpers shared by capture, transcription and benchmarks."""

from __future__ import annotations

from math import gcd

import numpy as np
from scipy.signal import resample_poly

CAPTURE_RATE = 48_000
"""Every capture backend delivers float32 frames at this rate."""

WHISPER_RATE = 16_000
"""faster-whisper expects mono float32 audio at 16 kHz."""


def rms(samples: np.ndarray) -> float:
    """Root-mean-square level of a block (0.0 for empty input)."""
    a = np.asarray(samples, dtype=np.float32)
    if a.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(a * a)))


def to_mono(samples: np.ndarray) -> np.ndarray:
    """Down-mix to mono without letting opposite-phase channels cancel speech.

    Some virtual devices and headsets expose a channel with inverted phase.
    A plain average of ``L`` and ``-L`` is silence, so when the mix is much
    quieter than the loudest channel we keep that channel instead.
    """
    a = np.asarray(samples, dtype=np.float32)
    if a.ndim == 1:
        return a
    if a.ndim != 2 or a.shape[1] == 0:
        raise ValueError("Audio block has no valid channels")
    mixed = a.mean(axis=1)
    levels = np.sqrt(np.mean(a * a, axis=0))
    best = int(np.argmax(levels))
    if rms(mixed) < levels[best] * 0.2:
        return a[:, best].copy()
    return mixed


def resample(block: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
    """Polyphase resampling along the time axis; returns contiguous float32."""
    if src_rate != dst_rate:
        divisor = gcd(src_rate, dst_rate)
        block = resample_poly(block, dst_rate // divisor, src_rate // divisor, axis=0)
    return np.ascontiguousarray(block, dtype=np.float32)


def for_whisper(samples: np.ndarray, rate: int = CAPTURE_RATE) -> np.ndarray:
    """Convert captured frames into the mono 16 kHz float32 array Whisper expects."""
    return resample(to_mono(samples), rate, WHISPER_RATE)
