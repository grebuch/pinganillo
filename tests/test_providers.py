import sys
from types import SimpleNamespace

import pytest

from escuchator.config import Settings
from escuchator.llm.analyzers import ChatGPTPlanAnalyzer, NoAnalyzer, OpenAICompatibleAnalyzer
from escuchator.llm.providers import PROVIDERS, build_analyzer


class HTTPError(Exception):
    def __init__(self, status_code):
        super().__init__(f"HTTP {status_code}")
        self.status_code = status_code


def completion(text, finish_reason="stop"):
    return SimpleNamespace(
        choices=[SimpleNamespace(finish_reason=finish_reason, message=SimpleNamespace(content=text))]
    )


def fake_openai(monkeypatch, create):
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create)),
        models=SimpleNamespace(list=lambda: [SimpleNamespace(id="b"), SimpleNamespace(id="a")]),
    )
    seen = {}

    def factory(**kwargs):
        seen.update(kwargs)
        return client

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=factory))
    return seen


def test_ollama_request_uses_json_mode_and_local_url(monkeypatch):
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        return completion("{}")

    seen = fake_openai(monkeypatch, create)
    analyzer = build_analyzer("ollama", model="qwen2.5:7b")
    assert isinstance(analyzer, OpenAICompatibleAnalyzer)
    assert analyzer.analyze("system", "{}") == "{}"
    assert seen["base_url"] == "http://localhost:11434/v1"
    assert calls[0]["response_format"] == {"type": "json_object"}
    assert calls[0]["messages"][0] == {"role": "system", "content": "system"}
    assert analyzer.list_models() == ["a", "b"]


def test_server_without_json_mode_falls_back_once(monkeypatch):
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        if "response_format" in kwargs:
            raise HTTPError(400)
        return completion("{}")

    fake_openai(monkeypatch, create)
    analyzer = OpenAICompatibleAnalyzer("http://localhost:8080/v1", "m")
    analyzer.analyze("s", "{}")
    analyzer.analyze("s", "{}")
    assert ["response_format" in c for c in calls] == [True, False, False]


def test_truncated_reply_is_rejected(monkeypatch):
    fake_openai(monkeypatch, lambda **k: completion('{"resu', finish_reason="length"))
    with pytest.raises(ValueError, match="cut off"):
        OpenAICompatibleAnalyzer("http://x/v1", "m").analyze("s", "{}")


def test_server_errors_are_not_swallowed(monkeypatch):
    def create(**kwargs):
        raise HTTPError(500)

    fake_openai(monkeypatch, create)
    analyzer = OpenAICompatibleAnalyzer("http://x/v1", "m")
    with pytest.raises(HTTPError):
        analyzer.analyze("s", "{}")
    assert analyzer.diagnostic == {"state": "error", "type": "HTTPError", "http_status": 500}


def test_factory_validates_configuration():
    assert isinstance(build_analyzer("none"), NoAnalyzer)
    with pytest.raises(ValueError, match="model"):
        build_analyzer("ollama")
    with pytest.raises(ValueError, match="API key"):
        build_analyzer("openai", model="gpt-4.1-mini")
    with pytest.raises(ValueError, match="URL"):
        build_analyzer("custom", model="m")
    with pytest.raises(ValueError, match="ChatGPT"):
        build_analyzer("chatgpt", model="m", auth=SimpleNamespace(connected=False))
    plan = build_analyzer("chatgpt", model="m", auth=SimpleNamespace(connected=True))
    assert isinstance(plan, ChatGPTPlanAnalyzer)
    assert all(p.local for p in PROVIDERS.values() if p.key in ("none", "ollama", "lmstudio"))


def test_settings_round_trip_and_tolerate_bad_files(tmp_path):
    settings = Settings(ai_provider="ollama", ai_model="qwen2.5:7b", analysis_interval_s=6)
    settings.save(tmp_path)
    assert Settings.load(tmp_path) == settings
    Settings.path(tmp_path).write_text('{"whisper_model": 42, "unknown": true, "profile": "security"}')
    loaded = Settings.load(tmp_path)
    assert loaded.whisper_model == "small" and loaded.profile == "security"
    Settings.path(tmp_path).write_text("garbage")
    assert Settings.load(tmp_path) == Settings()
    assert "api" not in Settings.path(tmp_path).read_text().lower()
