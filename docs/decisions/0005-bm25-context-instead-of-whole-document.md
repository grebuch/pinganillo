# 0005 · BM25 passages instead of the whole document or embeddings

**Context.** Users can load a reference document (product sheet, policy, meeting notes). The prototype attached all of it, up to 40,000 characters (~10k tokens), to every request, several times a minute. That burns ChatGPT plan limits, costs money on paid APIs and slows down local models.

**Decision.** Split the document into ~700-character passages on paragraph boundaries and rank them against the current fragment plus recent context with BM25 (accent-folded tokens, small es/en/ca stopword list). Send only the best passages that fit in 2,500 characters, in document order, or nothing if nothing matches.

**Alternatives.** Embeddings would catch synonyms but need a second model (download, RAM, startup time) or a cloud call, which contradicts ADR 0001's spirit. BM25 is deterministic, dependency-free and testable.

**Consequences.** Requests are an order of magnitude smaller. Paraphrases and synonyms are missed; an optional embedding retriever behind the same `relevant()` interface is a welcome contribution.
