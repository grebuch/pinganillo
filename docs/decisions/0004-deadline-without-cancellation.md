# 0004 · Deadlines that stop waiting, one request in flight

**Context.** A stuck HTTP request must not freeze the analysis forever, but Python cannot safely kill a thread blocked on a socket.

**Decision.** `DeadlineCall` runs the request in a worker thread and waits with a deadline (45 s by default, configurable). On timeout it raises, the session pauses only the analysis, and the UI says so. A new call is refused while the previous worker is still alive, so slow servers cannot pile up parallel requests. Every response is tagged with the AI "generation"; pausing or swapping the provider bumps it and late answers are discarded.

**Consequences.** A timed-out request may still complete on the server and consume quota; the docs and UI say "stop waiting", not "cancel". HTTP-level timeouts on the client provide a second bound.
