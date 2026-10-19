# Design decisions

Short records of the decisions that shape Escuchator: the context, what was chosen, and what it costs. New significant changes should add one (copy the format of any existing record).

| # | Decision |
|---|---|
| [0001](0001-local-speech-recognition.md) | Speech recognition always runs locally |
| [0002](0002-pause-based-chunking.md) | Pause-based chunks instead of streaming recognition |
| [0003](0003-threads-and-queues.md) | One thread per stage, queues between them, UI polls |
| [0004](0004-deadline-without-cancellation.md) | Deadlines that stop waiting, one request in flight |
| [0005](0005-bm25-context-instead-of-whole-document.md) | BM25 passages instead of the whole document or embeddings |
| [0006](0006-pluggable-openai-compatible-backends.md) | Any OpenAI-compatible backend; the ChatGPT plan is optional |
| [0007](0007-no-stealth-features.md) | No stealth features |
| [0008](0008-pad-wasapi-loopback-silence.md) | Pad WASAPI loopback silence instead of failing |
