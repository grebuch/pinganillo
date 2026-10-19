---
name: Release checklist
about: Manual test of a release candidate on a real Windows machine
title: "Release checklist vX.Y.Z-rc.N"
labels: release
---

Candidate: <!-- link to the pre-release -->
Machine: <!-- Windows version, CPU, RAM, GPU -->

### Install
- [ ] The release zip's SHA-256 matches the `.sha256` file
- [ ] `Pinganillo.exe` starts (or `run-windows.bat` from source) and the window appears in under 15 s
- [ ] `pinganillo --version` shows the candidate version

### Without audio
- [ ] `--demo` shows transcript, concepts and suggested replies
- [ ] Interface in English and Spanish (`--lang en`, `--lang es`)

### Capture and transcription
- [ ] The audio source list shows the speakers/headphones in use
- [ ] A YouTube video with speech: text appears and is understandable
- [ ] A Teams/Meet/Zoom call: text appears
- [ ] 30 s of silence: capture keeps running (no error)
- [ ] Stop and Start again: the session continues

### AI
- [ ] Transcription only: nothing is sent (AI button disabled)
- [ ] Ollama (local): "Test AI" works and suggestions appear during a session
- [ ] ChatGPT plan or API (if available): "Test AI" works
- [ ] Unplugging the network during AI: transcription keeps running, AI pauses with a clear message

### Session tools
- [ ] Export to Markdown and JSON
- [ ] "Copy meeting notice" puts the notice on the clipboard
- [ ] "Save diagnostics" contains no transcript, names or e-mail

### Measurements (paste the status bar or the diagnostics JSON)
- Text p50: 
- AI p50: 
- Speech → hint p50: 

Result: <!-- PASS → tag the final release / FAIL → link the issues -->
