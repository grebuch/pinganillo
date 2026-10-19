"""Reproducible speech-to-text benchmark: latency, real-time factor and WER.

    pinganillo-bench meeting.wav --model small --language es --reference meeting.txt

The audio file is cut exactly as the live app would cut it (0.5 s blocks and
the same PauseSegmenter) and each chunk is transcribed with the real model.
The timeline is then replayed as if the audio were arriving live, including
queueing when the model is slower than real time:

* latency  = when a chunk's text is ready - when that chunk's audio ended
* RTF      = processing time / audio time (below 1.0 keeps up with live audio)
* WER      = word error rate against an optional reference transcript

Results can be written as JSON so they can be compared across machines.
"""

from __future__ import annotations

import argparse
import json
import platform
import re
import sys
import time
import unicodedata
import wave
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from .audio.dsp import CAPTURE_RATE, resample, rms, to_mono
from .audio.segmenter import PauseSegmenter
from .pipeline import percentile

BLOCK_SECONDS = 0.5


@dataclass
class ChunkResult:
    start_s: float
    end_s: float
    processing_s: float
    ready_s: float
    latency_s: float
    text: str


@dataclass
class BenchResult:
    audio_seconds: float
    processing_seconds: float
    rtf: float
    latency_p50: float | None
    latency_p95: float | None
    latency_max: float | None
    wer: float | None
    chunks: list[ChunkResult] = field(default_factory=list)
    environment: dict[str, str] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, ensure_ascii=False)


def load_wav(path: Path) -> np.ndarray:
    """Read a 16-bit PCM WAV and return float32 frames at ``CAPTURE_RATE``."""
    with wave.open(str(path), "rb") as wav:
        if wav.getsampwidth() != 2:
            raise ValueError("Only 16-bit PCM WAV is supported (ffmpeg -i in.mp3 -c:a pcm_s16le out.wav).")
        rate, channels = wav.getframerate(), wav.getnchannels()
        pcm = np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2")
    frames = pcm.reshape(-1, channels).astype(np.float32) / 32768.0
    return resample(frames, rate, CAPTURE_RATE)


def segment(samples: np.ndarray, rate: int = CAPTURE_RATE) -> list[tuple[float, float, np.ndarray]]:
    """Cut audio exactly like the live capture loop; returns ``(start_s, end_s, chunk)``."""
    block = int(rate * BLOCK_SECONDS)
    segmenter = PauseSegmenter()
    chunks, start = [], 0.0
    for offset in range(0, len(samples), block):
        piece = samples[offset : offset + block]
        chunk = segmenter.push(piece, rms(to_mono(piece)))
        if chunk is not None:
            end = (offset + len(piece)) / rate
            chunks.append((start, end, chunk))
            start = end
    tail = segmenter.flush()
    if tail is not None:
        chunks.append((start, len(samples) / rate, tail))
    return chunks


def replay(
    chunks: list[tuple[float, float, np.ndarray]],
    transcribe: Callable[[np.ndarray], str],
    timer: Callable[[], float] = time.perf_counter,
) -> list[ChunkResult]:
    """Transcribe every chunk and place it on a simulated live timeline."""
    results, busy_until = [], 0.0
    for start, end, chunk in chunks:
        t0 = timer()
        text = transcribe(chunk)
        processing = timer() - t0
        ready = max(end, busy_until) + processing  # a slow model makes later chunks wait
        busy_until = ready
        results.append(ChunkResult(start, end, processing, ready, ready - end, text))
    return results


def _words(text: str) -> list[str]:
    text = unicodedata.normalize("NFKC", text.casefold())
    return re.findall(r"\w+", text)


def word_error_rate(reference: str, hypothesis: str) -> float:
    """Levenshtein distance over words divided by the reference length."""
    ref, hyp = _words(reference), _words(hypothesis)
    if not ref:
        return 0.0 if not hyp else 1.0
    previous = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        current = [i]
        for j, h in enumerate(hyp, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (r != h)))
        previous = current
    return previous[-1] / len(ref)


def summarise(chunks: list[ChunkResult], audio_seconds: float, reference: str | None) -> BenchResult:
    processing = sum(c.processing_s for c in chunks)
    latencies = [c.latency_s for c in chunks]
    hypothesis = " ".join(c.text for c in chunks)
    return BenchResult(
        audio_seconds=round(audio_seconds, 2),
        processing_seconds=round(processing, 2),
        rtf=round(processing / audio_seconds, 3) if audio_seconds else 0.0,
        latency_p50=percentile(latencies, 50),
        latency_p95=percentile(latencies, 95),
        latency_max=max(latencies) if latencies else None,
        wer=round(word_error_rate(reference, hypothesis), 3) if reference is not None else None,
        chunks=chunks,
    )


def environment(model: str, threads: int) -> dict[str, str]:
    import os

    return {
        "model": model,
        "cpu_threads": str(threads),
        "cpu": platform.processor() or platform.machine(),
        "cores": str(os.cpu_count()),
        "os": f"{platform.system()} {platform.release()}",
        "python": sys.version.split()[0],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pinganillo-bench", description=__doc__.split("\n\n")[0])
    parser.add_argument("audio", type=Path, help="16-bit PCM WAV file")
    parser.add_argument("--model", default="small", help="Whisper model (base, small, medium, ...)")
    parser.add_argument("--language", default="es", help="spoken language code, or 'auto'")
    parser.add_argument("--reference", type=Path, help="plain-text reference transcript for WER")
    parser.add_argument("--json", type=Path, help="write the full result as JSON")
    args = parser.parse_args(argv)

    from .stt.whisper_local import LocalTranscriber, default_cpu_threads

    samples = load_wav(args.audio)
    audio_seconds = len(samples) / CAPTURE_RATE
    transcriber = LocalTranscriber(args.model, None if args.language == "auto" else args.language)
    print(f"Loading {args.model}…", flush=True)
    transcriber.prepare()
    chunks = segment(samples)
    print(f"{audio_seconds:.1f} s of audio → {len(chunks)} chunks", flush=True)
    results = replay(chunks, lambda chunk: transcriber.transcribe(chunk))
    reference = args.reference.read_text(encoding="utf-8") if args.reference else None
    result = summarise(results, audio_seconds, reference)
    result.environment = environment(args.model, default_cpu_threads())

    print(f"\n{'chunk':>5} {'audio':>13} {'proc':>6} {'latency':>8}  text")
    for i, c in enumerate(result.chunks, 1):
        print(
            f"{i:>5} {c.start_s:6.1f}-{c.end_s:<6.1f} {c.processing_s:6.2f} {c.latency_s:8.2f}  {c.text[:60]}"
        )
    print(f"\nRTF {result.rtf:.2f} · latency p50 {result.latency_p50:.2f} s · p95 {result.latency_p95:.2f} s")
    if result.wer is not None:
        print(f"WER {result.wer:.1%}")
    if args.json:
        args.json.write_text(result.to_json(), encoding="utf-8")
        print(f"Saved {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
