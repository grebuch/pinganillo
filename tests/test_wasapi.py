import sys
from types import SimpleNamespace

import numpy as np
import pytest

from escuchator.audio.wasapi import WasapiDevice


def fake_pyaudio(observed, audio_frames, channels=2, rate=44_100):
    class Stream:
        def stop_stream(self):
            observed["stopped"] = True

        def close(self):
            observed["closed"] = True

        def is_active(self):
            return observed.get("active", True)

    class PyAudio:
        def open(self, **kwargs):
            observed.update(kwargs)
            if audio_frames:
                pcm = (np.ones((audio_frames, channels)) * 1000).astype("<i2").tobytes()
                kwargs["stream_callback"](pcm, audio_frames, None, 0)
            return Stream()

        def terminate(self):
            observed["terminated"] = True

    return SimpleNamespace(PyAudio=PyAudio, paInt16=8, paContinue=0)


def device(rate=44_100):
    return WasapiDevice(
        {
            "index": 4,
            "name": "Speakers",
            "maxInputChannels": 2,
            "defaultSampleRate": rate,
            "isLoopbackDevice": True,
        }
    )


def test_native_rate_is_resampled_to_48k(monkeypatch):
    observed = {}
    monkeypatch.setitem(sys.modules, "pyaudiowpatch", fake_pyaudio(observed, 22_050))
    with device().recorder(48_000) as recorder:
        block = recorder.record(24_000)
    assert block.shape == (24_000, 2)
    assert block.dtype == np.float32
    assert observed["rate"] == 44_100
    assert observed["terminated"] and observed["closed"]


def test_silent_loopback_is_padded_instead_of_failing(monkeypatch):
    """WASAPI loopback sends no packets while nothing plays; that is silence, not an error."""
    observed = {}
    monkeypatch.setitem(sys.modules, "pyaudiowpatch", fake_pyaudio(observed, 0))
    with device(48_000).recorder(48_000) as recorder:
        recorder.silence_grace = 0.1  # keep the test fast
        block = recorder.record(24_000)
    assert block.shape == (24_000, 2)
    assert not block.any()
    assert recorder.silence_padded_frames == 24_000


def test_partial_block_is_completed_with_silence(monkeypatch):
    observed = {}
    monkeypatch.setitem(sys.modules, "pyaudiowpatch", fake_pyaudio(observed, 12_000, rate=48_000))
    with device(48_000).recorder(48_000) as recorder:
        recorder.silence_grace = 0.1
        block = recorder.record(24_000)
    assert block[:12_000].any() and not block[12_000:].any()
    assert recorder.silence_padded_frames == 12_000


def test_stopped_device_is_still_an_error(monkeypatch):
    observed = {"active": False}
    monkeypatch.setitem(sys.modules, "pyaudiowpatch", fake_pyaudio(observed, 0))
    with device().recorder(48_000) as recorder, pytest.raises(RuntimeError, match="stopped"):
        recorder.record(24_000)
