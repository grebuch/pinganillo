"""Command-line self test: no account, no API, nothing saved but a short report.

Run with ``pinganillo --diagnose`` while a video with speech is playing.
"""

from __future__ import annotations

import importlib.metadata
import platform
import sys
import time
from pathlib import Path

PACKAGES = ["numpy", "scipy", "PyAudioWPatch", "SoundCard", "faster-whisper", "ctranslate2", "openai"]


def package_versions() -> dict[str, str]:
    versions = {}
    for name in PACKAGES:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = "not installed"
    return versions


def run(engine: str | None = None, seconds: int = 8, report: Path | None = None) -> int:
    from . import __version__
    from .audio.devices import default_engine, list_devices
    from .audio.dsp import CAPTURE_RATE, rms, to_mono

    lines: list[str] = []

    def log(message: object) -> None:
        print(message, flush=True)
        lines.append(str(message))

    log(f"PINGANILLO {__version__} · local self-test (no account, no API)")
    log("Nothing is recorded to disk. Keep a video with speech playing during the test.")
    log(f"System: {platform.system()} {platform.release()} · Python {sys.version.split()[0]}")
    for name, version in package_versions().items():
        log(f"{name}: {version}")
    step, status = "devices", 1
    try:
        import numpy as np

        devices, default = list_devices(engine or default_engine())
        if not devices:
            raise RuntimeError("No capture devices available")
        for i, d in enumerate(devices):
            log(f"{i}: {'PC ' if d.isloopback else 'MIC'} · {d.name}{'  (default)' if i == default else ''}")
        choice = input(f"Number of the output you are listening to [{default}]: ").strip()
        device = devices[int(choice) if choice else default]
        log(f"Selected: {device.name}")

        step = "capture"
        blocks = []
        log(f"Capturing {seconds} seconds…")
        with device.recorder(samplerate=CAPTURE_RATE) as recorder:
            for i in range(seconds * 2):
                block = recorder.record(numframes=CAPTURE_RATE // 2)
                blocks.append(block)
                log(f"Audio {i + 1}/{seconds * 2} · RMS {rms(block):.6f}")
        samples = np.concatenate(blocks)
        level = rms(to_mono(samples))
        log(f"Capture finished · mono RMS {level:.6f}")
        if level < 1e-5:
            raise RuntimeError("Capture is practically silent. Pick the exact output your call uses.")

        step = "local model"
        from .stt.whisper_local import LocalTranscriber

        log("Loading Whisper; the first run downloads the model from Hugging Face.")
        transcriber = LocalTranscriber("base")
        started = time.monotonic()
        transcriber.prepare()
        log(f"Model ready in {time.monotonic() - started:.1f} s")

        step = "transcription"
        started = time.monotonic()
        text = transcriber.transcribe(samples)
        log(
            f"Transcribed {seconds} s of audio in {time.monotonic() - started:.1f} s · {len(text)} characters"
        )
        log(
            "RESULT: audio and transcription work." if text else "RESULT: audio OK, but no speech recognised."
        )
        status = 0
    except Exception as exc:
        log(f"FAILED AT: {step}")
        log(f"{type(exc).__name__}: {exc}")
    finally:
        path = report or Path.cwd() / "pinganillo-diagnostics.txt"
        path.write_text("\n".join(lines), encoding="utf-8")
        print(f"Report saved to {path} (versions, device names and errors; no audio, no text).")
    return status
