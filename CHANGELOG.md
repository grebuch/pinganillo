# Changelog

All notable changes to this project. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [semantic versioning](https://semver.org/).

## [0.6.0] - 2026-10-19

First public release.

### Added
- Qt interface with concepts, suggested replies and live transcript; English and Spanish.
- AI providers: Ollama, LM Studio, any OpenAI-compatible server, ChatGPT plan, OpenAI API, or none.
- `--demo` mode that runs the real pipeline with a scripted meeting.
- Live latency telemetry (speech → text, model, speech → suggestion).
- `escuchator-bench`: replay benchmark with real-time factor, latency percentiles and WER.
- Markdown/JSON export, privacy-safe diagnostics, first-run notice and "Copy meeting notice".
- Design decision records, architecture notes, CI on Windows and Linux.

### Fixed
- Capture stopped after 10 s of silence on WASAPI loopback outputs.
- Every AI request carried the whole reference document; now only matching passages are sent.
- Windows launcher picked any Python version and reinstalled dependencies on every start.
- Corrupt settings or registration files no longer prevent start-up.
- Order-dependent test failures caused by unloading numpy/scipy modules.

### Changed
- Audio is always transcribed locally; the paid mode no longer uploads audio.
- Code restructured into an installable package.

## [0.1.0 – 0.5.0] - 2026

Windows prototype (Tkinter) built with ChatGPT's help: WASAPI capture, local Whisper, ChatGPT plan analysis.
