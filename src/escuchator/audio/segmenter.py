"""Turns a stream of short capture blocks into utterance-sized chunks.

Whisper works much better on a few seconds of speech than on tiny slices, but
waiting too long adds latency. The segmenter cuts at the first pause after a
minimum length, and never lets a chunk grow beyond a maximum length.

The pause detector is a volume heuristic, not linguistic segmentation: it can
still split a sentence. It is deliberately simple so it is cheap and testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class PauseSegmenter:
    min_blocks: int = 8
    """With 0.5 s blocks, prefer cutting after at least 4 s of audio."""
    max_blocks: int = 24
    """Hard cap: 12 s. Bounds worst-case latency when nobody pauses."""
    quiet_blocks_needed: int = 2
    """Consecutive quiet blocks (about 1 s) that count as a pause."""
    relative_quiet: float = 0.08
    """A block is quiet when its level is below 8 % of the chunk's peak..."""
    absolute_quiet: float = 1e-4
    """...or below this absolute floor, whichever is higher."""

    _parts: list[np.ndarray] = field(default_factory=list, init=False, repr=False)
    _quiet: int = field(default=0, init=False, repr=False)
    _peak: float = field(default=0.0, init=False, repr=False)

    def push(self, block: np.ndarray, level: float) -> np.ndarray | None:
        """Add one block with its pre-computed RMS level; return a chunk when one is ready."""
        self._parts.append(block)
        self._peak = max(self._peak, level)
        threshold = max(self.absolute_quiet, self._peak * self.relative_quiet)
        self._quiet = self._quiet + 1 if level < threshold else 0
        long_enough = len(self._parts) >= self.min_blocks
        if (long_enough and self._quiet >= self.quiet_blocks_needed) or len(self._parts) >= self.max_blocks:
            return self.flush()
        return None

    def flush(self) -> np.ndarray | None:
        """Return whatever is buffered (or None) and reset."""
        if not self._parts:
            return None
        chunk = np.concatenate(self._parts)
        self._parts, self._quiet, self._peak = [], 0, 0.0
        return chunk

    @property
    def buffered_blocks(self) -> int:
        return len(self._parts)
