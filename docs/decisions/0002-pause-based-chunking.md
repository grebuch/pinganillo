# 0002 · Pause-based chunks instead of streaming recognition

**Context.** Whisper is not a streaming model. Feeding it 1–3 s slices produces cut words and poor accuracy; feeding it long windows adds latency.

**Decision.** Capture in 0.5 s blocks and group them with `PauseSegmenter`: cut at the first ~1 s pause after 4 s of audio, and never let a chunk exceed 12 s. "Quiet" is relative to the chunk's own peak (8 %) with an absolute floor, so it adapts to loud and quiet sources. Whisper's own VAD filter then removes residual silence.

**Consequences.** Simple, cheap and fully unit-tested, but it is a volume heuristic: background music defeats it and it can still split a sentence. The first words of a long chunk wait up to 12 s. A VAD-based or streaming model is a natural upgrade path; the segmenter is isolated so it can be swapped.
