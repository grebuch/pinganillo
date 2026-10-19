import sys
from types import SimpleNamespace

import numpy as np
import pytest

from escuchator.llm.analyzers import ChatGPTPlanAnalyzer
from escuchator.stt.whisper_local import LocalTranscriber


class FakeStream:
    def __init__(self, completed):
        self.completed = completed

    def __enter__(self):
        return iter(
            [
                SimpleNamespace(type="response.output_text.delta", delta="{}"),
                SimpleNamespace(type="response.completed" if self.completed else "response.incomplete"),
            ]
        )

    def __exit__(self, *exc):
        return None


def test_chatgpt_plan_request_follows_preview_contract(monkeypatch):
    captured = {}

    def create(**kwargs):
        captured.update(kwargs)
        return FakeStream(True)

    client = SimpleNamespace(responses=SimpleNamespace(create=create))
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=lambda **k: client))
    analyzer = ChatGPTPlanAnalyzer(SimpleNamespace(access_token=lambda: "token"), "model-x")
    assert analyzer.analyze("instructions", "{}") == "{}"
    assert captured["stream"] is True
    assert captured["store"] is False
    assert isinstance(captured["input"], list)
    assert "temperature" not in captured and "max_output_tokens" not in captured

    client.responses.create = lambda **k: FakeStream(False)
    with pytest.raises(ValueError):
        analyzer.analyze("instructions", "{}")
    assert analyzer.diagnostic["state"] == "error"


def test_local_transcriber_settings_and_input_format(monkeypatch):
    seen = {}

    class Model:
        def __init__(self, name, **kwargs):
            seen["name"] = name
            seen.update(kwargs)

        def transcribe(self, audio, **kwargs):
            seen["decode"] = kwargs
            assert isinstance(audio, np.ndarray) and audio.dtype == np.float32 and audio.shape == (160,)
            return iter([SimpleNamespace(text=" Texto local ")]), None

    monkeypatch.setitem(sys.modules, "faster_whisper", SimpleNamespace(WhisperModel=Model))
    transcriber = LocalTranscriber()
    assert transcriber.transcribe(np.ones((480, 2), np.float32)) == "Texto local"
    assert seen["device"] == "cpu" and seen["compute_type"] == "int8" and seen["name"] == "small"
    assert seen["decode"]["language"] == "es"
    assert seen["decode"]["vad_filter"] is True
    assert seen["decode"]["condition_on_previous_text"] is False
