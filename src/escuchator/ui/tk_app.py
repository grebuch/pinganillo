"""Tkinter user interface (kept until the Qt UI lands)."""

import json
import os
import queue
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from ..audio.devices import list_devices
from ..auth.chatgpt import ChatGPTAuth
from ..llm.analyzers import ChatGPTPlanAnalyzer, NoAnalyzer, OpenAICompatibleAnalyzer
from ..llm.parsing import parse_analysis
from ..llm.prompt import instructions
from ..pipeline import Session
from ..stt.whisper_local import LocalTranscriber


class App:
    def __init__(self, root):
        self.root, self.events, self.session = root, queue.Queue(), None
        self.knowledge, self.devices, self.windows = "", [], {}
        self.auth = ChatGPTAuth()
        self.local_transcriber = LocalTranscriber()
        self.model_catalog = []
        self.auth_busy = False
        root.title("Escuchator 0.5 · Copiloto en directo")
        root.geometry("1250x820")
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TButton", padding=8)
        header = ttk.Frame(root, padding=14)
        header.pack(fill="x")
        ttk.Label(header, text="ESCUCHATOR 0.5", font=("Segoe UI", 22, "bold")).pack(side="left")
        ttk.Label(header, text="Conceptos claros. Respuestas con contexto.", padding=15).pack(side="left")
        setup = ttk.Frame(root, padding=10)
        setup.pack(fill="x")
        self.mode = ttk.Combobox(
            setup,
            state="readonly",
            values=["Plan ChatGPT + transcripción local", "API de pago (opcional)"],
            width=38,
        )
        self.mode["values"] = [
            "Plan ChatGPT + transcripción local",
            "API de pago (opcional)",
            "Solo transcripción local (diagnóstico)",
        ]
        self.mode.current(2)
        self.mode.grid(row=0, column=0, columnspan=2, sticky="w")
        self.login_button = ttk.Button(setup, text="Continue with ChatGPT", command=self.login)
        self.login_button.grid(row=0, column=2)
        ttk.Button(setup, text="Desconectar", command=self.logout).grid(row=0, column=3)
        ttk.Label(setup, text="Cuenta registrada:").grid(row=3, column=0, sticky="w")
        self.account = ttk.Combobox(setup, state="readonly", width=48)
        self.account.grid(row=3, column=1, sticky="w")
        self.update_accounts()
        ttk.Label(setup, text="Modelo de tu plan:").grid(row=4, column=0, sticky="w")
        self.model_choice = ttk.Combobox(setup, state="readonly", width=48)
        self.model_choice.grid(row=4, column=1, sticky="w")
        ttk.Label(setup, text="Clave API (solo modo de pago):").grid(row=5, column=0, sticky="w")
        self.key = tk.StringVar(value="")
        ttk.Entry(setup, textvariable=self.key, show="•", width=48).grid(row=5, column=1, sticky="w")
        ttk.Label(setup, text="No se usa en modo Plan ChatGPT.").grid(row=5, column=2, padx=10)
        ttk.Label(setup, text="Fuente de audio:").grid(row=1, column=0, sticky="w")
        self.source = ttk.Combobox(setup, state="readonly", width=65)
        self.source.grid(row=1, column=1, columnspan=2, sticky="w", pady=8)
        ttk.Label(setup, text="Motor de captura:").grid(row=6, column=0, sticky="w")
        self.engine = ttk.Combobox(
            setup,
            state="readonly",
            values=["WASAPI nativo (recomendado)", "SoundCard (alternativo)"],
            width=42,
        )
        self.engine.current(0 if os.name == "nt" else 1)
        self.engine.grid(row=6, column=1, sticky="w")
        self.engine.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        ttk.Label(setup, text="Modelo de transcripción:").grid(row=7, column=0, sticky="w")
        self.speech_model = ttk.Combobox(
            setup, state="readonly", values=["small", "medium", "base"], width=20
        )
        self.speech_model.current(0)
        self.speech_model.grid(row=7, column=1, sticky="w")
        ttk.Label(setup, text="Idioma del audio:").grid(row=7, column=2, sticky="w")
        self.speech_language = ttk.Combobox(
            setup, state="readonly", values=["Castellano", "Català", "English", "Automático"], width=18
        )
        self.speech_language.current(0)
        self.speech_language.grid(row=7, column=3, sticky="w")
        ttk.Button(setup, text="Actualizar dispositivos", command=self.refresh).grid(row=1, column=3)
        ttk.Label(setup, text="Perfil experto:").grid(row=2, column=0, sticky="w")
        self.profile = ttk.Combobox(
            setup,
            values=["General", "CTO / CIO · IT y estrategia", "Ciberseguridad", "Empresa y finanzas"],
            width=40,
        )
        self.profile.set("CTO / CIO · IT y estrategia")
        self.profile.grid(row=2, column=1, sticky="w")
        ttk.Button(setup, text="Cargar contexto .txt / .md", command=self.load).grid(row=2, column=2)
        controls = ttk.Frame(root, padding=10)
        controls.pack(fill="x")
        self.start_button = ttk.Button(controls, text="▶ Escucha", command=self.start)
        self.start_button.pack(side="left")
        ttk.Button(controls, text="■ Pausar / terminar", command=self.pause).pack(side="left", padx=8)
        ttk.Button(controls, text="Nueva sesión", command=self.reset).pack(side="left")
        ttk.Button(controls, text="Exportar sesión", command=self.export).pack(side="left", padx=8)
        ttk.Button(controls, text="Probar IA sin audio", command=self.test_ai).pack(side="left")
        ttk.Button(controls, text="Guardar diagnóstico", command=self.diagnostics).pack(side="left", padx=8)
        ai_controls = ttk.Frame(root, padding=4)
        ai_controls.pack(fill="x")
        ttk.Button(ai_controls, text="Activar IA sin parar transcripción", command=self.enable_ai).pack(
            side="left"
        )
        ttk.Button(ai_controls, text="Pausar IA", command=self.pause_ai).pack(side="left", padx=8)
        self.status = tk.StringVar(value="Listo · Ctrl+Espacio para escuchar o pausar")
        ttk.Label(root, textvariable=self.status, padding=10).pack(fill="x")
        self.audio_status = tk.StringVar(value="Audio: sin iniciar")
        ttk.Label(root, textvariable=self.audio_status, padding=5).pack(fill="x")
        self.audio_meter = ttk.Progressbar(root, maximum=100)
        self.audio_meter.pack(fill="x", padx=12)
        self.ai_status = tk.StringVar(
            value="IA desactivada en modo diagnóstico. La transcripción funciona sin cuenta."
        )
        ttk.Label(root, textvariable=self.ai_status, padding=5).pack(fill="x")
        panes = ttk.Panedwindow(root, orient="horizontal")
        panes.pack(fill="both", expand=True, padx=12)
        self.boxes = {}
        for name, title in [("concept", "¿De qué están hablando?"), ("question", "¿Qué puedo responder?")]:
            frame = ttk.Frame(panes)
            panes.add(frame, weight=1)
            ttk.Label(frame, text=title, font=("Segoe UI", 15, "bold")).pack(anchor="w", pady=6)
            ttk.Button(frame, text="Abrir en otra pantalla", command=lambda n=name: self.detach(n)).pack(
                anchor="w"
            )
            self.boxes[name] = self.textbox(frame)
        ttk.Label(root, text="Transcripción en directo", padding=8).pack(anchor="w")
        self.boxes["transcript"] = self.textbox(root, height=7)
        root.bind(
            "<Control-space>",
            lambda e: self.pause() if self.session and not self.session.stop.is_set() else self.start(),
        )
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.refresh()
        root.after(100, self.poll)

    def update_accounts(self):
        records = self.auth.config["registrations"]
        self.account["values"] = ["Añadir cuenta"] + [
            r.get("email", "") + " · " + r["client_id"][-8:] for r in records
        ]
        self.account.current(0)

    def login(self):
        if self.auth_busy:
            return
        if (
            self.session
            and not self.session.analysis_disabled
            and not isinstance(self.session.analyzer, NoAnalyzer)
        ):
            messagebox.showinfo("IA activa", "Pulsa Pausar IA antes de reconectar la cuenta.")
            return
        self.auth_busy = True
        self.login_button.configure(state="disabled")
        index = self.account.current()
        record = self.auth.config["registrations"][index - 1] if index > 0 else None
        self.status.set("Completa la conexión y el permiso de uso del plan en tu navegador…")

        def worker():
            try:
                if self.auth.tokens:
                    if not self.auth.logout():
                        raise ValueError(
                            "No se confirmó la revocación anterior. Desconecta Escucha en Ajustes de ChatGPT y vuelve a conectar."
                        )
                email = self.auth.login(record)
                models = self.auth.models()
                if not models:
                    raise ValueError("Tu cuenta no devuelve modelos disponibles para esta conexión.")
                self.events.put((None, "login_ok", (email, models)))
            except Exception as exc:
                self.events.put((None, "login_error", str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def logout(self):
        if self.auth_busy or (self.session and any(t.is_alive() for t in self.session.threads)):
            messagebox.showinfo("Conexión", "Pausa y espera al procesamiento antes de desconectar.")
            return
        self.auth_busy = True

        def worker():
            confirmed = self.auth.logout()
            self.events.put((None, "logout", confirmed))

        threading.Thread(target=worker, daemon=True).start()

    def textbox(self, parent, height=12):
        box = ScrolledText(
            parent,
            wrap="word",
            font=("Segoe UI", 11),
            height=height,
            bg="#101c30",
            fg="#e9f0fa",
            padx=12,
            pady=12,
            state="disabled",
        )
        box.pack(fill="both", expand=True, padx=4, pady=4)
        return box

    def write(self, box, text):
        box.configure(state="normal")
        box.insert("end", text)
        box.see("end")
        box.configure(state="disabled")

    def refresh(self):
        if self.session and any(t.is_alive() for t in self.session.threads):
            messagebox.showinfo("Audio", "Pausa y espera antes de cambiar dispositivos.")
            return
        try:
            self.devices, index = list_devices("wasapi" if self.engine.current() == 0 else "soundcard")
            self.source["values"] = [
                ("Audio del PC · " if d.isloopback else "Micrófono · ") + d.name for d in self.devices
            ]
            if self.devices:
                self.source.current(index)
            else:
                self.source.set("")
                self.status.set("No hay fuentes disponibles. Revisa los dispositivos de Windows.")
        except Exception as exc:
            self.devices = []
            self.source.set("")
            self.status.set("No se pudo acceder al audio: " + str(exc) + " · prueba el motor alternativo")

    def enable_ai(self):
        if not self.session or not any(t.is_alive() for t in self.session.threads):
            messagebox.showinfo("IA", "Inicia primero la escucha en modo local.")
            return
        if not self.auth.tokens or self.model_choice.current() < 0 or self.auth_busy:
            messagebox.showinfo(
                "IA", "Conecta ChatGPT y elige un modelo. La transcripción puede seguir mientras conectas."
            )
            return
        current = self.session.analyzer
        if hasattr(current, "guard") and current.guard.worker and current.guard.worker.is_alive():
            messagebox.showinfo(
                "IA", "La petición anterior aún no ha cerrado su conexión. Espera unos segundos."
            )
            return
        self.session.analyzer = ChatGPTPlanAnalyzer(
            self.auth, self.model_catalog[self.model_choice.current()]["slug"]
        )
        self.session.analysis_disabled = False
        self.session.ai_generation += 1
        self.ai_status.set("IA activada · analizará los próximos fragmentos sin reiniciar el audio")

    def pause_ai(self):
        if self.session:
            self.session.analysis_disabled = True
            self.session.ai_generation += 1
        self.ai_status.set(
            "IA pausada · se mantiene la transcripción. Una petición ya enviada puede completar en segundo plano."
        )

    def test_ai(self):
        if self.auth_busy:
            return
        if (
            self.session
            and not self.session.analysis_disabled
            and not isinstance(self.session.analyzer, NoAnalyzer)
        ):
            messagebox.showinfo(
                "Prueba IA", "Pulsa Pausar IA antes de probar; la transcripción puede seguir."
            )
            return
        if not self.auth.tokens or self.model_choice.current() < 0:
            messagebox.showinfo(
                "Prueba IA",
                "Selecciona modo Plan ChatGPT, conecta y elige modelo. Esta prueba no utiliza API de pago.",
            )
            return
        analyzer = ChatGPTPlanAnalyzer(self.auth, self.model_catalog[self.model_choice.current()]["slug"])
        self.ai_status.set("Probando IA con texto de ejemplo, sin capturar audio…")
        self.auth_busy = True

        def worker():
            try:
                payload = json.dumps(
                    {
                        "fragmento_nuevo": "Estamos hablando de copias de seguridad. ¿Qué significa RTO?",
                        "resumen_anterior": "",
                        "contexto_reciente": [],
                        "documentacion": "",
                    }
                )
                result = parse_analysis(analyzer.analyze(instructions("IT"), payload))
                if not result["conceptos"] and not result["preguntas"]:
                    raise ValueError("Conecta, pero no devuelve conceptos o respuestas al ejemplo.")
                self.events.put((None, "ai_test_ok", "IA conectada y respuesta estructurada correcta."))
            except Exception as exc:
                self.events.put((None, "ai_test_error", str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def diagnostics(self):
        import importlib.metadata
        import platform

        path = filedialog.asksaveasfilename(
            defaultextension=".json", initialfile="diagnostico-escuchator.json"
        )
        if not path:
            return
        packages = {}
        for name in [
            "numpy",
            "scipy",
            "SoundCard",
            "PyAudioWPatch",
            "faster-whisper",
            "ctranslate2",
            "av",
            "openai",
        ]:
            try:
                packages[name] = importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:
                packages[name] = "no instalado"
        data = {
            "version": "0.5",
            "platform": platform.system() + " " + platform.release(),
            "python": platform.python_version(),
            "packages": packages,
            "engine": self.engine.get(),
            "device": self.source.get(),
            "mode": self.mode.get(),
            "audio_status": self.audio_status.get(),
            "chatgpt_connected": bool(self.auth.tokens),
            "metrics": self.session.metrics.copy() if self.session else {},
            "session_has_errors": bool(self.session and self.session.errors),
            "ai_diagnostic": self.session.last_ai_diagnostic.copy() if self.session else {},
            "audio_queue": self.session.audio.qsize() if self.session else 0,
            "analysis_queue": self.session.analysis.qsize() if self.session else 0,
            "note": "No contiene audio, transcripción, documentos, email ni credenciales. Los errores concretos se consultan en pantalla.",
        }
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            messagebox.showinfo(
                "Diagnóstico", "Diagnóstico guardado sin audio, transcripciones ni credenciales."
            )
        except OSError as exc:
            messagebox.showerror("Diagnóstico", str(exc))

    def load(self):
        path = filedialog.askopenfilename(filetypes=[("Texto y Markdown", "*.txt *.md")])
        if path:
            try:
                with open(path, encoding="utf-8-sig") as f:
                    content = f.read(40001)
                if len(content) > 40000:
                    raise ValueError("Máximo 40.000 caracteres; carga un documento más corto.")
                self.knowledge = content
                self.status.set("Contexto cargado para la próxima sesión: " + os.path.basename(path))
            except Exception as exc:
                messagebox.showerror("Contexto", str(exc))

    def start(self):
        if self.session and any(t.is_alive() for t in self.session.threads):
            return
        if self.auth_busy:
            messagebox.showinfo("Conexión", "Espera a que termine la prueba o conexión de IA.")
            return
        if self.source.current() < 0 or not self.devices:
            messagebox.showinfo("Configuración", "Selecciona una fuente de audio.")
            return
        plan_mode = self.mode.current() == 0
        local_only = self.mode.current() == 2
        selected_language = {"Castellano": "es", "Català": "ca", "English": "en", "Automático": None}[
            self.speech_language.get()
        ]
        if (self.local_transcriber.model_name, self.local_transcriber.language) != (
            self.speech_model.get(),
            selected_language,
        ):
            self.local_transcriber = LocalTranscriber(self.speech_model.get(), selected_language)
        if local_only:
            transcriber, analyzer = self.local_transcriber, NoAnalyzer()
        elif plan_mode:
            if not self.auth.tokens or self.model_choice.current() < 0:
                messagebox.showinfo(
                    "Conexión", "Pulsa Continue with ChatGPT y selecciona un modelo de tu plan."
                )
                return
            transcriber = self.local_transcriber
            analyzer = ChatGPTPlanAnalyzer(self.auth, self.model_catalog[self.model_choice.current()]["slug"])
        else:
            if not self.key.get().strip():
                messagebox.showinfo("API", "Introduce una clave API para el modo de pago.")
                return
            if not messagebox.askyesno(
                "API de pago",
                "Has seleccionado API de pago. Esta sesión genera costes aparte de ChatGPT. ¿Iniciar?",
            ):
                return
            transcriber, analyzer = (
                self.local_transcriber,
                OpenAICompatibleAnalyzer("https://api.openai.com/v1", "gpt-4.1-mini", self.key.get().strip()),
            )
        previous = self.session
        self.session = Session(
            transcriber,
            analyzer,
            self.devices[self.source.current()],
            self.profile.get(),
            self.knowledge,
            self.events,
        )
        if previous:
            self.session.adopt_context(previous)
        self.start_button.configure(state="disabled")
        self.status.set(
            "● Solo transcripción local · no se envía nada a la IA"
            if local_only
            else (
                "● Escuchando · transcripción local · análisis con tu plan"
                if plan_mode
                else "● Escuchando · API de pago activa"
            )
        )
        self.ai_status.set(
            "IA desactivada · solo transcripción local"
            if local_only
            else "IA preparada · esperando transcripción"
        )
        self.session.start()

    def pause(self):
        if self.session and not self.session.stop.is_set():
            self.session.stop.set()
            self.status.set("Pausando · completando bloques pendientes…")

    def reset(self):
        if self.session and any(t.is_alive() for t in self.session.threads):
            messagebox.showinfo(
                "Sesión", "Pausa y espera a que termine el procesamiento antes de iniciar una nueva sesión."
            )
            return
        if self.session and not messagebox.askyesno(
            "Nueva sesión",
            "¿Borrar el contexto y la transcripción de esta sesión? Exporta antes si quieres conservarlos.",
        ):
            return
        self.session = None
        for box in list(self.boxes.values()) + [item[1] for item in self.windows.values()]:
            box.configure(state="normal")
            box.delete("1.0", "end")
            box.configure(state="disabled")
        self.status.set("Nueva sesión lista")

    def detach(self, name):
        if name in self.windows:
            self.windows[name][0].lift()
            return
        window = tk.Toplevel(self.root)
        window.title("Escucha · " + ("Conceptos" if name == "concept" else "Respuestas"))
        window.geometry("700x750")
        box = self.textbox(window)
        self.write(box, self.boxes[name].get("1.0", "end"))
        self.windows[name] = (window, box)
        window.protocol("WM_DELETE_WINDOW", lambda: (self.windows.pop(name, None), window.destroy()))

    def export(self):
        if not self.session:
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".json", initialfile="sesion-escucha.json", filetypes=[("Sesión JSON", "*.json")]
        )
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(
                        {
                            "transcripcion": self.session.transcript,
                            "resumen": self.session.summary,
                            "conceptos": list(self.session.concepts.values()),
                            "respuestas": self.boxes["question"].get("1.0", "end"),
                        },
                        f,
                        ensure_ascii=False,
                        indent=2,
                    )
                self.status.set("Sesión exportada")
            except OSError as exc:
                messagebox.showerror("Exportación", str(exc))

    def poll(self):
        while True:
            try:
                session, kind, value = self.events.get_nowait()
            except queue.Empty:
                break
            if session is None:
                self.auth_busy = False
                self.login_button.configure(state="normal")
                if kind in ("ai_test_ok", "ai_test_error"):
                    self.ai_status.set(value)
                    if kind == "ai_test_error":
                        messagebox.showerror("Prueba IA", value)
                elif kind == "login_ok":
                    email, self.model_catalog = value
                    self.model_choice["values"] = [
                        m.get("display_name", m["slug"]) for m in self.model_catalog
                    ]
                    self.model_choice.current(0)
                    self.update_accounts()
                    index = next(
                        (
                            i + 1
                            for i, r in enumerate(self.auth.config["registrations"])
                            if r["client_id"] == self.auth.client_id
                        ),
                        0,
                    )
                    self.account.current(index)
                    self.status.set("Conectado: " + email + " · se usará tu plan ChatGPT")
                elif kind == "login_error":
                    self.status.set("Conexión: " + value)
                    messagebox.showerror("ChatGPT", value + "\nNo se activará ninguna API de pago.")
                elif kind == "logout":
                    self.model_catalog = []
                    self.model_choice.set("")
                    self.status.set(
                        "Desconectado"
                        if value
                        else "Desconectado localmente; revocación remota no confirmada. Desconecta Escucha en Ajustes de ChatGPT."
                    )
                continue
            if session is not self.session:
                continue
            if kind == "audio_level":
                level = value
                self.audio_meter["value"] = min(100, level * 1000)
                self.audio_status.set(
                    "Audio recibido · nivel %.4f%s"
                    % (
                        level,
                        " · casi silencio: revisa los altavoces elegidos en Teams" if level < 0.00001 else "",
                    )
                )
            elif kind == "ai_stage":
                self.ai_status.set(value)
            elif kind == "stage":
                self.status.set(value)
            elif kind == "error":
                self.status.set(value)
                self.write(self.boxes["transcript"], "\n[ERROR] " + value + "\n")
            elif kind == "done":
                self.start_button.configure(state="normal")
                self.status.set(
                    "En pausa · revisa los errores en Transcripción si los hay; pulsa Escucha para continuar"
                )
            else:
                if kind == "transcript":
                    rendered = f"[{value['hora']}] {value['texto']}\n\n"
                elif kind == "concept":
                    rendered = f"{value['termino'].upper()}\n{value['explicacion']}\n\n"
                else:
                    rendered = f"PREGUNTA: {value['pregunta']}\n\nPARA INTERVENIR: {value['breve']}\n\n{value.get('detalle', '')}\n"
                    if value.get("faltan"):
                        rendered += "POR CONFIRMAR: " + str(value["faltan"]) + "\n"
                    rendered += "\n─────────────────────────\n\n"
                self.write(self.boxes[kind], rendered)
                if kind in self.windows:
                    self.write(self.windows[kind][1], rendered)
        if (
            self.session
            and not self.session.stop.is_set()
            and time.monotonic() - self.session.last_audio > 10
        ):
            self.audio_status.set(
                "No llegan bloques de audio. Comprueba que la fuente elegida coincide con la salida de Teams."
            )
        self.root.after(100, self.poll)

    def close(self):
        if self.session:
            self.session.stop.set()
            self.session.cancel.set()
        self.root.destroy()


def main():
    App(tk.Tk())
    tk.mainloop()
