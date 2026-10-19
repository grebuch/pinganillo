"""Regenerate the README screenshots from the demo meeting (headless).

QT_QPA_PLATFORM=offscreen python scripts/make_screenshots.py
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from escuchator.config import Settings
from escuchator.demo import DemoAnalyzer, DemoDevice, DemoTranscriber
from escuchator.i18n import set_language, tr
from escuchator.pipeline import Session
from escuchator.ui.main_window import MainWindow
from escuchator.ui.theme import STYLESHEET

OUT = Path(__file__).resolve().parent.parent / "docs" / "img"


class Speakers:
    name, isloopback = "Speakers (Realtek Audio)", True


def shoot(app: QApplication, language: str) -> Path:
    set_language(language)
    settings = Settings(
        ai_provider="ollama",
        ai_model="qwen2.5:7b",
        capture_engine="wasapi",
        speech_language=language,
        notice_acknowledged=True,
    )
    window = MainWindow(settings, devices_fn=lambda engine: ([Speakers()], 0), persist=False)
    window.resize(1440, 860)
    window.show()
    window.ai_button.setChecked(True)
    window._update_ai_button()
    session = Session(
        DemoTranscriber(language, delay=0.4),
        DemoAnalyzer(language, delay=0.8),
        DemoDevice(speed=8),
        profile="it",
        events=window.events,
        interval=0.5,
    )
    window.session = session
    session.start()
    window._set_live()
    deadline = time.monotonic() + 60
    while (len(session.questions) < 2 or len(session.transcript) < 5) and time.monotonic() < deadline:
        app.processEvents()
        window.poll()
        time.sleep(0.05)
    for _ in range(10):
        window.poll()
        app.processEvents()
    window.meter.setValue(38)
    window.ai_label.setText(tr("ai.answered"))
    window.stage_label.setText("Whisper small · CPU int8")
    path = OUT / f"screenshot-{language}.png"
    window.grab().save(str(path))
    session.stop.set()
    session.cancel.set()
    window.close()
    return path


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)
    for language in ("en", "es"):
        print(shoot(app, language))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
