"""Demo mode: the real pipeline, driven by a scripted meeting.

``pinganillo --demo`` runs the actual capture -> transcribe -> analyse threads,
but the device synthesises audio, the transcriber returns scripted lines and the
analyzer returns scripted JSON. It needs no microphone, no model download and no
account, which makes it handy for screenshots, UI work and trying the app.
"""

from __future__ import annotations

import json
import threading
import time
from typing import Any

import numpy as np

from .audio.dsp import CAPTURE_RATE

SCRIPT: dict[str, list[dict[str, Any]]] = {
    "en": [
        {"text": "Let's review the backup plan for the ERP before next month's audit."},
        {"text": "Right now we take nightly backups, so in the worst case we'd lose a full day of orders."},
        {
            "text": "The auditors will ask about our RTO and RPO, and whether the backups are immutable.",
            "concepts": [
                (
                    "RTO",
                    "Recovery Time Objective: the maximum time a system may stay down after an incident.",
                ),
                ("RPO", "Recovery Point Objective: how much data, measured in time, you can afford to lose."),
                (
                    "Immutable backup",
                    "A copy that cannot be modified or deleted for a set period, even by an admin.",
                ),
            ],
        },
        {
            "text": "What would it take to get the RPO down to fifteen minutes?",
            "questions": [
                (
                    "What would it take to get the RPO down to 15 minutes?",
                    "Move from nightly backups to 15-minute snapshots or continuous replication of the ERP database.",
                    "Snapshots are usually the cheaper step; replication also shortens the RTO.",
                    "Database size, daily change rate and available bandwidth.",
                )
            ],
        },
        {
            "text": "And do we need a second site, or is a cloud copy enough for NIS2?",
            "concepts": [
                (
                    "NIS2",
                    "EU cybersecurity directive that includes business continuity and backup management.",
                ),
            ],
            "questions": [
                (
                    "Is a cloud copy enough, or do we need a second site?",
                    "NIS2 asks for continuity and backup management, not a specific architecture.",
                    "An isolated, immutable cloud copy often covers off-site needs; a second site buys speed.",
                    "Whether the company is in NIS2 scope, and the RTO the business accepts.",
                )
            ],
        },
    ],
    "es": [
        {"text": "Repasemos el plan de copias del ERP antes de la auditoría del mes que viene."},
        {"text": "Ahora hacemos copias cada noche, así que en el peor caso perderíamos un día de pedidos."},
        {
            "text": "Los auditores preguntarán por el RTO y el RPO, y si las copias son inmutables.",
            "concepts": [
                (
                    "RTO",
                    "Objetivo de tiempo de recuperación: cuánto puede estar caído un sistema tras un incidente.",
                ),
                (
                    "RPO",
                    "Objetivo de punto de recuperación: cuántos datos, medidos en tiempo, puedes perder.",
                ),
                (
                    "Copia inmutable",
                    "Copia que nadie puede modificar ni borrar durante un periodo, ni un administrador.",
                ),
            ],
        },
        {
            "text": "¿Qué haría falta para bajar el RPO a quince minutos?",
            "questions": [
                (
                    "¿Qué haría falta para bajar el RPO a 15 minutos?",
                    "Pasar de la copia nocturna a instantáneas cada 15 minutos o a replicación continua de la base de datos.",
                    "Las instantáneas suelen ser el paso más barato; la replicación además reduce el RTO.",
                    "Tamaño de la base de datos, volumen de cambios diario y ancho de banda disponible.",
                )
            ],
        },
        {
            "text": "¿Y necesitamos un segundo centro o basta con una copia en la nube para NIS2?",
            "concepts": [
                (
                    "NIS2",
                    "Directiva europea de ciberseguridad que incluye continuidad de negocio y gestión de copias.",
                ),
            ],
            "questions": [
                (
                    "¿Basta una copia en la nube o hace falta un segundo centro?",
                    "NIS2 pide continuidad y gestión de copias, no una arquitectura concreta.",
                    "Una copia aislada e inmutable en la nube suele cubrir el requisito externo; un segundo centro da rapidez.",
                    "Si la empresa entra en el ámbito de NIS2 y qué RTO acepta el negocio.",
                )
            ],
        },
    ],
}


class DemoDevice:
    """Synthesises ~6 s of 'speech' (a tone) followed by 1.5 s of silence, in real time."""

    name = "Demo"
    isloopback = True

    def __init__(self, speed: float = 1.0) -> None:
        self.speed = speed

    def recorder(self, samplerate: int = CAPTURE_RATE) -> _DemoRecorder:
        return _DemoRecorder(samplerate, self.speed)


class _DemoRecorder:
    def __init__(self, rate: int, speed: float) -> None:
        self.rate, self.speed, self.index = rate, speed, 0

    def __enter__(self) -> _DemoRecorder:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def record(self, numframes: int) -> np.ndarray:
        time.sleep(numframes / self.rate / self.speed)
        speaking = self.index % 15 < 12  # 12 loud blocks then 3 quiet ones
        self.index += 1
        if not speaking:
            return np.zeros((numframes, 2), np.float32)
        t = (np.arange(numframes) + self.index * numframes) / self.rate
        wave = (0.08 * np.sin(2 * np.pi * 180 * t) * (1 + 0.5 * np.sin(2 * np.pi * 3 * t))).astype(np.float32)
        return np.repeat(wave[:, None], 2, axis=1)


class DemoTranscriber:
    def __init__(self, language: str = "en", delay: float = 0.6) -> None:
        self.lines = [step["text"] for step in SCRIPT.get(language, SCRIPT["en"])]
        self.delay, self.index = delay, 0

    def transcribe(self, samples: np.ndarray, prompt: str = "") -> str:
        time.sleep(self.delay)
        if self.index >= len(self.lines):
            return ""
        self.index += 1
        return self.lines[self.index - 1]


class DemoAnalyzer:
    """Returns the scripted concepts/questions for whichever lines are in the new fragment."""

    def __init__(self, language: str = "en", delay: float = 1.2) -> None:
        self.script = SCRIPT.get(language, SCRIPT["en"])
        self.delay = delay
        self.lock = threading.Lock()

    def analyze(self, instructions: str, payload: str) -> str:
        time.sleep(self.delay)
        fragment = json.loads(payload)["fragmento_nuevo"]
        concepts, questions = [], []
        for step in self.script:
            if step["text"] in fragment:
                concepts += [{"termino": t, "explicacion": e} for t, e in step.get("concepts", [])]
                questions += [
                    {"pregunta": q, "breve": b, "detalle": d, "faltan": f}
                    for q, b, d, f in step.get("questions", [])
                ]
        return json.dumps({"resumen": "", "conceptos": concepts, "preguntas": questions}, ensure_ascii=False)
