"""Session export (Markdown notes or JSON) and the privacy-safe diagnostics report."""

from __future__ import annotations

import json
import platform
import sys
from dataclasses import asdict
from typing import Any

from . import __version__
from .i18n import tr


def session_to_markdown(session: Any, title: str = "Pinganillo") -> str:
    lines = [f"# {title}", ""]
    if session.summary:
        lines += [f"## {tr('export.heading_summary')}", "", session.summary, ""]
    if session.questions:
        lines += [f"## {tr('export.heading_questions')}", ""]
        for q in session.questions.values():
            lines.append(f"- **{q['pregunta']}**")
            lines.append(f"  - {tr('answer.reply')}: {q['breve']}")
            if q.get("detalle"):
                lines.append(f"  - {q['detalle']}")
            if q.get("faltan"):
                lines.append(f"  - {tr('answer.missing')}: {q['faltan']}")
        lines.append("")
    if session.concepts:
        lines += [f"## {tr('export.heading_concepts')}", ""]
        lines += [f"- **{c['termino']}**: {c['explicacion']}" for c in session.concepts.values()]
        lines.append("")
    lines += [f"## {tr('export.heading_transcript')}", ""]
    lines += [f"`{e['hora']}` {e['texto']}  " for e in session.transcript]
    return "\n".join(lines).rstrip() + "\n"


def session_to_json(session: Any) -> str:
    return json.dumps(
        {
            "version": __version__,
            "summary": session.summary,
            "transcript": session.transcript,
            "concepts": list(session.concepts.values()),
            "questions": list(session.questions.values()),
        },
        ensure_ascii=False,
        indent=2,
    )


def diagnostics_report(settings: Any, session: Any | None, extra: dict[str, Any] | None = None) -> str:
    """Versions, settings, counters and latency. Never audio, transcript, documents or credentials."""
    from .diagnostics import package_versions

    data: dict[str, Any] = {
        "pinganillo": __version__,
        "platform": f"{platform.system()} {platform.release()} ({platform.machine()})",
        "python": sys.version.split()[0],
        "packages": package_versions(),
        "settings": asdict(settings),
        "session": None,
        "note": "No audio, transcript, documents, e-mail or credentials are included.",
    }
    if session is not None:
        data["session"] = {
            "metrics": dict(session.metrics),
            "latency_seconds": session.latency_summary(),
            "ai_diagnostic": dict(session.last_ai_diagnostic),
            "error_count": len(session.errors),
            "error_kinds": sorted({e.split(":", 1)[0] for e in session.errors}),
            "audio_queue": session.audio.qsize(),
            "analysis_queue": session.analysis.qsize(),
        }
    if extra:
        data.update(extra)
    return json.dumps(data, ensure_ascii=False, indent=2)
