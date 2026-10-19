# Benchmarks

## Method

`pinganillo-bench` measures the speech-to-text part with the same code path as the live app:

1. Load a 16-bit WAV and resample it to 48 kHz.
2. Cut it into 0.5 s blocks and group them with the same `PauseSegmenter`.
3. Transcribe every chunk with the real faster-whisper model.
4. Replay the timeline as if the audio were arriving live: a chunk can only start when its audio has ended *and* the previous chunk is done.

It reports:

- **RTF** (real-time factor): processing time ÷ audio time. Below 1.0 the model keeps up with live audio.
- **Latency p50 / p95 / max**: from the end of a chunk's audio to its text being ready.
- **WER** (word error rate) against a reference transcript, if you pass one. Punctuation and case are ignored; accents count.

```bash
pinganillo-bench meeting.wav --model small --language es --reference meeting.txt --json small.json
pinganillo-bench meeting.wav --model base  --language es --reference meeting.txt --json base.json
```

Convert other formats with `ffmpeg -i input.mp3 -ac 1 -ar 16000 -c:a pcm_s16le meeting.wav`.

## Results

Numbers depend heavily on the CPU, so each row states the machine. Please contribute yours by opening an issue with the JSON file.

| Machine | Model | Audio | RTF | Latency p50 | Latency p95 | WER |
|---|---|---|---|---|---|---|
| *your machine here* | small | | | | | |

The AI part is measured live: the status bar shows the median model time and speech → suggestion time for the current session, and *Save diagnostics* exports p50/p95 for all three measurements.
