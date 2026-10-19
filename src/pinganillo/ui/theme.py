"""Visual identity.

The app sits next to a video call for an hour, so it is calm by default: an
ink-slate surface and warm paper-coloured text. Amber is the "on air" lamp of
a radio studio and is reserved for two things only: the app is listening, and
the line you could say out loud. Everything else stays quiet.
"""

from __future__ import annotations

from pathlib import Path

ICON = Path(__file__).resolve().parent.parent / "assets" / "icon.svg"

INK = "#1A2230"  # window background
SLATE = "#222C3C"  # panels
LINE = "#33405A"  # borders, separators
PAPER = "#ECE6D9"  # primary text
MUTED = "#98A3B6"  # secondary text
AMBER = "#F2B544"  # live state and "say this"
DANGER = "#E58A7A"
CALM = "#8CCFB0"

FONT = '"Segoe UI Variable Text", "Segoe UI", "Inter", "Helvetica Neue", sans-serif'

STYLESHEET = f"""
* {{ font-family: {FONT}; font-size: 13px; color: {PAPER}; }}
QMainWindow, QWidget#root {{ background: {INK}; }}
QWidget#sidebar {{ background: {INK}; }}
QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}

QLabel#brand {{ font-size: 20px; font-weight: 700; letter-spacing: 0.5px; }}
QLabel#tagline {{ color: {MUTED}; }}
QLabel#section {{ color: {MUTED}; font-weight: 600; padding-top: 14px; }}
QLabel#hint {{ color: {MUTED}; font-size: 12px; }}
QLabel#panelTitle {{ font-size: 15px; font-weight: 600; padding: 2px 2px 6px 2px; }}

QLabel#onAir {{
    border: 1px solid {LINE}; border-radius: 13px; padding: 4px 12px; color: {MUTED};
}}
QLabel#onAir[live="true"] {{ border-color: {AMBER}; color: {AMBER}; }}

QFrame#panel {{ background: {SLATE}; border: 1px solid {LINE}; border-radius: 10px; }}
QTextBrowser {{
    background: transparent; border: none; selection-background-color: {LINE};
    font-size: 14px;
}}

QComboBox, QLineEdit {{
    background: {SLATE}; border: 1px solid {LINE}; border-radius: 6px; padding: 5px 8px; min-height: 18px;
}}
QComboBox:focus, QLineEdit:focus {{ border-color: {MUTED}; }}
QComboBox QAbstractItemView {{
    background: {SLATE}; border: 1px solid {LINE}; selection-background-color: {LINE};
}}

QPushButton {{
    background: {SLATE}; border: 1px solid {LINE}; border-radius: 6px; padding: 6px 12px;
}}
QPushButton:hover {{ border-color: {MUTED}; }}
QPushButton:focus {{ border-color: {PAPER}; }}
QPushButton:disabled {{ color: {MUTED}; border-color: {SLATE}; }}
QPushButton#primary {{
    background: {AMBER}; color: {INK}; border: none; font-weight: 700; padding: 8px 18px;
}}
QPushButton#primary[live="true"] {{ background: {SLATE}; color: {AMBER}; border: 1px solid {AMBER}; }}
QPushButton#toggle[checked="true"] {{ border-color: {CALM}; color: {CALM}; }}
QPushButton#flat {{ background: transparent; border: none; color: {MUTED}; padding: 4px 6px; }}
QPushButton#flat:hover {{ color: {PAPER}; }}

QProgressBar {{ background: {SLATE}; border: none; border-radius: 2px; max-height: 4px; }}
QProgressBar::chunk {{ background: {AMBER}; border-radius: 2px; }}
QStatusBar {{ background: {INK}; border-top: 1px solid {LINE}; }}
QStatusBar QLabel {{ color: {MUTED}; padding: 0 8px; }}
QSplitter::handle {{ background: {INK}; }}
QScrollBar:vertical {{ background: transparent; width: 8px; }}
QScrollBar::handle:vertical {{ background: {LINE}; border-radius: 4px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
"""

CARD_CSS = f"""
<style>
  p {{ margin: 0; }}
  .term {{ font-weight: 700; font-size: 15px; color: {PAPER}; }}
  .body {{ color: {PAPER}; }}
  .muted {{ color: {MUTED}; }}
  .question {{ font-weight: 600; color: {PAPER}; }}
  .say {{ color: {AMBER}; font-size: 16px; font-weight: 600; }}
  .label {{ color: {MUTED}; font-size: 12px; }}
  .time {{ color: {MUTED}; font-size: 12px; }}
  .error {{ color: {DANGER}; }}
</style>
"""
