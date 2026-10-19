"""Qt application bootstrap."""

from __future__ import annotations

import sys

from ..config import Settings
from ..i18n import set_language


def run(demo: bool = False, language: str | None = None) -> int:
    from PySide6.QtWidgets import QApplication

    from .main_window import MainWindow
    from .theme import STYLESHEET

    settings = Settings.load()
    set_language(language or settings.ui_language)
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Escuchator")
    app.setStyleSheet(STYLESHEET)
    window = MainWindow(settings, demo=demo)
    window.show()
    return app.exec()
