"""Qt main window.

Threading rule: worker threads never touch widgets. The pipeline and the
background tasks (sign-in, model listing, AI test) post ``(source, kind, value)``
tuples to one queue, and a 100 ms QTimer on the GUI thread drains it.
"""

from __future__ import annotations

import contextlib
import html
import json
import queue
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QCloseEvent, QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStatusBar,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..audio.devices import ENGINES, default_engine, list_devices
from ..config import SPEECH_LANGUAGES, WHISPER_MODELS, Settings, api_key_from_env
from ..export import diagnostics_report, session_to_json, session_to_markdown
from ..i18n import current_language, tr, tr_message
from ..llm.analyzers import NoAnalyzer
from ..llm.knowledge import KnowledgeBase
from ..llm.parsing import parse_analysis
from ..llm.prompt import PROFILES, instructions
from ..llm.providers import PROVIDERS, build_analyzer
from ..pipeline import Session
from . import theme

SAMPLE_PAYLOAD = json.dumps(
    {
        "resumen_anterior": "",
        "contexto_reciente": [],
        "fragmento_nuevo": "We are talking about backups. What does RTO mean?",
        "conceptos_explicados": [],
        "preguntas_respondidas": [],
        "documentacion": "",
    }
)
MAX_TRANSCRIPT_LINES = 400


def _fmt_seconds(value: float | None) -> str:
    return "–" if value is None else f"{value:.1f} s"


class MainWindow(QMainWindow):
    def __init__(
        self,
        settings: Settings,
        demo: bool = False,
        devices_fn: Callable[[str], tuple[list[Any], int]] = list_devices,
        auth: Any = None,
        persist: bool = True,
    ) -> None:
        super().__init__()
        self.settings, self.demo, self.devices_fn, self.persist = settings, demo, devices_fn, persist
        self._auth = auth
        self.events: queue.Queue = queue.Queue()
        self.session: Session | None = None
        self.devices: list[Any] = []
        self.transcriber: Any = None
        self.knowledge = KnowledgeBase("")
        self.doc_name = ""
        self.concepts: list[dict] = []
        self.answers: list[dict] = []
        self.chatgpt_models: list[dict] = []

        self.setWindowTitle("Escuchator")
        self.resize(1320, 840)
        self._build()
        self._restore()
        self.refresh_devices()
        self.on_provider_changed()
        if demo:  # the demo is about the suggestions, so start with the AI on
            self.ai_button.setChecked(True)
            self._update_ai_button()
        self._render_all()
        self._set_idle()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll)
        self.timer.start(100)
        QShortcut(QKeySequence("Ctrl+Space"), self, activated=self.toggle_listening)

    # ------------------------------------------------------------------ build
    def _build(self) -> None:
        root = QWidget(objectName="root")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(16, 12, 16, 0)
        layout.setSpacing(10)

        header = QHBoxLayout()
        brand = QLabel("Escuchator", objectName="brand")
        header.addWidget(brand)
        header.addWidget(QLabel(tr("app.tagline"), objectName="tagline"))
        header.addStretch(1)
        self.settings_button = QPushButton(tr("btn.settings"), objectName="flat", clicked=self.toggle_sidebar)
        header.addWidget(self.settings_button)
        self.on_air = QLabel(objectName="onAir")
        header.addWidget(self.on_air)
        self.ai_button = QPushButton(objectName="toggle", checkable=True)
        self.ai_button.clicked.connect(self.toggle_ai)
        header.addWidget(self.ai_button)
        self.start_button = QPushButton(objectName="primary", clicked=self.toggle_listening)
        header.addWidget(self.start_button)
        layout.addLayout(header)

        self.body = QSplitter(Qt.Orientation.Horizontal)
        self.body.setChildrenCollapsible(False)
        self.sidebar = self._build_sidebar()
        self.body.addWidget(self.sidebar)

        main = QSplitter(Qt.Orientation.Vertical)
        top = QSplitter(Qt.Orientation.Horizontal)
        concepts_panel, self.concepts_view = self._panel(tr("panel.concepts"))
        answers_panel, self.answers_view = self._panel(tr("panel.answers"))
        top.addWidget(concepts_panel)
        top.addWidget(answers_panel)
        top.setSizes([520, 640])
        transcript_panel, self.transcript_view = self._panel(tr("panel.transcript"))
        main.addWidget(top)
        main.addWidget(transcript_panel)
        main.setSizes([560, 220])
        self.body.addWidget(main)
        self.body.setSizes([350, 970])
        self.body.setStretchFactor(1, 1)
        layout.addWidget(self.body, 1)
        self.setCentralWidget(root)

        status = QStatusBar()
        self.meter = QProgressBar(maximum=100, textVisible=False)
        self.meter.setFixedWidth(120)
        self.stage_label = QLabel()
        self.ai_label = QLabel()
        self.latency_label = QLabel()
        status.addWidget(self.meter)
        status.addWidget(self.stage_label, 1)
        status.addWidget(self.ai_label, 1)
        status.addPermanentWidget(self.latency_label)
        self.setStatusBar(status)

    def _panel(self, title: str) -> tuple[QFrame, QTextBrowser]:
        frame = QFrame(objectName="panel")
        box = QVBoxLayout(frame)
        box.setContentsMargins(14, 10, 14, 10)
        box.addWidget(QLabel(title, objectName="panelTitle"))
        browser = QTextBrowser(openExternalLinks=False)
        box.addWidget(browser, 1)
        return frame, browser

    def _section(self, form: QFormLayout, key: str) -> None:
        form.addRow(QLabel(tr(key), objectName="section"))

    def _build_sidebar(self) -> QScrollArea:
        container = QWidget(objectName="sidebar")
        form = QFormLayout(container)
        form.setContentsMargins(0, 0, 12, 12)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        form.setVerticalSpacing(6)
        self.form = form

        self._section(form, "group.audio")
        self.engine_combo = QComboBox()
        for engine in ENGINES:
            self.engine_combo.addItem(tr(f"engine.{engine}"), engine)
        self.engine_combo.currentIndexChanged.connect(lambda _: self.refresh_devices())
        form.addRow(tr("label.engine"), self.engine_combo)
        self.source_combo = QComboBox()
        source_row = QHBoxLayout()
        source_row.addWidget(self.source_combo, 1)
        source_row.addWidget(QPushButton(tr("btn.refresh"), clicked=self.refresh_devices))
        form.addRow(tr("label.source"), source_row)

        self._section(form, "group.transcription")
        self.whisper_combo = QComboBox()
        self.whisper_combo.addItems(list(WHISPER_MODELS))
        form.addRow(tr("label.whisper_model"), self.whisper_combo)
        self.language_combo = QComboBox()
        for code in SPEECH_LANGUAGES:
            self.language_combo.addItem(tr(f"speech.{code}"), code)
        form.addRow(tr("label.speech_language"), self.language_combo)

        self._section(form, "group.ai")
        self.provider_combo = QComboBox()
        for key in PROVIDERS:
            self.provider_combo.addItem(tr(f"provider.{key}"), key)
        self.provider_combo.currentIndexChanged.connect(lambda _: self.on_provider_changed())
        form.addRow(tr("label.provider"), self.provider_combo)
        self.provider_hint = QLabel(objectName="hint", wordWrap=True)
        form.addRow(self.provider_hint)
        self.url_edit = QLineEdit()
        form.addRow(tr("label.server_url"), self.url_edit)
        self.chatgpt_row = QHBoxLayout()
        self.connect_button = QPushButton(tr("btn.connect_chatgpt"), clicked=self.connect_chatgpt)
        self.disconnect_button = QPushButton(tr("btn.disconnect"), clicked=self.disconnect_chatgpt)
        self.chatgpt_row.addWidget(self.connect_button, 1)
        self.chatgpt_row.addWidget(self.disconnect_button)
        form.addRow(self.chatgpt_row)
        self.key_edit = QLineEdit(echoMode=QLineEdit.EchoMode.Password, placeholderText="sk-…")
        form.addRow(tr("label.api_key"), self.key_edit)
        self.model_combo = QComboBox(editable=True)
        self.model_row = QHBoxLayout()
        self.model_row.addWidget(self.model_combo, 1)
        self.list_models_button = QPushButton(tr("btn.list_models"), clicked=self.list_models)
        self.model_row.addWidget(self.list_models_button)
        form.addRow(tr("label.model"), self.model_row)
        self.profile_combo = QComboBox()
        for key in PROFILES:
            self.profile_combo.addItem(tr(f"profile.{key}"), key)
        form.addRow(tr("label.profile"), self.profile_combo)
        self.test_button = QPushButton(tr("btn.test_ai"), clicked=self.test_ai)
        form.addRow(self.test_button)

        self._section(form, "group.context")
        self.doc_label = QLabel(tr("label.no_doc"), objectName="hint", wordWrap=True)
        form.addRow(self.doc_label)
        doc_row = QHBoxLayout()
        doc_row.addWidget(QPushButton(tr("btn.load_doc"), clicked=self.load_document), 1)
        doc_row.addWidget(QPushButton(tr("btn.clear_doc"), clicked=self.clear_document))
        form.addRow(doc_row)

        self._section(form, "group.session")
        for key, slot in (
            ("btn.notice", self.copy_notice),
            ("btn.export", self.export_session),
            ("btn.new_session", self.new_session),
            ("btn.diagnostics", self.save_diagnostics),
        ):
            form.addRow(QPushButton(tr(key), clicked=slot))
        form.addRow(QLabel(f"v{__version__} · MIT", objectName="hint"))

        # Long device or model names must not widen the sidebar.
        for combo in container.findChildren(QComboBox):
            combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            combo.setMinimumContentsLength(8)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(container)
        scroll.setMinimumWidth(320)
        return scroll

    # --------------------------------------------------------------- settings
    @staticmethod
    def _select(combo: QComboBox, value: Any) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _restore(self) -> None:
        s = self.settings
        self._select(self.engine_combo, s.capture_engine or default_engine())
        self.whisper_combo.setCurrentText(s.whisper_model)
        self._select(self.language_combo, s.speech_language)
        self._select(self.provider_combo, s.ai_provider)
        self._select(self.profile_combo, s.profile)
        self.url_edit.setText(s.ai_base_url)
        self.model_combo.setEditText(s.ai_model)
        self.key_edit.setText(api_key_from_env())
        self.sidebar.setVisible(s.sidebar_visible)

    def collect_settings(self) -> Settings:
        s = self.settings
        s.capture_engine = self.engine_combo.currentData()
        s.device_name = self.devices[self.source_combo.currentIndex()].name if self.devices else s.device_name
        s.whisper_model = self.whisper_combo.currentText()
        s.speech_language = self.language_combo.currentData()
        s.ai_provider = self.provider_combo.currentData()
        s.ai_model = self.current_model()
        s.ai_base_url = self.url_edit.text().strip()
        s.profile = self.profile_combo.currentData()
        s.sidebar_visible = self.sidebar.isVisible()
        return s

    def save_settings(self) -> None:
        if self.persist:
            with contextlib.suppress(OSError):  # settings are a convenience; never block the user
                self.collect_settings().save()

    # ---------------------------------------------------------------- devices
    def refresh_devices(self) -> None:
        if self.session and self.session.running:
            return
        engine = self.engine_combo.currentData()
        self.source_combo.clear()
        try:
            self.devices, default = self.devices_fn(engine)
        except Exception as exc:
            self.devices = []
            self.stage_label.setText(tr("status.devices_error", detail=str(exc)))
            return
        for d in self.devices:
            self.source_combo.addItem(tr("source.pc" if d.isloopback else "source.mic", name=d.name))
        if not self.devices:
            self.stage_label.setText(tr("status.no_devices"))
            return
        saved = next((i for i, d in enumerate(self.devices) if d.name == self.settings.device_name), None)
        self.source_combo.setCurrentIndex(saved if saved is not None else default)

    # --------------------------------------------------------------------- AI
    @property
    def auth(self) -> Any:
        if self._auth is None:
            from ..auth.chatgpt import ChatGPTAuth

            self._auth = ChatGPTAuth()
        return self._auth

    def provider(self) -> str:
        return self.provider_combo.currentData()

    def current_model(self) -> str:
        index = self.model_combo.currentIndex()
        text = self.model_combo.currentText().strip()
        if index >= 0 and self.model_combo.itemText(index) == text and self.model_combo.itemData(index):
            return str(self.model_combo.itemData(index))
        return text

    def on_provider_changed(self) -> None:
        key = self.provider()
        spec = PROVIDERS[key]
        enabled = key != "none"
        self.form.setRowVisible(self.url_edit, key in ("ollama", "lmstudio", "custom"))
        self.url_edit.setPlaceholderText(spec.base_url or "http://localhost:8080/v1")
        self.form.setRowVisible(self.key_edit, key in ("openai", "custom"))
        self.form.setRowVisible(self.chatgpt_row, key == "chatgpt")
        self.form.setRowVisible(self.model_row, enabled)
        self.form.setRowVisible(self.test_button, enabled)
        self.model_combo.lineEdit().setPlaceholderText(spec.model_hint)
        if key == "chatgpt":
            self._fill_chatgpt_models()
        else:
            self.model_combo.clear()
            self.model_combo.setEditText(self.settings.ai_model if self.settings.ai_provider == key else "")
        self.provider_hint.setText("" if key == "none" else tr("hint.local" if spec.local else "hint.cloud"))
        self.ai_button.setEnabled(enabled or self.demo)
        if not enabled and not self.demo:
            self.ai_button.setChecked(False)
        self._update_ai_button()
        if not (self.session and self.session.running):
            self.ai_label.setText(
                tr("ai.off") if not enabled else tr("ai.ready", provider=tr(f"provider.{key}"))
            )

    def _fill_chatgpt_models(self) -> None:
        self.model_combo.clear()
        for m in self.chatgpt_models:
            self.model_combo.addItem(m.get("display_name", m["slug"]), m["slug"])

    def make_analyzer(self, confirm_paid: bool = True) -> Any:
        key = self.provider()
        analyzer = build_analyzer(
            key,
            model=self.current_model(),
            base_url=self.url_edit.text().strip(),
            api_key=self.key_edit.text().strip() or api_key_from_env(),
            auth=self.auth if key == "chatgpt" else None,
            timeout=self.settings.ai_timeout_s,
        )
        if confirm_paid and key == "openai":
            answer = QMessageBox.question(self, tr("dialog.paid_title"), tr("dialog.paid_body"))
            if answer != QMessageBox.StandardButton.Yes:
                raise ValueError(tr("dialog.paid_title"))
        return analyzer

    def toggle_ai(self, checked: bool) -> None:
        session = self.session
        if checked and session and session.running and not self.demo:
            try:
                analyzer = self.make_analyzer()
            except ValueError as exc:
                self.ai_button.setChecked(False)
                self._update_ai_button()
                self._warn(str(exc))
                return
            session.analyzer = analyzer
            session.analysis_disabled = False
            session.ai_generation += 1
            self.ai_label.setText(tr("ai.enabled_live"))
        elif checked and session and session.running:
            session.analysis_disabled = False
            session.ai_generation += 1
            self.ai_label.setText(tr("ai.enabled_live"))
        elif session and session.running:
            session.analysis_disabled = True
            session.ai_generation += 1
            self.ai_label.setText(tr("ai.paused"))
        self._update_ai_button()

    def _update_ai_button(self) -> None:
        on = self.ai_button.isChecked()
        self.ai_button.setText(tr("btn.ai_on" if on else "btn.ai_off"))
        self.ai_button.setProperty("checked", "true" if on else "false")
        self._repolish(self.ai_button)

    def _background(self, work: Callable[[], Any], ok_kind: str, error_kind: str) -> None:
        def run() -> None:
            try:
                self.events.put((None, ok_kind, work()))
            except Exception as exc:
                self.events.put((None, error_kind, str(exc)))

        threading.Thread(target=run, daemon=True, name=ok_kind).start()

    def connect_chatgpt(self) -> None:
        self.connect_button.setEnabled(False)
        self.ai_label.setText(tr("ai.connecting"))
        registration = self.auth.registrations[-1] if self.auth.registrations else None

        def work() -> tuple[str, list[dict]]:
            if self.auth.connected:
                self.auth.logout()
            email = self.auth.login(registration)
            models = self.auth.models()
            if not models:
                raise ValueError("Your account returned no models for this connection.")
            return email, models

        self._background(work, "login_ok", "login_error")

    def disconnect_chatgpt(self) -> None:
        if self.session and self.session.running:
            return
        self._background(self.auth.logout, "logout", "logout")

    def list_models(self) -> None:
        key = self.provider()
        if key == "chatgpt":
            self._background(self.auth.models, "models_chatgpt", "ai_error")
            return
        try:
            analyzer = build_analyzer(
                key,
                model="-",
                base_url=self.url_edit.text().strip(),
                api_key=self.key_edit.text().strip() or api_key_from_env(),
            )
        except ValueError as exc:
            self._warn(str(exc))
            return
        self._background(analyzer.list_models, "models", "ai_error")

    def test_ai(self) -> None:
        try:
            analyzer = self.make_analyzer()
        except ValueError as exc:
            self._warn(str(exc))
            return
        profile = self.profile_combo.currentData()
        self.ai_label.setText(tr("ai.testing"))

        def work() -> str:
            result = parse_analysis(analyzer.analyze(instructions(profile), SAMPLE_PAYLOAD))
            if not result["conceptos"] and not result["preguntas"]:
                raise ValueError("Connected, but the model returned no concepts or answers for the sample.")
            return tr("ai.test_ok")

        self._background(work, "test_ok", "ai_error")

    # ---------------------------------------------------------------- session
    def toggle_listening(self) -> None:
        if self.session and self.session.running:
            self.stop()
        else:
            self.start()

    def _confirm_notice(self) -> bool:
        if self.settings.notice_acknowledged or self.demo:
            return True
        box = QMessageBox(self)
        box.setWindowTitle(tr("dialog.notice_title"))
        box.setText(tr("dialog.notice_body"))
        ok = box.addButton(tr("dialog.notice_ok"), QMessageBox.ButtonRole.AcceptRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.exec()
        if box.clickedButton() is ok:
            self.settings.notice_acknowledged = True
            self.save_settings()
            return True
        return False

    def build_session(self) -> Session:
        s = self.collect_settings()
        if self.demo:
            from ..demo import DemoAnalyzer, DemoDevice, DemoTranscriber

            lang = current_language()
            return Session(
                DemoTranscriber(lang),
                DemoAnalyzer(lang),
                DemoDevice(),
                profile=s.profile,
                knowledge=self.knowledge,
                events=self.events,
                interval=1.0,
            )
        if not self.devices:
            raise ValueError(tr("status.no_devices"))
        from ..stt.whisper_local import LocalTranscriber

        wanted = (s.whisper_model, s.whisper_language)
        if self.transcriber is None or (self.transcriber.model_name, self.transcriber.language) != wanted:
            self.transcriber = LocalTranscriber(*wanted)
        analyzer: Any = NoAnalyzer()
        if self.ai_button.isChecked() and s.ai_provider != "none":
            try:
                analyzer = self.make_analyzer()
            except ValueError as exc:
                self.ai_button.setChecked(False)
                self._update_ai_button()
                self._warn(str(exc))
        return Session(
            self.transcriber,
            analyzer,
            self.devices[self.source_combo.currentIndex()],
            profile=s.profile,
            knowledge=self.knowledge,
            events=self.events,
            interval=s.analysis_interval_s,
            context_budget_chars=s.context_budget_chars,
        )

    def start(self) -> None:
        if self.session and self.session.running:
            return
        if not self._confirm_notice():
            return
        try:
            session = self.build_session()
        except ValueError as exc:
            self._warn(str(exc))
            return
        if self.session:
            session.adopt_context(self.session)
        session.analysis_disabled = not self.ai_button.isChecked()
        self.session = session
        session.start()
        self.save_settings()
        self._set_live()

    def stop(self) -> None:
        if self.session and not self.session.stop.is_set():
            self.session.stop.set()
            self.stage_label.setText(tr("status.stopping"))

    def new_session(self) -> None:
        if self.session and self.session.running:
            return
        if self.session and (
            QMessageBox.question(self, tr("btn.new_session"), tr("dialog.new_session"))
            != QMessageBox.StandardButton.Yes
        ):
            return
        self.session = None
        self.concepts, self.answers = [], []
        self.transcript_view.clear()
        self._render_all()
        self.latency_label.setText("")
        self.stage_label.setText(tr("status.ready"))

    def _set_live(self) -> None:
        self.start_button.setText(tr("btn.stop"))
        self.start_button.setProperty("live", "true")
        self.on_air.setText("● " + tr("status.listening"))
        self.on_air.setProperty("live", "true")
        for w in (self.start_button, self.on_air):
            self._repolish(w)
        if self.demo:
            self.stage_label.setText(tr("status.demo"))

    def _set_idle(self) -> None:
        self.start_button.setText(tr("btn.start"))
        self.start_button.setProperty("live", "false")
        self.on_air.setText("○ " + (tr("status.paused") if self.session else tr("status.ready")))
        self.on_air.setProperty("live", "false")
        for w in (self.start_button, self.on_air):
            self._repolish(w)
        self.meter.setValue(0)

    @staticmethod
    def _repolish(widget: QWidget) -> None:
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    # ------------------------------------------------------------------ events
    def poll(self) -> None:
        for _ in range(200):  # bounded so the UI stays responsive under bursts
            try:
                source, kind, value = self.events.get_nowait()
            except queue.Empty:
                break
            if source is None:
                self._on_background(kind, value)
            elif source is self.session:
                self._on_session(kind, value)

    def _on_background(self, kind: str, value: Any) -> None:
        if kind == "login_ok":
            email, self.chatgpt_models = value
            self.connect_button.setEnabled(True)
            if self.provider() == "chatgpt":
                self._fill_chatgpt_models()
            self.ai_label.setText(tr("ai.connected", email=email))
        elif kind == "login_error":
            self.connect_button.setEnabled(True)
            self.ai_label.setText(value)
            self._warn(value)
        elif kind == "logout":
            self.chatgpt_models = []
            self.model_combo.clear()
            self.ai_label.setText(tr("ai.disconnected" if value is True else "ai.disconnected_unconfirmed"))
        elif kind in ("models", "models_chatgpt"):
            current = self.model_combo.currentText()
            if kind == "models_chatgpt":
                self.chatgpt_models = value
                self._fill_chatgpt_models()
            else:
                self.model_combo.clear()
                self.model_combo.addItems(value)
                self.model_combo.setEditText(current)
            self.ai_label.setText(tr("ai.models_found", n=len(value)))
        elif kind == "test_ok":
            self.ai_label.setText(value)
        elif kind == "ai_error":
            self.ai_label.setText(value)
            self._warn(value)

    def _on_session(self, kind: str, value: Any) -> None:
        if kind == "audio_level":
            self.meter.setValue(min(100, int(value * 1000)))
            if not self.demo:
                self.stage_label.setText(
                    tr("status.silence") if value < 1e-5 else tr("status.level", level=value)
                )
        elif kind == "stage":
            if not self.demo:
                self.stage_label.setText(tr_message(value))
        elif kind == "ai_stage":
            self.ai_label.setText(tr_message(value))
        elif kind == "error":
            text = tr_message(value)
            self.stage_label.setText(text)
            self.transcript_view.append(f'<p style="color:{theme.DANGER}">⚠ {html.escape(text)}</p>')
        elif kind == "transcript":
            self._append_transcript(value)
        elif kind == "concept":
            self.concepts.insert(0, value)
            self._render_concepts()
        elif kind == "question":
            self.answers.insert(0, value)
            self._render_answers()
        elif kind == "latency":
            summary = self.session.latency_summary() if self.session else {}
            self.latency_label.setText(
                tr(
                    "status.latency",
                    stt=_fmt_seconds(summary.get("stt", {}).get("p50")),
                    ai=_fmt_seconds(summary.get("ai", {}).get("p50")),
                    e2e=_fmt_seconds(summary.get("e2e", {}).get("p50")),
                )
            )
        elif kind == "done":
            self._set_idle()
            self.stage_label.setText(tr("status.paused"))

    # --------------------------------------------------------------- rendering
    def _render_all(self) -> None:
        self._render_concepts()
        self._render_answers()
        if not self.transcript_view.toPlainText():
            self.transcript_view.setHtml(
                f'{theme.CARD_CSS}<p class="muted">{html.escape(tr("panel.transcript_empty"))}</p>'
            )

    def _render_concepts(self) -> None:
        if not self.concepts:
            body = f'<p class="muted">{html.escape(tr("panel.concepts_empty"))}</p>'
        else:
            body = "".join(
                f'<p class="term">{html.escape(c["termino"])}</p>'
                f'<p class="body">{html.escape(c["explicacion"])}</p><br>'
                for c in self.concepts
            )
        self.concepts_view.setHtml(theme.CARD_CSS + body)

    def _render_answers(self) -> None:
        if not self.answers:
            body = f'<p class="muted">{html.escape(tr("panel.answers_empty"))}</p>'
        else:
            parts = []
            for q in self.answers:
                part = (
                    f'<p class="question">{html.escape(q["pregunta"])}</p>'
                    f'<p class="label">{html.escape(tr("answer.reply"))}</p>'
                    f'<p class="say">{html.escape(q["breve"])}</p>'
                )
                if q.get("detalle"):
                    part += f'<p class="body">{html.escape(str(q["detalle"]))}</p>'
                if q.get("faltan"):
                    part += (
                        f'<p class="muted">{html.escape(tr("answer.missing"))}: '
                        f"{html.escape(str(q['faltan']))}</p>"
                    )
                parts.append(part + "<br>")
            body = "".join(parts)
        self.answers_view.setHtml(theme.CARD_CSS + body)

    def _append_transcript(self, entry: dict) -> None:
        first = self.session is not None and len(self.session.transcript) == 1
        if first or self.transcript_view.document().blockCount() > MAX_TRANSCRIPT_LINES:
            self.transcript_view.clear()  # drop the empty-state hint, or old lines
        self.transcript_view.append(
            f'<p><span style="color:{theme.MUTED}">{html.escape(entry["hora"])}</span>&nbsp;&nbsp;'
            f"{html.escape(entry['texto'])}</p>"
        )

    # ------------------------------------------------------------------ actions
    def toggle_sidebar(self) -> None:
        self.sidebar.setVisible(not self.sidebar.isVisible())

    def copy_notice(self) -> None:
        key = self.provider()
        ai_part = "" if PROVIDERS[key].local else tr("notice.ai_part", provider=tr(f"provider.{key}"))
        QGuiApplication.clipboard().setText(tr("notice.text", ai_part=ai_part))
        self.stage_label.setText(tr("notice.copied"))

    def load_document(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, tr("dialog.doc_title"), "", "Text (*.txt *.md)")
        if not path:
            return
        try:
            knowledge = KnowledgeBase(Path(path).read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            self._warn(str(exc))
            return
        self.knowledge, self.doc_name = knowledge, Path(path).name
        if self.session:
            self.session.knowledge = knowledge
        self.doc_label.setText(tr("label.doc_loaded", name=self.doc_name, passages=len(knowledge.passages)))

    def clear_document(self) -> None:
        self.knowledge, self.doc_name = KnowledgeBase(""), ""
        if self.session:
            self.session.knowledge = self.knowledge
        self.doc_label.setText(tr("label.no_doc"))

    def export_session(self) -> None:
        if not self.session:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, tr("dialog.export_title"), "escuchator-session.md", "Markdown (*.md);;JSON (*.json)"
        )
        if not path:
            return
        text = session_to_json(self.session) if path.endswith(".json") else session_to_markdown(self.session)
        try:
            Path(path).write_text(text, encoding="utf-8")
            self.stage_label.setText(tr("export.saved", path=path))
        except OSError as exc:
            self._warn(str(exc))

    def save_diagnostics(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, tr("dialog.diag_title"), "escuchator-diagnostics.json", "JSON (*.json)"
        )
        if not path:
            return
        try:
            Path(path).write_text(diagnostics_report(self.collect_settings(), self.session), encoding="utf-8")
            self.stage_label.setText(tr("diag.saved"))
        except OSError as exc:
            self._warn(str(exc))

    def _warn(self, text: str) -> None:
        QMessageBox.warning(self, tr("error.title"), text)

    def closeEvent(self, event: QCloseEvent) -> None:
        self.save_settings()
        if self.session:
            self.session.stop.set()
            self.session.cancel.set()
        super().closeEvent(event)
