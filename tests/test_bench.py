import wave

import numpy as np
import pytest

from pinganillo.bench import load_wav, replay, segment, summarise, word_error_rate


def test_word_error_rate():
    assert word_error_rate("the cat sat", "the cat sat") == 0
    assert word_error_rate("the cat sat", "the hat sat") == pytest.approx(1 / 3)
    assert word_error_rate("the cat sat", "cat sat on") == pytest.approx(2 / 3)
    assert word_error_rate("Hola, ¿qué tal?", "hola que tal") == pytest.approx(1 / 3)  # accents matter


def test_replay_models_queueing_when_slower_than_real_time():
    chunks = [(0.0, 5.0, None), (5.0, 10.0, None)]
    clock = iter([0, 7, 7, 14])  # each chunk takes 7 s to transcribe
    results = replay(chunks, lambda c: "x", timer=lambda: next(clock))
    assert [r.latency_s for r in results] == [7, 9]  # second chunk waits for the first
    summary = summarise(results, 10.0, "x x")
    assert summary.rtf == 1.4 and summary.wer == 0


def test_wav_loading_and_segmentation(tmp_path):
    rate = 16_000
    t = np.arange(rate * 10) / rate
    tone = (np.sin(2 * np.pi * 300 * t) * 8000).astype("<i2")
    tone[rate * 5 : rate * 6] = 0  # one-second pause after five seconds
    path = tmp_path / "a.wav"
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(tone.tobytes())
    samples = load_wav(path)
    assert samples.shape == (480_000, 1)
    chunks = segment(samples)
    assert chunks[0][1] == pytest.approx(6.0)  # cut at the pause
    assert chunks[-1][1] == pytest.approx(10.0)
