"""Strict parsing of the model's JSON answer.

Models sometimes wrap JSON in Markdown fences or return partial structures.
Anything that does not match the expected shape is dropped rather than shown.
"""

from __future__ import annotations

import json
from typing import Any

MAX_CONCEPTS = 4
MAX_QUESTIONS = 3
MAX_SUMMARY_CHARS = 6000


def parse_analysis(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```") and text.endswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("Invalid analysis: expected a JSON object")
    concepts = data.get("conceptos", [])
    questions = data.get("preguntas", [])
    if not isinstance(concepts, list) or not isinstance(questions, list):
        raise ValueError("Invalid analysis: 'conceptos' and 'preguntas' must be lists")
    return {
        "resumen": str(data.get("resumen", ""))[:MAX_SUMMARY_CHARS],
        "conceptos": [
            c
            for c in concepts
            if isinstance(c, dict)
            and isinstance(c.get("termino"), str)
            and isinstance(c.get("explicacion"), str)
        ][:MAX_CONCEPTS],
        "preguntas": [
            q
            for q in questions
            if isinstance(q, dict) and isinstance(q.get("pregunta"), str) and isinstance(q.get("breve"), str)
        ][:MAX_QUESTIONS],
    }
