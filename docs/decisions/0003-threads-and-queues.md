# 0003 · One thread per stage, queues between them, UI polls

**Context.** Capture must never block (audio is lost), transcription is CPU-bound and bursty, and AI calls can take tens of seconds. Qt widgets may only be touched from the GUI thread.

**Decision.** Three daemon threads (capture, transcribe, analyze) connected by queues. The audio queue is bounded (20 chunks) to make overload visible. Every event for the UI goes into one queue that a 100 ms `QTimer` drains. Shutdown is a `None` sentinel that flows downstream so pending audio is still transcribed.

**Consequences.** Each stage can fail without stopping the previous ones, and the whole pipeline can be tested without Qt (the tests push into the queues directly). Python's GIL is not a bottleneck here because CTranslate2 and the network release it. `asyncio` was considered and rejected: the heavy calls are blocking C extensions, so it would add complexity without removing threads.
