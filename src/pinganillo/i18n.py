"""Tiny translation layer (English and Spanish).

The pipeline emits message keys with parameters, never sentences, so every
thread can stay UI-agnostic. Adding a language means adding one dictionary:
see CONTRIBUTING.md.
"""

from __future__ import annotations

import locale
from typing import Any

EN: dict[str, str] = {
    "app.tagline": "Live meeting copilot · local-first",
    # buttons
    "btn.start": "Start listening",
    "btn.stop": "Stop",
    "btn.new_session": "New session",
    "btn.ai_on": "AI analysis: on",
    "btn.ai_off": "AI analysis: off",
    "btn.export": "Export…",
    "btn.diagnostics": "Save diagnostics…",
    "btn.notice": "Copy meeting notice",
    "btn.refresh": "Refresh",
    "btn.load_doc": "Load reference document…",
    "btn.clear_doc": "Remove",
    "btn.connect_chatgpt": "Continue with ChatGPT",
    "btn.disconnect": "Disconnect",
    "btn.test_ai": "Test AI",
    "btn.list_models": "List models",
    "btn.settings": "Settings",
    "group.session": "Session",
    "hint.local": "Local: nothing leaves this PC.",
    "hint.cloud": "Cloud: short text excerpts are sent to this provider. Audio never is.",
    # settings
    "group.audio": "Audio",
    "group.transcription": "Transcription · always on this PC",
    "group.ai": "AI analysis",
    "group.context": "Context",
    "label.engine": "Capture engine",
    "label.source": "Source",
    "label.whisper_model": "Whisper model",
    "label.speech_language": "Spoken language",
    "label.provider": "Provider",
    "label.server_url": "Server URL",
    "label.model": "Model",
    "label.api_key": "API key",
    "label.profile": "Expertise",
    "label.no_doc": "No document loaded",
    "label.doc_loaded": "{name} · {passages} passages",
    "engine.wasapi": "WASAPI (recommended)",
    "engine.soundcard": "SoundCard (alternative)",
    "source.pc": "PC audio · {name}",
    "source.mic": "Microphone · {name}",
    "speech.es": "Spanish",
    "speech.ca": "Catalan",
    "speech.en": "English",
    "speech.auto": "Auto-detect",
    "profile.general": "General",
    "profile.it": "CTO / CIO · IT and strategy",
    "profile.security": "Cybersecurity",
    "profile.business": "Business and finance",
    "provider.none": "Transcription only · nothing leaves this PC",
    "provider.ollama": "Ollama · local",
    "provider.lmstudio": "LM Studio · local",
    "provider.chatgpt": "ChatGPT plan",
    "provider.openai": "OpenAI API · your key, billed",
    "provider.custom": "Other OpenAI-compatible server",
    # panels
    "panel.concepts": "What are they talking about?",
    "panel.answers": "What could I answer?",
    "panel.transcript": "Live transcript",
    "panel.concepts_empty": "Concepts explained by the AI will appear here.",
    "panel.answers_empty": "Detected questions and suggested replies will appear here.",
    "panel.transcript_empty": "Press Start and play some speech.",
    "answer.reply": "Say",
    "answer.missing": "To confirm",
    # status
    "status.ready": "Ready",
    "status.listening": "Listening",
    "status.stopping": "Stopping · finishing pending audio…",
    "status.paused": "Paused · press Start to continue",
    "status.silence": "Silence on this output",
    "status.level": "Audio level {level:.3f}",
    "status.no_devices": "No audio sources found.",
    "status.devices_error": "Could not list audio devices: {detail}",
    "status.latency": "Text {stt} · AI {ai} · Speech → hint {e2e}",
    "status.demo": "Demo mode · scripted meeting, no audio, no AI",
    # AI
    "ai.off": "AI off · nothing leaves this PC",
    "ai.ready": "AI ready · {provider}",
    "ai.connected": "Connected: {email}",
    "ai.connecting": "Complete the sign-in in your browser…",
    "ai.disconnected": "Disconnected",
    "ai.disconnected_unconfirmed": "Disconnected locally; remote revocation not confirmed.",
    "ai.testing": "Testing the AI with a sample text (no audio)…",
    "ai.test_ok": "The AI works: structured answer received.",
    "ai.models_found": "{n} models found",
    "ai.waiting": "Waiting for the AI · {seconds} s (limit {limit} s)",
    "ai.asking": "Asking the AI…",
    "ai.answered": "AI answered · waiting for new speech",
    "ai.paused_error": "AI paused after an error · transcription keeps running",
    "ai.paused": "AI paused · transcription keeps running",
    "ai.enabled_live": "AI on · analysing upcoming speech",
    # pipeline stages
    "stage.loading_whisper": "Loading Whisper · the first download can take a few minutes…",
    "stage.whisper_ready": "Whisper ready · waiting for speech",
    "stage.transcribing": "Transcribing…",
    "stage.slower_than_realtime": "Transcription is slower than real time · try a smaller model",
    "stage.no_words": "Audio received, no words recognised",
    # errors
    "error.capture": "Audio capture failed: {detail}",
    "error.falling_behind": "Transcription is falling behind: an audio chunk was skipped. Try a smaller model.",
    "error.whisper_load": "Could not load Whisper: {detail}",
    "error.transcription": "Transcription error: {detail}",
    "error.analysis": "AI analysis paused: {detail}. Local transcription continues.",
    "error.title": "Pinganillo",
    # dialogs
    "dialog.notice_title": "Before you start",
    "dialog.notice_body": (
        "Pinganillo transcribes what your computer plays, including other people's voices.\n\n"
        "• Tell the other participants before using it. Recording and transcription laws differ "
        "between countries; in some places everyone must consent.\n"
        "• With a local provider (or transcription only) nothing leaves this PC. With a cloud "
        "provider, short text excerpts are sent to that provider.\n"
        "• Suggestions can be wrong. Verify before you rely on them.\n\n"
        "Use 'Copy meeting notice' to tell participants in one click."
    ),
    "dialog.notice_ok": "I understand",
    "dialog.paid_title": "Billed provider",
    "dialog.paid_body": "This provider bills your API account separately from any subscription. Continue?",
    "dialog.new_session": "Clear the transcript and suggestions? Export first if you want to keep them.",
    "dialog.export_title": "Export session",
    "dialog.doc_title": "Load reference document (.txt / .md)",
    "dialog.diag_title": "Save diagnostics",
    "notice.text": (
        "Heads-up: I'm using Pinganillo, an open-source assistant that transcribes this call on my "
        "computer to help me follow it.{ai_part} Tell me if you'd rather I turn it off."
    ),
    "notice.ai_part": " Short text excerpts are analysed by {provider}.",
    "notice.copied": "Meeting notice copied to the clipboard.",
    "export.saved": "Session exported to {path}",
    "export.heading_transcript": "Transcript",
    "export.heading_concepts": "Concepts",
    "export.heading_questions": "Questions and suggested replies",
    "export.heading_summary": "Summary",
    "diag.saved": "Diagnostics saved (no audio, no transcript, no credentials).",
}

ES: dict[str, str] = {
    "app.tagline": "Copiloto de reuniones en directo · local primero",
    "btn.start": "Empezar a escuchar",
    "btn.stop": "Detener",
    "btn.new_session": "Nueva sesión",
    "btn.ai_on": "Análisis IA: activado",
    "btn.ai_off": "Análisis IA: desactivado",
    "btn.export": "Exportar…",
    "btn.diagnostics": "Guardar diagnóstico…",
    "btn.notice": "Copiar aviso para la reunión",
    "btn.refresh": "Actualizar",
    "btn.load_doc": "Cargar documento de referencia…",
    "btn.clear_doc": "Quitar",
    "btn.connect_chatgpt": "Continue with ChatGPT",
    "btn.disconnect": "Desconectar",
    "btn.test_ai": "Probar IA",
    "btn.list_models": "Ver modelos",
    "btn.settings": "Ajustes",
    "group.session": "Sesión",
    "hint.local": "Local: nada sale de este PC.",
    "hint.cloud": "Nube: se envían fragmentos cortos de texto a este proveedor. El audio, nunca.",
    "group.audio": "Audio",
    "group.transcription": "Transcripción · siempre en este PC",
    "group.ai": "Análisis con IA",
    "group.context": "Contexto",
    "label.engine": "Motor de captura",
    "label.source": "Fuente",
    "label.whisper_model": "Modelo Whisper",
    "label.speech_language": "Idioma hablado",
    "label.provider": "Proveedor",
    "label.server_url": "URL del servidor",
    "label.model": "Modelo",
    "label.api_key": "Clave API",
    "label.profile": "Especialidad",
    "label.no_doc": "Ningún documento cargado",
    "label.doc_loaded": "{name} · {passages} fragmentos",
    "engine.wasapi": "WASAPI (recomendado)",
    "engine.soundcard": "SoundCard (alternativo)",
    "source.pc": "Audio del PC · {name}",
    "source.mic": "Micrófono · {name}",
    "speech.es": "Castellano",
    "speech.ca": "Català",
    "speech.en": "Inglés",
    "speech.auto": "Detectar",
    "profile.general": "General",
    "profile.it": "CTO / CIO · IT y estrategia",
    "profile.security": "Ciberseguridad",
    "profile.business": "Empresa y finanzas",
    "provider.none": "Solo transcripción · nada sale de este PC",
    "provider.ollama": "Ollama · local",
    "provider.lmstudio": "LM Studio · local",
    "provider.chatgpt": "Plan de ChatGPT",
    "provider.openai": "API de OpenAI · tu clave, de pago",
    "provider.custom": "Otro servidor compatible con OpenAI",
    "panel.concepts": "¿De qué están hablando?",
    "panel.answers": "¿Qué puedo responder?",
    "panel.transcript": "Transcripción en directo",
    "panel.concepts_empty": "Aquí aparecerán los conceptos que explique la IA.",
    "panel.answers_empty": "Aquí aparecerán las preguntas detectadas y respuestas sugeridas.",
    "panel.transcript_empty": "Pulsa Empezar y reproduce algo de voz.",
    "answer.reply": "Para intervenir",
    "answer.missing": "Por confirmar",
    "status.ready": "Listo",
    "status.listening": "Escuchando",
    "status.stopping": "Deteniendo · terminando el audio pendiente…",
    "status.paused": "En pausa · pulsa Empezar para continuar",
    "status.silence": "Silencio en esta salida",
    "status.level": "Nivel de audio {level:.3f}",
    "status.no_devices": "No se han encontrado fuentes de audio.",
    "status.devices_error": "No se pudieron listar los dispositivos de audio: {detail}",
    "status.latency": "Texto {stt} · IA {ai} · Voz → sugerencia {e2e}",
    "status.demo": "Modo demo · reunión simulada, sin audio ni IA",
    "ai.off": "IA desactivada · nada sale de este PC",
    "ai.ready": "IA lista · {provider}",
    "ai.connected": "Conectado: {email}",
    "ai.connecting": "Completa el inicio de sesión en tu navegador…",
    "ai.disconnected": "Desconectado",
    "ai.disconnected_unconfirmed": "Desconectado en este PC; no se confirmó la revocación remota.",
    "ai.testing": "Probando la IA con un texto de ejemplo (sin audio)…",
    "ai.test_ok": "La IA funciona: respuesta estructurada recibida.",
    "ai.models_found": "{n} modelos encontrados",
    "ai.waiting": "Esperando a la IA · {seconds} s (límite {limit} s)",
    "ai.asking": "Consultando a la IA…",
    "ai.answered": "La IA respondió · esperando nuevas intervenciones",
    "ai.paused_error": "IA pausada por un error · la transcripción sigue",
    "ai.paused": "IA pausada · la transcripción sigue",
    "ai.enabled_live": "IA activada · analizará lo que se diga a continuación",
    "stage.loading_whisper": "Cargando Whisper · la primera descarga puede tardar unos minutos…",
    "stage.whisper_ready": "Whisper listo · esperando voz",
    "stage.transcribing": "Transcribiendo…",
    "stage.slower_than_realtime": "La transcripción va más lenta que el audio · prueba un modelo menor",
    "stage.no_words": "Llega audio, pero no se reconocen palabras",
    "error.capture": "Fallo en la captura de audio: {detail}",
    "error.falling_behind": "La transcripción no sigue el ritmo: se ha omitido un bloque. Prueba un modelo menor.",
    "error.whisper_load": "No se pudo cargar Whisper: {detail}",
    "error.transcription": "Error de transcripción: {detail}",
    "error.analysis": "Análisis con IA pausado: {detail}. La transcripción local continúa.",
    "error.title": "Pinganillo",
    "dialog.notice_title": "Antes de empezar",
    "dialog.notice_body": (
        "Pinganillo transcribe lo que suena en tu ordenador, incluidas las voces de otras personas.\n\n"
        "• Avisa a los demás participantes antes de usarlo. Las leyes sobre grabación y transcripción "
        "cambian según el país; en algunos sitios hace falta el consentimiento de todos.\n"
        "• Con un proveedor local (o solo transcripción) nada sale de este PC. Con un proveedor en la "
        "nube, se envían fragmentos cortos de texto a ese proveedor.\n"
        "• Las sugerencias pueden equivocarse. Compruébalas antes de fiarte de ellas.\n\n"
        "Usa «Copiar aviso para la reunión» para avisar con un clic."
    ),
    "dialog.notice_ok": "Entendido",
    "dialog.paid_title": "Proveedor de pago",
    "dialog.paid_body": "Este proveedor cobra en tu cuenta de API, aparte de cualquier suscripción. ¿Continuar?",
    "dialog.new_session": "¿Borrar la transcripción y las sugerencias? Exporta antes si quieres conservarlas.",
    "dialog.export_title": "Exportar sesión",
    "dialog.doc_title": "Cargar documento de referencia (.txt / .md)",
    "dialog.diag_title": "Guardar diagnóstico",
    "notice.text": (
        "Aviso: estoy usando Pinganillo, un asistente de código abierto que transcribe esta llamada en "
        "mi ordenador para ayudarme a seguirla.{ai_part} Dime si prefieres que lo apague."
    ),
    "notice.ai_part": " Fragmentos cortos de texto se analizan con {provider}.",
    "notice.copied": "Aviso copiado al portapapeles.",
    "export.saved": "Sesión exportada en {path}",
    "export.heading_transcript": "Transcripción",
    "export.heading_concepts": "Conceptos",
    "export.heading_questions": "Preguntas y respuestas sugeridas",
    "export.heading_summary": "Resumen",
    "diag.saved": "Diagnóstico guardado (sin audio, transcripción ni credenciales).",
}

LANGUAGES = {"en": EN, "es": ES}
_current = "en"


def system_language() -> str:
    try:
        name = locale.getlocale()[0] or ""
    except ValueError:
        name = ""
    return "es" if name.lower().startswith(("es", "ca", "spanish", "catalan")) else "en"


def set_language(code: str) -> str:
    global _current
    _current = system_language() if code in ("", "auto") else (code if code in LANGUAGES else "en")
    return _current


def current_language() -> str:
    return _current


def tr(key: str, **params: Any) -> str:
    """Translate ``key``; unknown keys are returned as-is so raw text still displays."""
    text = LANGUAGES[_current].get(key) or EN.get(key) or key
    try:
        return text.format(**params) if params else text
    except (KeyError, IndexError, ValueError):
        return text


def tr_message(value: Any) -> str:
    """Translate a pipeline message: ``(key, params)`` or plain text."""
    if isinstance(value, tuple) and len(value) == 2 and isinstance(value[1], dict):
        return tr(value[0], **value[1])
    return str(value)
