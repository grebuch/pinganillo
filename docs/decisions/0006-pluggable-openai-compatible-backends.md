# 0006 · Any OpenAI-compatible backend; the ChatGPT plan is optional

**Context.** The prototype depended on "Sign in with ChatGPT" plan usage, which is a preview, limited to some plans and subject to change. An open-source tool should not depend on one vendor's preview.

**Decision.** One `Analyzer` protocol (`analyze(instructions, payload) -> str`) with two implementations: `OpenAICompatibleAnalyzer` (Chat Completions, which Ollama, LM Studio, llama.cpp, vLLM and most hosted APIs speak) and `ChatGPTPlanAnalyzer` (Responses API with the preview's constraints: `store=false`, `stream=true`, list input). A registry and `build_analyzer()` factory validate the configuration with user-facing errors. JSON mode is requested and dropped (once, remembered) for servers that reject it; replies cut by a length limit are rejected.

**Consequences.** The default local setup (Ollama) is free and private. Output quality depends on the chosen model; small local models follow the JSON format less reliably, which the strict parser absorbs by dropping bad items.
