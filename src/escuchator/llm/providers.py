"""Which AI does the analysis. Speech recognition is always local regardless."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .analyzers import Analyzer, ChatGPTPlanAnalyzer, NoAnalyzer, OpenAICompatibleAnalyzer


@dataclass(frozen=True)
class Provider:
    key: str
    label: str
    base_url: str = ""
    needs_key: bool = False
    local: bool = False
    model_hint: str = ""


PROVIDERS: dict[str, Provider] = {
    p.key: p
    for p in (
        Provider("none", "Transcription only (nothing leaves this PC)", local=True),
        Provider(
            "ollama", "Ollama (local)", "http://localhost:11434/v1", local=True, model_hint="qwen2.5:7b"
        ),
        Provider("lmstudio", "LM Studio (local)", "http://localhost:1234/v1", local=True),
        Provider("chatgpt", "ChatGPT plan (Sign in with ChatGPT)"),
        Provider(
            "openai",
            "OpenAI API (your key, billed)",
            "https://api.openai.com/v1",
            needs_key=True,
            model_hint="gpt-4.1-mini",
        ),
        Provider("custom", "Other OpenAI-compatible server", needs_key=False),
    )
}


def build_analyzer(
    provider: str,
    model: str = "",
    base_url: str = "",
    api_key: str = "",
    auth: Any = None,
    timeout: float = 45,
) -> Analyzer:
    """Create the analyzer for a provider; raises ``ValueError`` with a user-facing reason."""
    spec = PROVIDERS.get(provider)
    if spec is None:
        raise ValueError(f"Unknown AI provider: {provider}")
    if spec.key == "none":
        return NoAnalyzer()
    if not model:
        raise ValueError("Choose a model for the AI analysis.")
    if spec.key == "chatgpt":
        if auth is None or not auth.connected:
            raise ValueError("Connect your ChatGPT account first.")
        return ChatGPTPlanAnalyzer(auth, model, timeout)
    url = base_url or spec.base_url
    if not url:
        raise ValueError("Enter the server URL (for example http://localhost:8080/v1).")
    if spec.needs_key and not api_key:
        raise ValueError("This provider needs an API key.")
    return OpenAICompatibleAnalyzer(url, model, api_key, timeout)
