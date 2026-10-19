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


class OpenAICompatibleAnalyzer:
    """Any server that speaks the OpenAI Chat Completions API.

    That covers fully local runtimes (Ollama, LM Studio, llama.cpp server,
    vLLM) as well as hosted APIs (OpenAI, Groq, OpenRouter, Mistral...).
    JSON mode is requested; servers that reject ``response_format`` are
    retried once without it and the strict parser still validates the reply.
    """

    def __init__(self, base_url: str, model: str, api_key: str = "", timeout: float = 45) -> None:
        self.base_url, self.model = base_url.rstrip("/"), model
        self.api_key = api_key or "not-needed"  # local servers ignore it, the SDK requires one
        self.json_mode = True
        self.guard = DeadlineCall(timeout)
        self.diagnostic: dict[str, Any] = {"state": "untested"}
        self._client: Any = None

    @property
    def client(self) -> Any:
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(base_url=self.base_url, api_key=self.api_key, timeout=30, max_retries=0)
        return self._client

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
            }
            raise

    def _request(self, instructions: str, payload: str) -> str:
        messages = [{"role": "system", "content": instructions}, {"role": "user", "content": payload}]
        options: dict[str, Any] = {"model": self.model, "messages": messages, "temperature": 0.2}
        if self.json_mode:
            try:
                response = self.client.chat.completions.create(
                    **options, response_format={"type": "json_object"}
                )
            except Exception as exc:
                if getattr(exc, "status_code", None) not in (400, 422):
                    raise
                self.json_mode = False  # server does not support JSON mode; remember that
                response = self.client.chat.completions.create(**options)
        else:
            response = self.client.chat.completions.create(**options)
        choice = response.choices[0]
        if getattr(choice, "finish_reason", "stop") == "length":
            raise ValueError("The model reply was cut off (length limit); it will not be shown.")
        return choice.message.content or ""

    def list_models(self) -> list[str]:
        return sorted(m.id for m in self.client.models.list())
