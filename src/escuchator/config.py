"""User settings, persisted as JSON in the per-user config folder.

Secrets are never written here: no tokens, no API keys. An API key can be
typed in each session or provided through the ``ESCUCHATOR_API_KEY``
environment variable.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from .auth.chatgpt import config_dir

API_KEY_ENV = "ESCUCHATOR_API_KEY"
WHISPER_MODELS = ("small", "base", "medium", "large-v3-turbo")
SPEECH_LANGUAGES = {"es": "Español", "ca": "Català", "en": "English", "auto": "Auto"}


@dataclass
class Settings:
    ui_language: str = "auto"
    capture_engine: str = ""
    device_name: str = ""
    whisper_model: str = "small"
    speech_language: str = "es"
    profile: str = "it"
    ai_provider: str = "none"
    ai_model: str = ""
    ai_base_url: str = ""
    analysis_interval_s: float = 4.0
    context_budget_chars: int = 2_500
    ai_timeout_s: float = 45.0
    notice_acknowledged: bool = False
    sidebar_visible: bool = True

    @classmethod
    def path(cls, directory: Path | None = None) -> Path:
        return (directory or config_dir()) / "settings.json"

    @classmethod
    def load(cls, directory: Path | None = None) -> Settings:
        """Unknown keys are ignored and bad values fall back to defaults: old files never break start-up."""
        try:
            raw = json.loads(cls.path(directory).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls()
        settings = cls()
        if not isinstance(raw, dict):
            return settings
        for f in fields(cls):
            if f.name in raw:
                default = getattr(settings, f.name)
                value = raw[f.name]
                if isinstance(default, float) and isinstance(value, int):
                    value = float(value)
                if type(value) is type(default):
                    setattr(settings, f.name, value)
        return settings

    def save(self, directory: Path | None = None) -> None:
        path = self.path(directory)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        os.replace(temporary, path)

    @property
    def whisper_language(self) -> str | None:
        return None if self.speech_language == "auto" else self.speech_language


def api_key_from_env() -> str:
    return os.environ.get(API_KEY_ENV, "")
