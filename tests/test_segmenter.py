import numpy as np

from pinganillo.audio.segmenter import PauseSegmenter

LOUD, QUIET = 0.1, 0.0


def feed(segmenter, levels):
    chunks = []
    for level in levels:
        chunk = segmenter.push(np.full((10, 1), level, np.float32), level)
        if chunk is not None:
            chunks.append(len(chunk) // 10)
    return chunks


def test_cuts_at_first_pause_after_minimum_length():
    # 8 loud blocks then 2 quiet ones: the pause completes at block 10.
    assert feed(PauseSegmenter(), [LOUD] * 8 + [QUIET] * 2) == [10]


def test_does_not_cut_on_pause_before_minimum_length():
    assert feed(PauseSegmenter(), [LOUD] * 3 + [QUIET] * 2) == []


def test_caps_chunk_length_when_nobody_pauses():
    assert feed(PauseSegmenter(), [LOUD] * 50) == [24, 24]


def test_flush_returns_tail_and_resets():
    seg = PauseSegmenter()
    feed(seg, [LOUD] * 5)
    assert len(seg.flush()) == 50
    assert seg.flush() is None
    assert seg.buffered_blocks == 0
