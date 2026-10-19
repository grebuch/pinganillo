"""End-to-end run of the real pipeline in demo mode, plus a headless UI smoke test."""

import os
import queue

import pytest

from escuchator.demo import SCRIPT, DemoAnalyzer, DemoDevice, DemoTranscriber
from escuchator.pipeline import Session


def run_demo(speed=40.0):
    events = queue.Queue()
    session = Session(
        DemoTranscriber("en", delay=0),
        DemoAnalyzer("en", delay=0),
        DemoDevice(speed),
        events=events,
        interval=0,
    )
    session.start()
    return session, events


def test_demo_meeting_flows_through_the_real_pipeline():
    session, _ = run_demo()
    import time

    deadline = time.monotonic() + 20
    while len(session.questions) < 2 and time.monotonic() < deadline:
        time.sleep(0.05)
    session.stop.set()
    for t in session.threads:
        t.join(10)
    assert len(session.transcript) == len(SCRIPT["en"])
    assert {"rto", "rpo", "nis2"} <= set(session.concepts)
    assert len(session.questions) == 2
    summary = session.latency_summary()
    assert summary["stt"]["n"] >= 5 and summary["e2e"]["n"] >= 1


@pytest.fixture
def qt_app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    widgets = pytest.importorskip("PySide6.QtWidgets")
    from escuchator.ui.theme import STYLESHEET

    app = widgets.QApplication.instance() or widgets.QApplication([])
    app.setStyleSheet(STYLESHEET)
    return app


def test_main_window_builds_and_renders_session_events(qt_app, tmp_path):
    from escuchator.config import Settings
    from escuchator.ui.main_window import MainWindow

    class Dev:
        name, isloopback = "Speakers", True

    window = MainWindow(Settings(), devices_fn=lambda engine: ([Dev()], 0), persist=False)
    assert window.source_combo.count() == 1
    assert not window.ai_button.isEnabled()  # provider "none": AI cannot be switched on

    window._select(window.provider_combo, "ollama")
    assert window.ai_button.isEnabled()
    assert window.url_edit.placeholderText() == "http://localhost:11434/v1"

    window.session = Session(None, None, None, events=window.events)
    window.session.transcript.append({"hora": "10:00", "texto": "hello"})
    window.events.put((window.session, "transcript", {"hora": "10:00", "texto": "hello"}))
    window.events.put((window.session, "concept", {"termino": "RTO", "explicacion": "Recovery time."}))
    window.events.put((window.session, "question", {"pregunta": "How?", "breve": "Like this."}))
    window.events.put((window.session, "error", ("error.analysis", {"detail": "HTTP 429"})))
    window.poll()
    assert "RTO" in window.concepts_view.toPlainText()
    assert "Like this." in window.answers_view.toPlainText()
    transcript = window.transcript_view.toPlainText()
    assert "hello" in transcript and "HTTP 429" in transcript
    window.close()
