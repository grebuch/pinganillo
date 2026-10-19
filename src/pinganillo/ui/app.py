"""Qt application bootstrap."""

from __future__ import annotations

import contextlib
import faulthandler
import logging
import sys

from ..config import Settings
from ..i18n import set_language

log = logging.getLogger("pinganillo")
STARTUP_WATCHDOG_S = 30


def _start_watchdog() -> None:
    """If start-up stalls, dump every thread's stack to stderr so the hang can be located."""
    with contextlib.suppress(AttributeError, ValueError, OSError, RuntimeError):
        if sys.stderr is not None:
            faulthandler.dump_traceback_later(STARTUP_WATCHDOG_S, exit=False)


def _stop_watchdog() -> None:
    with contextlib.suppress(Exception):
        faulthandler.cancel_dump_traceback_later()


def run(demo: bool = False, language: str | None = None) -> int:
    if sys.stderr is not None:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    _start_watchdog()
    log.info("starting Qt")

    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    from .main_window import MainWindow
    from .theme import ICON, STYLESHEET

    settings = Settings.load()
    set_language(language or settings.ui_language)
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Pinganillo")
    app.setStyleSheet(STYLESHEET)
    app.setWindowIcon(QIcon(str(ICON)))
    log.info("building the main window")
    window = MainWindow(settings, demo=demo)
    window.show()
    window.raise_()
    window.activateWindow()
    log.info("window shown")
    QTimer.singleShot(0, _stop_watchdog)  # the event loop is running: start-up is over
    return app.exec()
