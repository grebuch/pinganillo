"""One entry point to enumerate capture devices, whatever the backend.

Every device object exposes ``name``, ``isloopback`` and
``recorder(samplerate=...)`` returning a context manager with
``record(numframes) -> float32 array (frames, channels)``.
"""

from __future__ import annotations

import os
from typing import Any

ENGINES = ("wasapi", "soundcard")


def default_engine() -> str:
    return "wasapi" if os.name == "nt" else "soundcard"


def list_devices(engine: str) -> tuple[list[Any], int]:
    """Return ``(devices, index_of_default)`` for the chosen engine."""
    if engine == "wasapi":
        from .wasapi import list_devices as wasapi_devices

        devices = wasapi_devices()
        index = next((i for i, d in enumerate(devices) if d.default), 0)
        return devices, index
    if engine == "soundcard":
        import soundcard as sc

        devices = sc.all_microphones(include_loopback=True)
        speaker = sc.default_speaker()
        index = next(
            (i for i, d in enumerate(devices) if d.isloopback and speaker and d.id == speaker.id),
            0,
        )
        return devices, index
    raise ValueError(f"Unknown capture engine: {engine}")
