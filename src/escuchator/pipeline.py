"""The live pipeline: capture -> transcribe -> analyse, one thread each.

Threads talk through queues and never touch the UI. Everything the UI needs
is published as ``(session, kind, value)`` tuples on ``events``; the UI polls
that queue from its own thread. Each stage can fail without stopping the
previous ones: if the AI breaks, capture and transcription keep going.

Shutdown is a sentinel (``None``) that flows down the queues, so pending audio
is still transcribed after the user presses stop.
"""

from __future__ import annotations

import datetime as dt
import json
import queue
import threading
import time
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
        self.audio: queue.Queue[np.ndarray | None] = queue.Queue(maxsize=20)
        self.analysis: queue.Queue[tuple[str, list[dict]] | None] = queue.Queue()
        self.analysis_disabled = False
        self.ai_generation = 0
        self.last_ai_diagnostic: dict[str, Any] = {}
        self.transcript: list[dict[str, str]] = []
        self.summary = ""
        self.concepts: dict[str, dict] = {}
        self.questions: dict[str, dict] = {}
        self._carry = ""
        self.threads: list[threading.Thread] = []
        self.last_audio = time.monotonic()
        self.metrics = {
            "audio_blocks": 0,
            "transcript_blocks": 0,
            "analysis_calls": 0,
            "dropped_chunks": 0,
            "payload_chars": 0,
        }
        self.errors: list[str] = []

    # -- plumbing ----------------------------------------------------------
    def emit(self, kind: str, value: Any) -> None:
        if kind == "error":
            self.errors.append(str(value))
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
            self.emit("error", f"Audio capture: {exc}")
        finally:
            self.audio.put(None)

    def enqueue(self, chunk: np.ndarray) -> None:
        self.metrics["audio_blocks"] += 1
        if rms(to_mono(chunk)) < SILENT_CHUNK:
            return
        try:
            self.audio.put_nowait(chunk)
        except queue.Full:
            self.metrics["dropped_chunks"] += 1
            self.emit(
                "error", "Transcription is falling behind: an audio chunk was skipped. Try a smaller model."
            )

    # -- stage 2: transcription -------------------------------------------
    def transcribe(self) -> None:
        if hasattr(self.transcriber, "prepare"):
            self.emit("stage", "Loading local Whisper: the first download can take a few minutes…")
            try:
                self.transcriber.prepare()
                self.emit("stage", "Whisper ready · waiting for speech")
            except Exception as exc:
                self.emit("error", f"Could not load Whisper: {exc}")
                self.stop.set()
                while self.audio.get() is not None:
                    pass  # drain so capture can shut down cleanly
                self.analysis.put(None)
                return
        while True:
            samples = self.audio.get()
            if samples is None:
                self.analysis.put(None)
                return
            if self.cancel.is_set():
                continue
            try:
                self.emit("stage", "Transcribing…")
                started = time.monotonic()
                text = self.transcriber.transcribe(samples, "")
                if time.monotonic() - started > len(samples) / CAPTURE_RATE:
                    self.emit("stage", "Transcription is slower than real time: try a smaller model")
                if not text:
                    self.emit("stage", "Audio received, but no words detected in this chunk")
                    continue
                entry = {"hora": dt.datetime.now().strftime("%H:%M:%S"), "texto": text}
                self.metrics["transcript_blocks"] += 1
                self.transcript.append(entry)
                self.emit("transcript", entry)
                self.analysis.put((text, self.transcript[-RECENT_FRAGMENTS:].copy()))
            except Exception as exc:
                self.emit("error", f"Transcription: {exc}")

    # -- stage 3: analysis -------------------------------------------------
    def _collect(self, first: tuple[str, list[dict]], until: float) -> tuple[str, list[dict], bool]:
        """Batch fragments that arrive before ``until`` so one request covers them all."""
        pending, recent = [first[0]], first[1]
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
        return "\n".join(pending), recent, ended

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
            text, recent, ended = self._collect(item, max(next_call, time.monotonic() + 2))
            text = f"{self._carry}\n{text}".strip() if self._carry else text
            if len(text.strip()) < MIN_FRAGMENT_CHARS and not ended:
                self._carry = text
                continue
            self._carry = ""
            if not self.cancel.is_set() and not self.analysis_disabled:
                self._analyze_once(text, recent)
                next_call = time.monotonic() + self.interval
            if ended:
                break
        self.emit("done", "")

    def _analyze_once(self, text: str, recent: list[dict]) -> None:
        analyzer, generation = self.analyzer, self.ai_generation
        if isinstance(analyzer, NoAnalyzer):
            return
        try:
            if hasattr(analyzer, "guard"):
                analyzer.guard.progress = lambda message: self.emit("ai_stage", message)
            self.metrics["analysis_calls"] += 1
            self.emit("ai_stage", "Asking the AI…")
            payload = self.build_payload(text, recent)
            self.metrics["payload_chars"] += len(payload)
            output = analyzer.analyze(instructions(self.profile), payload)
            self.last_ai_diagnostic = dict(getattr(analyzer, "diagnostic", {}))
            if generation != self.ai_generation:
                return  # AI was paused or swapped meanwhile: discard the late answer
            data = parse_analysis(output)
            self.emit("ai_stage", "AI answered · waiting for new speech")
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
            self.emit("ai_stage", "AI paused after an error; transcription keeps running")
            self.emit("error", f"Analysis paused: {exc} Local transcription continues.")
