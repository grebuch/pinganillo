"""Windows loopback capture through PyAudioWPatch (WASAPI).

Captures at the device's native rate and resamples to ``CAPTURE_RATE``, which
avoids the format negotiation failures some drivers have with 48 kHz.
"""

from __future__ import annotations

import queue
import time
from typing import Any

import numpy as np

from .dsp import CAPTURE_RATE, resample


class WasapiDevice:
    """A WASAPI input or loopback endpoint as reported by PyAudioWPatch."""

    def __init__(self, info: dict[str, Any], default: bool = False) -> None:
        self.info = info
        self.id = int(info["index"])
        self.name = str(info["name"])
        self.isloopback = bool(info.get("isLoopbackDevice"))
        self.default = default

    def recorder(self, samplerate: int = CAPTURE_RATE) -> WasapiRecorder:
        return WasapiRecorder(self.info, samplerate)


def list_devices() -> list[WasapiDevice]:
    """Loopback endpoints first (what you hear), then WASAPI microphones."""
    import pyaudiowpatch as pa

    with pa.PyAudio() as p:
        try:
            default = int(p.get_default_wasapi_loopback()["index"])
        except (OSError, KeyError):
            default = -1
        result = [WasapiDevice(d, int(d["index"]) == default) for d in p.get_loopback_device_info_generator()]
        wasapi = p.get_host_api_info_by_type(pa.paWASAPI)["index"]
        for i in range(p.get_device_count()):
            d = p.get_device_info_by_index(i)
            if d["hostApi"] == wasapi and d["maxInputChannels"] > 0 and not d.get("isLoopbackDevice"):
                result.append(WasapiDevice(d))
        return result


class WasapiRecorder:
    """Context manager that yields fixed-size float32 blocks at ``target_rate``."""

    def __init__(self, info: dict[str, Any], target_rate: int) -> None:
        self.info, self.target = info, target_rate
        self.rate = int(info["defaultSampleRate"])
        self.channels = int(info["maxInputChannels"])
        self.pending = np.empty((0, self.channels), np.float32)
        self.q: queue.Queue[np.ndarray] = queue.Queue(maxsize=100)
        self.dropped = False
        self.p: Any = None
        self.stream: Any = None

    def __enter__(self) -> WasapiRecorder:
        import pyaudiowpatch as pa

        self.p = pa.PyAudio()

        def callback(data, count, time_info, status):
            if data:
                block = np.frombuffer(data, dtype="<i2").astype(np.float32).reshape(-1, self.channels)
                try:
                    self.q.put_nowait(block / 32768.0)
                except queue.Full:
                    self.dropped = True
            return (None, pa.paContinue)

        try:
            self.stream = self.p.open(
                format=pa.paInt16,
                channels=self.channels,
                rate=self.rate,
                input=True,
                input_device_index=int(self.info["index"]),
                frames_per_buffer=max(128, self.rate // 10),
                stream_callback=callback,
            )
        except Exception:
            self.p.terminate()
            raise
        return self

    def record(self, numframes: int) -> np.ndarray:
        needed = round(numframes * self.rate / self.target)
        deadline = time.monotonic() + 10
        while len(self.pending) < needed:
            if self.dropped:
                raise RuntimeError("Capture buffer overflowed. Close heavy applications and try again.")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError("No samples from this output. Play some audio or pick another device.")
            try:
                block = self.q.get(timeout=min(0.5, remaining))
            except queue.Empty:
                continue
            self.pending = np.concatenate((self.pending, block))
        block, self.pending = self.pending[:needed], self.pending[needed:]
        return resample(block, self.rate, self.target)

    def __exit__(self, *exc: object) -> None:
        try:
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
        finally:
            if self.p:
                self.p.terminate()
