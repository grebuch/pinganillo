# Roadmap

## 0.7 · Closer to real time

Today text appears about 5–15 s after something is said, and a suggestion 15–40 s after (estimates from the pipeline design; the live telemetry measures the real numbers on each machine). The goal for 0.7 is **text in 1–3 s and the short reply starting to appear in 3–6 s** with a fast model.

| # | Change | Expected effect |
|---|---|---|
| 1 | **Question fast path**: when the new fragment contains a question, send it to the AI immediately instead of waiting to batch | Removes 2–4 s from every answer |
| 2 | **Stream the AI reply**: ask for the short reply first and render it token by token | First useful words in 1–2 s instead of waiting for the full JSON |
| 3 | **Faster decoding**: greedy Whisper decoding (`beam_size=1`) as the default, beam search as an "accuracy" option; prefer fast, non-reasoning chat models | 2–3× faster transcription |
| 4 | **Live provisional transcript**: re-transcribe the growing buffer every ~1 s and show it greyed out, replaced by the final text when the chunk closes | Text visible while people are still talking |
| 5 | **Speech-aware chunking**: cut with the Silero VAD bundled with faster-whisper, 2–8 s chunks instead of 4–12 s | Shorter wait for the first words of each phrase |
| 6 | **GPU when available**: `device="cuda"` with automatic fallback to CPU | 5–10× faster on NVIDIA GPUs |

Every change must show its effect in `pinganillo-bench` and in the live latency telemetry before and after.

## Later

- Microphone and speakers mixed, so your own voice is transcribed too.
- Linux (PipeWire/PulseAudio monitor) and macOS (ScreenCaptureKit) capture.
- Optional embedding retriever for reference documents.
- Catalan interface.
