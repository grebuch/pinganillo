import json
import threading
from types import SimpleNamespace

import numpy as np

from conftest import FakeDevice
from escuchator.llm.analyzers import NoAnalyzer
from escuchator.pipeline import Session

ANSWER = json.dumps(
    {
        "resumen": "Backups.",
        "conceptos": [{"termino": "RTO", "explicacion": "Recovery time objective."}],
        "preguntas": [{"pregunta": "How do we reduce RTO?", "breve": "Replication."}],
    }
)


def drain(events):
    kinds = []
    while not events.empty():
        kinds.append(events.get()[1])
    return kinds


def test_capture_and_transcription_work_without_any_account(speech_block):
    device = FakeDevice([speech_block()] * 10)
    session = Session(SimpleNamespace(transcribe=lambda *a: "Hola"), NoAnalyzer(), device)
    device.ref["session"] = session
    session.start()
    for t in session.threads:
        t.join(5)
        assert not t.is_alive()
    assert session.metrics["transcript_blocks"] >= 1
    assert session.metrics["analysis_calls"] == 0
    assert session.transcript[0]["texto"] == "Hola"
    assert "done" in drain(session.events)


def test_ai_failure_pauses_only_the_analysis():
    def fail(*args):
        raise ValueError("limit")

    session = Session(SimpleNamespace(transcribe=lambda *a: "x"), SimpleNamespace(analyze=fail), None)
    session.analysis.put(("Text", []))
    session.analysis.put(None)
    session.analyze()
    assert session.analysis_disabled
    assert not session.stop.is_set()


def test_transcription_continues_while_ai_is_waiting():
    entered, release = threading.Event(), threading.Event()

    def slow_ai(*args):
        entered.set()
        release.wait(3)
        return ANSWER

    session = Session(
        SimpleNamespace(transcribe=lambda *a: "Text"), SimpleNamespace(analyze=slow_ai), None, interval=0
    )
    session.analysis.put(("Question", []))
    session.analysis.put(None)
    ai = threading.Thread(target=session.analyze)
    ai.start()
    try:
        assert entered.wait(3)
        session.audio.put(np.ones((480, 2), np.float32))
        session.audio.put(None)
        stt = threading.Thread(target=session.transcribe)
        stt.start()
        stt.join(2)
        assert not stt.is_alive()
        assert session.metrics["transcript_blocks"] == 1
        assert ai.is_alive()
    finally:
        release.set()
        ai.join(3)


def test_fragments_are_batched_and_results_deduplicated():
    calls = []

    def analyze(instructions, payload):
        calls.append(json.loads(payload))
        return ANSWER

    session = Session(
        SimpleNamespace(transcribe=lambda *a: "How do we reduce RTO?"),
        SimpleNamespace(analyze=analyze),
        None,
        profile="it",
        interval=0,
    )
    for _ in range(2):
        session.audio.put(np.ones((480, 2), np.float32) * 0.1)
    session.audio.put(None)
    threads = [threading.Thread(target=session.transcribe), threading.Thread(target=session.analyze)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(5)
        assert not t.is_alive()
    kinds = drain(session.events)
    assert kinds.count("transcript") == 2
    assert kinds.count("concept") == 1
    assert kinds.count("question") == 1
    assert kinds[-1] == "done"
    assert len(calls) == 1
    assert "\n" in calls[0]["fragmento_nuevo"]
