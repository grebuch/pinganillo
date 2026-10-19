# 0001 · Speech recognition always runs locally

**Context.** The audio of a meeting contains other people's voices. Sending it to a cloud service is the most sensitive thing the app could do, and cloud transcription also adds cost and a network dependency to the part that must never stop.

**Decision.** Transcription always uses faster-whisper on the user's CPU (int8). The only network access is the one-time model download from Hugging Face. No provider, paid or not, receives audio. The prototype's paid mode that uploaded audio was removed.

**Consequences.** Accuracy and latency depend on the user's CPU; `small` is the default as a balance, `base` is offered for slow machines and `medium`/`large-v3-turbo` for strong ones. GPU support is a possible extension.
