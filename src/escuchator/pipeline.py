"""The live pipeline: capture -> transcribe -> analyse, one thread each.

Threads talk through queues and never touch the UI. Everything the UI needs
is published as ``(session, kind, value)`` tuples on ``events``; the UI polls
that queue from its own thread. Each stage can fail without stopping the
previous ones: if the AI breaks, capture and transcription keep going.

Shutdown is a sentinel (``None``) that flows down the queues, so pending audio
is still transcribed after the user presses stop.

User-facing messages are emitted as ``(message_key, params)`` so the UI can
translate them; see ``escuchator.i18n``.

Latency is measured, not guessed: each chunk carries the monotonic time at
which its audio ended, and the pipeline records how long it took until its
text (``stt``) and the resulting suggestions (``e2e``) were ready, plus the
pure model time (``ai``).
"""

from __future__ import annotations

import datetime as dt
import json
import queue
import threading
import time
from collections import deque
from typing import Any

import numpy as np

from .audio.dsp import CAPTURE_RATE, rms, to_mono
from .audio.segmenter import PauseSegmenter
from .llm.analyzers import Analyzer, NoAnalyzer
from .llm.knowledge import KnowledgeBase
from .llm.parsing import parse_analysis
from .llm.prompt import instructions

BLOCK_FRAMES = CAPTURE_RATE // 2  # 0.5 s capture blocks
SILENT_CHUNK = 1e-5
RECENT_FRAGMENTS = 6
MIN_FRAGMENT_CHARS = 12
"""Fragments shorter than this ("Yes.", "OK") wait for more speech instead of costing a request."""

Message = tuple[str, dict[str, Any]]


def msg(key: str, **params: Any) -> Message:
    return key, params


def percentile(values: list[float], q: float) -> float | None:
    """Nearest-rank percentile; ``None`` for no data."""
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(q / 100 * len(ordered) + 0.5) - 1))
    return ordered[index]


class Session:
    def __init__(
        self,
        transcriber: Any,
        analyzer: Analyzer,
        device: Any,
        profile: str = "general",
        knowledge: KnowledgeBase | str = "",
        events: queue.Queue | None = None,
        interval: float = 4.0,
        context_budget_chars: int = 2_500,
    ) -> None:
        self.transcriber, self.analyzer, self.device = transcriber, analyzer, device
        self.profile = profile
        self.knowledge = knowledge if isinstance(knowledge, KnowledgeBase) else KnowledgeBase(knowledge)
        self.context_budget_chars = context_budget_chars
        self.events: queue.Queue = events if events is not None else queue.Queue()
        self.interval = interval
        self.stop = threading.Event()
        self.cancel = threading.Event()
        self.audio: queue.Queue[tuple[np.ndarray, float] | np.ndarray | None] = queue.Queue(maxsize=20)
        self.analysis: queue.Queue[tuple[str, list[dict], float] | None] = queue.Queue()
        self.analysis_disabled = False
        self.ai_generation = 0
        self.last_ai_diagnostic: dict[str, Any] = {}
        self.transcript: list[dict[str, str]] = []
        self.summary = ""
        self.concepts: dict[str, dict] = {}
        self.questions: dict[str, dict] = {}
        self._carry = ""
        self._carry_since: float | None = None
        self.threads: list[threading.Thread] = []
        self.last_audio = time.monotonic()
        self.metrics = {
            "audio_blocks": 0,
            "transcript_blocks": 0,
            "analysis_calls": 0,
            "dropped_chunks": 0,
            "payload_chars": 0,
        }
        self.latency: dict[str, deque[float]] = {k: deque(maxlen=500) for k in ("stt", "ai", "e2e")}
        self.errors: list[str] = []

    # -- plumbing ----------------------------------------------------------
    def emit(self, kind: str, value: Any) -> None:
        if kind == "error":
            key, params = value
            self.errors.append(f"{key}: {params.get('detail', '')}".rstrip(": "))
        self.events.put((self, kind, value))

    @property
    def running(self) -> bool:
        return any(t.is_alive() for t in self.threads)

    def start(self) -> None:
        for name, target in (
            ("capture", self.capture),
            ("transcribe", self.transcribe),
            ("analyze", self.analyze),
        ):
            thread = threading.Thread(target=target, daemon=True, name=name)
            self.threads.append(thread)
            thread.start()

    def adopt_context(self, previous: Session) -> None:
        """Continue a paused session: keep transcript, summary and what was already explained."""
        self.transcript = previous.transcript.copy()
        self.summary = previous.summary
        self.concepts = previous.concepts.copy()
        self.questions = previous.questions.copy()
        for key, values in previous.latency.items():
            self.latency[key].extend(values)

    def latency_summary(self) -> dict[str, dict[str, float | int | None]]:
        return {
            key: {"n": len(v), "p50": percentile(list(v), 50), "p95": percentile(list(v), 95)}
            for key, v in self.latency.items()
        }

    # -- stage 1: capture --------------------------------------------------
    def capture(self) -> None:
        segmenter = PauseSegmenter()
        try:
            # Keep all channels: recording a single WASAPI channel has known issues.
            with self.device.recorder(samplerate=CAPTURE_RATE) as recorder:
                while not self.stop.is_set():
                    block = recorder.record(numframes=BLOCK_FRAMES)
                    self.last_audio = time.monotonic()
                    level = rms(to_mono(block))
                    self.emit("audio_level", level)
                    chunk = segmenter.push(block, level)
                    if chunk is not None:
                        self.enqueue(chunk)
                tail = segmenter.flush()
                if tail is not None:
                    self.enqueue(tail)
        except Exception as exc:
            self.stop.set()
            self.emit("error", msg("error.capture", detail=str(exc)))
        finally:
            self.audio.put(None)

    def enqueue(self, chunk: np.ndarray) -> None:
        self.metrics["audio_blocks"] += 1
        if rms(to_mono(chunk)) < SILENT_CHUNK:
            return
        try:
            self.audio.put_nowait((chunk, time.monotonic()))
        except queue.Full:
            self.metrics["dropped_chunks"] += 1
            self.emit("error", msg("error.falling_behind"))

    # -- stage 2: transcription -------------------------------------------
    def transcribe(self) -> None:
        if hasattr(self.transcriber, "prepare"):
            self.emit("stage", msg("stage.loading_whisper"))
            try:
                self.transcriber.prepare()
                self.emit("stage", msg("stage.whisper_ready"))
            except Exception as exc:
                self.emit("error", msg("error.whisper_load", detail=str(exc)))
                self.stop.set()
                while self.audio.get() is not None:
                    pass  # drain so capture can shut down cleanly
                self.analysis.put(None)
                return
        while True:
            item = self.audio.get()
            if item is None:
                self.analysis.put(None)
                return
            samples, captured_at = item if isinstance(item, tuple) else (item, time.monotonic())
            if self.cancel.is_set():
                continue
            try:
                self.emit("stage", msg("stage.transcribing"))
                started = time.monotonic()
                text = self.transcriber.transcribe(samples, "")
                if time.monotonic() - started > len(samples) / CAPTURE_RATE:
                    self.emit("stage", msg("stage.slower_than_realtime"))
                if not text:
                    self.emit("stage", msg("stage.no_words"))
                    continue
                self.latency["stt"].append(time.monotonic() - captured_at)
                entry = {"hora": dt.datetime.now().strftime("%H:%M:%S"), "texto": text}
                self.metrics["transcript_blocks"] += 1
                self.transcript.append(entry)
                self.emit("transcript", entry)
                self.emit("latency", self.latency_snapshot())
                self.analysis.put((text, self.transcript[-RECENT_FRAGMENTS:].copy(), captured_at))
            except Exception as exc:
                self.emit("error", msg("error.transcription", detail=str(exc)))

    # -- stage 3: analysis -------------------------------------------------
    def _collect(self, first: tuple, until: float) -> tuple[str, list[dict], float, bool]:
        """Batch fragments that arrive before ``until`` so one request covers them all."""
        pending, recent = [first[0]], first[1]
        oldest = first[2] if len(first) > 2 else time.monotonic()
        ended = False
        while time.monotonic() < until:
            try:
                more = self.analysis.get(timeout=min(0.5, max(0.01, until - time.monotonic())))
            except queue.Empty:
                if self.cancel.is_set():
                    break
                continue
            if more is None:
                ended = True
                break
            pending.append(more[0])
            recent = more[1]
        return "\n".join(pending), recent, oldest, ended

    def build_payload(self, text: str, recent: list[dict]) -> str:
        """Everything the model needs for one request, kept deliberately small.

        Plan-backed requests are stateless (``store=False``), so context must be
        resent every time. The document is reduced to the passages that match
        what is being said right now.
        """
        query = text + "\n" + " ".join(entry["texto"] for entry in recent)
        return json.dumps(
            {
                "resumen_anterior": self.summary,
                "contexto_reciente": recent,
                "fragmento_nuevo": text,
                "conceptos_explicados": list(self.concepts)[-40:],
                "preguntas_respondidas": list(self.questions)[-20:],
                "documentacion": self.knowledge.relevant(query, self.context_budget_chars),
            },
            ensure_ascii=False,
        )

    def analyze(self) -> None:
        next_call = 0.0
        while True:
            item = self.analysis.get()
            if item is None:
                break
            if self.cancel.is_set() or self.analysis_disabled or isinstance(self.analyzer, NoAnalyzer):
                continue
            text, recent, oldest, ended = self._collect(item, max(next_call, time.monotonic() + 2))
            if self._carry:
                text = f"{self._carry}\n{text}".strip()
                oldest = min(oldest, self._carry_since or oldest)
            if len(text.strip()) < MIN_FRAGMENT_CHARS and not ended:
                self._carry, self._carry_since = text, oldest
                continue
            self._carry, self._carry_since = "", None
            if not self.cancel.is_set() and not self.analysis_disabled:
                self._analyze_once(text, recent, oldest)
                next_call = time.monotonic() + self.interval
            if ended:
                break
        self.emit("done", "")

    def _analyze_once(self, text: str, recent: list[dict], spoken_at: float | None = None) -> None:
        analyzer, generation = self.analyzer, self.ai_generation
        if isinstance(analyzer, NoAnalyzer):
            return
        try:
            if hasattr(analyzer, "guard"):
                analyzer.guard.progress = lambda elapsed, limit: self.emit(
                    "ai_stage", msg("ai.waiting", seconds=elapsed, limit=int(limit))
                )
            self.metrics["analysis_calls"] += 1
            self.emit("ai_stage", msg("ai.asking"))
            payload = self.build_payload(text, recent)
            self.metrics["payload_chars"] += len(payload)
            started = time.monotonic()
            output = analyzer.analyze(instructions(self.profile), payload)
            self.latency["ai"].append(time.monotonic() - started)
            self.last_ai_diagnostic = dict(getattr(analyzer, "diagnostic", {}))
            if generation != self.ai_generation:
                return  # AI was paused or swapped meanwhile: discard the late answer
            data = parse_analysis(output)
            if spoken_at is not None:
                self.latency["e2e"].append(time.monotonic() - spoken_at)
            self.emit("ai_stage", msg("ai.answered"))
            self.emit("latency", self.latency_snapshot())
            self.summary = data["resumen"]
            for concept in data["conceptos"]:
                key = concept["termino"].strip().casefold()
                if key and key not in self.concepts:
                    self.concepts[key] = concept
                    self.emit("concept", concept)
            for question in data["preguntas"]:
                key = question["pregunta"].strip().casefold()
                if key and key not in self.questions:
                    self.questions[key] = question
                    self.emit("question", question)
        except Exception as exc:
            self.last_ai_diagnostic = dict(
                getattr(analyzer, "diagnostic", {"state": "error", "type": type(exc).__name__})
            )
            self.analysis_disabled = True
            self.emit("ai_stage", msg("ai.paused_error"))
            self.emit("error", msg("error.analysis", detail=str(exc)))

    def latency_snapshot(self) -> dict[str, float | None]:
        return {key: (values[-1] if values else None) for key, values in self.latency.items()}
