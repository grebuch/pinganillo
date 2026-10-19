# Contributing

Thanks for helping. Issues, ideas, benchmark results and pull requests are all welcome.

## Set up

```bash
git clone https://github.com/grebuch/pinganillo && cd pinganillo
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest
python -m pinganillo --demo                       # no audio, model or account needed
```

Tests never touch audio hardware, download models or call the network: devices, Whisper and HTTP clients are replaced by small fakes. Please keep it that way, so CI stays fast and deterministic. The UI test runs headless (`QT_QPA_PLATFORM=offscreen`).

Before opening a pull request:

```bash
ruff format . && ruff check . && pytest
```

## Where things live

See [docs/architecture.md](docs/architecture.md) for the module map. In short: `audio/` captures, `stt/` transcribes, `llm/` analyses, `pipeline.py` wires the threads, `ui/` displays.

## Adding a language

1. Copy the `EN` dictionary in `src/pinganillo/i18n.py`, translate the values, and register it in `LANGUAGES`.
2. `tests/test_i18n_export.py` checks that every language defines the same keys.
3. Optionally add a demo script for it in `src/pinganillo/demo.py`.

## Good first issues

- **Catalan interface**: the speech model already supports it.
- **Microphone + speakers mixed** into one stream, so your own voice is transcribed too.
- **Linux capture**: PulseAudio/PipeWire monitor sources through the SoundCard engine, tested on a real desktop.
- **macOS capture** with ScreenCaptureKit.
- **Optional embedding retriever** behind `KnowledgeBase.relevant()` (see ADR 0005).
- **GPU transcription** (`device="cuda"`) with automatic fallback to CPU.
- **Benchmarks** from your machine in `docs/benchmarks.md`.

## Design changes

If a change alters how the app behaves in a way others should understand later (a new dependency, a new data flow, a trade-off), add a short record to `docs/decisions/`.

## Code of conduct

Be kind and assume good faith. See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
