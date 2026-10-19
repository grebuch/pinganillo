"""Analysis backends."""

from __future__ import annotations

from typing import Any, Protocol

from .deadline import DeadlineCall

EMPTY_ANALYSIS = '{"resumen":"","conceptos":[],"preguntas":[]}'


class Analyzer(Protocol):
    def analyze(self, instructions: str, payload: str) -> str: ...


class NoAnalyzer:
    """Transcription-only mode: nothing is sent anywhere."""

    def analyze(self, instructions: str, payload: str) -> str:
        return EMPTY_ANALYSIS


class ChatGPTPlanAnalyzer:
    """Uses the signed-in user's ChatGPT plan through Sign in with ChatGPT.

    Follows the preview contract: Responses API at api.openai.com/v1 with
    ``store=False``, ``stream=True``, ``input`` as a list and ``instructions``
    instead of a system message. A response is only accepted after the
    ``response.completed`` event, so a cut stream is never shown as complete.
    """

    def __init__(self, auth: Any, model: str, timeout: float = 45) -> None:
        self.auth, self.model = auth, model
        self.guard = DeadlineCall(timeout)
        self.diagnostic: dict[str, Any] = {"state": "untested"}

    def analyze(self, instructions: str, payload: str) -> str:
        self.diagnostic = {"state": "waiting"}
        try:
            result = self.guard.call(lambda: self._request(instructions, payload))
            self.diagnostic = {"state": "completed"}
            return result
        except Exception as exc:
            self.diagnostic = {
                "state": "error",
                "type": type(exc).__name__,
                "http_status": getattr(exc, "status_code", None),
                "code": getattr(exc, "code", None),
            }
            raise

    def _request(self, instructions: str, payload: str) -> str:
        import httpx
        from openai import OpenAI

        client = OpenAI(
            api_key=self.auth.access_token(),
            base_url="https://api.openai.com/v1",
            timeout=httpx.Timeout(20, connect=8, read=20, write=10, pool=8),
            max_retries=0,
        )
        parts: list[str] = []
        completed = False
        with client.responses.create(
            model=self.model,
            instructions=instructions,
            input=[{"role": "user", "content": payload}],
            store=False,
            stream=True,
        ) as stream:
            for event in stream:
                if event.type == "response.output_text.delta":
                    parts.append(event.delta)
                elif event.type == "response.completed":
                    completed = True
                elif event.type in ("response.failed", "response.incomplete", "error"):
                    error = getattr(getattr(event, "response", None), "error", None)
                    code = getattr(error, "code", None) or getattr(event, "code", "")
                    raise ValueError(
                        f"Analysis stopped: {code or event.type}. Check your plan limits or reconnect."
                    )
        if not completed:
            raise ValueError("The response was interrupted; it will not be shown as complete.")
        return "".join(parts)


class PaidApiAnalyzer:
    """OpenAI API with the user's own key (billed separately)."""

    def __init__(self, key: str, model: str = "gpt-4.1-mini") -> None:
        from openai import OpenAI

        self.client = OpenAI(api_key=key, timeout=30, max_retries=1)
        self.model = model

    def analyze(self, instructions: str, payload: str) -> str:
        return self.client.responses.create(
            model=self.model,
            instructions=instructions,
            input=payload,
            text={"format": {"type": "json_object"}},
            max_output_tokens=2200,
            store=False,
        ).output_text
