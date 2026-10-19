"""On-device transcription with faster-whisper (CTranslate2, int8 on CPU)."""

from __future__ import annotations

import os
from typing import Any, Protocol

import numpy as np

from ..audio.dsp import CAPTURE_RATE, for_whisper


class Transcriber(Protocol):
    def transcribe(self, samples: np.ndarray, prompt: str = "") -> str: ...


def default_cpu_threads() -> int:
    """Leave at least one core for capture, the UI and the network."""
    return max(1, min(4, (os.cpu_count() or 2) - 1))


class LocalTranscriber:
    """Lazy-loads a Whisper model the first time it is needed.

    The first load downloads the weights from Hugging Face; afterwards the
    model runs fully offline. Audio never leaves the computer.
    """

    def __init__(self, model_name: str = "small", language: str | None = "es") -> None:
        self.model_name = model_name
        self.language = language
        self.model: Any = None

    def prepare(self) -> None:
        if self.model is None:
            from faster_whisper import WhisperModel

            self.model = WhisperModel(
                self.model_name,
                device="cpu",
                compute_type="int8",
                cpu_threads=default_cpu_threads(),
                num_workers=1,
            )

    def transcribe(self, samples: np.ndarray, prompt: str = "", rate: int = CAPTURE_RATE) -> str:
        self.prepare()
        segments, _ = self.model.transcribe(
            for_whisper(samples, rate),
            language=self.language,
            initial_prompt=prompt or None,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 600},
            beam_size=5,
            temperature=0,
            # Feeding previous text back tends to propagate recognition errors.
            condition_on_previous_text=False,
        )
        return " ".join(s.text.strip() for s in segments).strip()
