# Responsible use

Escuchator transcribes what your computer plays, which usually includes other people's voices. Using it well is your responsibility; the app tries to make the right thing easy.

## Before a meeting

- **Tell the participants.** The *Copy meeting notice* button puts a short, honest message on your clipboard, for example: *"Heads-up: I'm using Escuchator, an open-source assistant that transcribes this call on my computer to help me follow it. Tell me if you'd rather I turn it off."* When a cloud provider is selected, the message says which one.
- **Know your local rules.** Recording and transcription laws differ by country and state. Some require the consent of everyone in the conversation. Workplaces often have their own policies, and in the EU the GDPR applies when you process other people's personal data in a professional context. This page is not legal advice.
- **Prefer a local provider** for confidential meetings. With *Transcription only*, Ollama or LM Studio, nothing leaves your computer.

## What leaves your computer

| Data | Local providers | Cloud providers |
|---|---|---|
| Audio | Never | Never |
| Transcript text | Never | Short recent excerpts with each request |
| Reference document | Never | Only the few passages that match the current speech |
| Credentials | ChatGPT tokens are kept in memory only | API keys are never written to disk |

Exports and diagnostics are written only where you choose. Diagnostics never contain audio, transcripts, documents or credentials.

## Treat suggestions as suggestions

The model is instructed not to invent prices, facts or sources and to say when something needs verifying, but it can still be wrong. Use the panels to understand and prepare, not to read answers aloud unchecked.

## What the project will not build

Features whose purpose is to hide the tool from other participants, such as overlays invisible to screen sharing. See [ADR 0007](decisions/0007-no-stealth-features.md).
