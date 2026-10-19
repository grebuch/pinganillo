"""Regenerate the README screenshots from the demo meeting (headless).

QT_QPA_PLATFORM=offscreen python scripts/make_screenshots.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
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


def shoot(app: QApplication, language: str, gif: bool = False) -> Path:
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
        DemoDevice(speed=3 if gif else 8),
        profile="it",
        events=window.events,
        interval=0.5,
    )
    window.session = session
    session.start()
    window._set_live()
    frames = Path(tempfile.mkdtemp()) if gif else None
    next_frame, count = time.monotonic(), 0
    deadline = time.monotonic() + 90
    while (len(session.questions) < 2 or len(session.transcript) < 5) and time.monotonic() < deadline:
        app.processEvents()
        window.poll()
        if frames and time.monotonic() >= next_frame:
            window.grab().scaledToWidth(960, Qt.TransformationMode.SmoothTransformation).save(
                str(frames / f"{count:04d}.png")
            )
            count += 1
            next_frame += 0.25
        time.sleep(0.02)
    for _ in range(10):
        window.poll()
        app.processEvents()
    window.meter.setValue(38)
    window.ai_label.setText(tr("ai.answered"))
    window.stage_label.setText("Whisper small · CPU int8")
    path = OUT / f"screenshot-{language}.png"
    window.grab().save(str(path))
    if frames:
        for extra in range(8):  # hold the final state for two seconds
            window.grab().scaledToWidth(960, Qt.TransformationMode.SmoothTransformation).save(
                str(frames / f"{count + extra:04d}.png")
            )
        path = OUT / "demo.gif"
        palette = "split[a][b];[a]palettegen=max_colors=96[p];[b][p]paletteuse=dither=none"
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-loglevel",
                "error",
                "-framerate",
                "4",
                "-i",
                str(frames / "%04d.png"),
                "-filter_complex",
                palette,
                str(path),
            ],
            check=True,
        )
        shutil.rmtree(frames)
    session.stop.set()
    session.cancel.set()
    window.close()
    return path


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)
    for language in ("en", "es"):
        print(shoot(app, language))
    if "--gif" in sys.argv:
        print(shoot(app, "en", gif=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
