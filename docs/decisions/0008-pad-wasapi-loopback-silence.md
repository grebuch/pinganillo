# 0008 · Pad WASAPI loopback silence instead of failing

**Context.** A WASAPI loopback stream delivers no packets at all while nothing is rendered on that output. The prototype waited up to 10 s for samples and then raised "no samples from this output", which ended the session during any quiet moment (a paused video, a silent part of a call). It looked like a broken device and was hard to diagnose. NAudio and GStreamer document the same behaviour.

**Decision.** `WasapiRecorder.record()` waits for one block's duration plus a 50 % margin. If not enough samples arrived, it completes the block with zeros, which is exactly what the output was playing, and counts the padded frames. A stream that is no longer active, or an overflowing buffer, is still an error.

**Alternatives.** Rendering a silent stream on the same output keeps the loopback "awake" and avoids padding, but adds a second audio stream and device-specific failure modes. Padding is simpler and testable without hardware.

**Consequences.** The timeline stays continuous and the segmenter sees real pauses as pauses. Tests cover full silence, partial blocks and a stopped device.
