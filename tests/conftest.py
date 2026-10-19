"""Shared fakes. No test touches real audio hardware, Whisper weights or the network."""

from __future__ import annotations

import time

import numpy as np
import pytest


class FakeRecorder:
    """Plays a scripted list of blocks, then asks the session to stop."""

    def __init__(self, blocks, session_ref):
        self.blocks = list(blocks)
        self.session_ref = session_ref

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return None

    def record(self, numframes):
        if self.blocks:
            return self.blocks.pop(0)
        session = self.session_ref.get("session")
        if session is None:  # the test has not attached the session yet: keep "playing" silence
            time.sleep(0.01)
        else:
            session.stop.set()
        return np.zeros((numframes, 2), np.float32)


class FakeDevice:
    def __init__(self, blocks):
        self.blocks = blocks
        self.ref = {}
        self.name = "fake"
        self.isloopback = True

    def recorder(self, samplerate):
        return FakeRecorder(self.blocks, self.ref)


@pytest.fixture
def speech_block():
    def make(seconds=0.5, level=0.1, channels=2):
        frames = int(48_000 * seconds)
        t = np.arange(frames) / 48_000
        wave = (np.sin(2 * np.pi * 220 * t) * level * np.sqrt(2)).astype(np.float32)
        return np.repeat(wave[:, None], channels, axis=1)

    return make
