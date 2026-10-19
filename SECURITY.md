# Security policy

## Reporting a vulnerability

Please use GitHub's **private vulnerability reporting** (Security tab → *Report a vulnerability*) instead of a public issue. You will get an answer within a week.

## Scope

Areas where a report is especially valuable:

- The Sign in with ChatGPT flow (`auth/chatgpt.py`): state, PKCE, ID-token verification, token handling.
- Prompt injection: meeting speech or documents that make the model output something harmful or misleading.
- Anything that could write audio, transcripts or credentials somewhere the user did not choose.

## Design guarantees

- Audio is never uploaded.
- ChatGPT tokens live in memory only; only a non-secret registration record (client id, account id, e-mail, random host id) is stored.
- API keys are never written to disk.
- Model output is only displayed; the app never executes it.
